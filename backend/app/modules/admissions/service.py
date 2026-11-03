"""Admissions: enquiries and applications, documents, the public online form and conversion to a
student (which reuses the students service so logins and guardians are created the same way)."""

from collections.abc import Sequence

from fastapi import status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.tenant import scope_admissions, scope_branches
from app.db.base import utcnow
from app.modules.academics.models import AcademicYear, SchoolClass
from app.modules.admissions.models import (
    AdmissionApplication,
    AdmissionDocument,
    ApplicationSource,
    ApplicationStatus,
    DocumentType,
)
from app.modules.admissions.schemas import (
    AppCreate,
    AppDetail,
    AppOut,
    AppPage,
    AppUpdate,
    ConvertRequest,
    ConvertResult,
    DocOut,
    PublicAdmissions,
    PublicApply,
    PublicBranch,
    PublicClass,
    PublicReference,
    StatusChange,
    SummaryOut,
)
from app.modules.audit import service as audit
from app.modules.branches.models import Branch
from app.modules.schools.models import School
from app.modules.settings import service as settings_service
from app.modules.students import service as students_service
from app.modules.students.models import Gender, GuardianRelation, Student
from app.modules.students.schemas import EnrollmentIn, NewGuardian, StudentCreate
from app.modules.users.models import User

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_DOCUMENTS_PER_APPLICATION = 10

# Allowed next statuses. `enrolled` is reached only through conversion.
TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.ENQUIRY: frozenset({ApplicationStatus.APPLIED, ApplicationStatus.REJECTED}),
    ApplicationStatus.APPLIED: frozenset({ApplicationStatus.ADMITTED, ApplicationStatus.REJECTED}),
    ApplicationStatus.ADMITTED: frozenset({ApplicationStatus.REJECTED}),
    ApplicationStatus.REJECTED: frozenset({ApplicationStatus.ENQUIRY}),
    ApplicationStatus.ENROLLED: frozenset(),
}

_SIGNATURES: dict[DocumentType, tuple[bytes, ...]] = {
    DocumentType.PDF: (b"%PDF-",),
    DocumentType.PNG: (b"\x89PNG\r\n\x1a\n",),
    DocumentType.JPEG: (b"\xff\xd8\xff",),
}
_EXTENSIONS: dict[DocumentType, str] = {
    DocumentType.PDF: "pdf",
    DocumentType.PNG: "png",
    DocumentType.JPEG: "jpg",
}


def extension_for(content_type: str) -> str:
    return _EXTENSIONS.get(DocumentType(content_type), "bin")


def _not_found(what: str) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, f"{what} not found", "not_found")


def _unprocessable(detail: str, code: str = "unprocessable") -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, code)


def _conflict(detail: str, code: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, detail, code)


def sniff_document(data: bytes) -> DocumentType | None:
    """The real type from the file's leading bytes; None when it is not an accepted format."""
    for kind, signatures in _SIGNATURES.items():
        if any(data.startswith(sig) for sig in signatures):
            return kind
    return None


# ---- lookups and output ----


async def _get_application(
    db: AsyncSession, actor: User, application_id: int
) -> AdmissionApplication:
    application: AdmissionApplication | None = await db.scalar(
        scope_admissions(select(AdmissionApplication), actor).where(
            AdmissionApplication.id == application_id
        )
    )
    if application is None:
        raise _not_found("Application")
    return application


async def _outs(db: AsyncSession, apps: Sequence[AdmissionApplication]) -> list[AppOut]:
    """Output rows with branch and class names, in two queries (no N+1)."""
    if not apps:
        return []
    branch_ids = {a.branch_id for a in apps}
    class_ids = {a.class_id for a in apps if a.class_id is not None}
    branch_names = dict(
        (await db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(branch_ids)))).all()
    )
    class_names: dict[int, str] = {}
    if class_ids:
        class_names = dict(
            (
                await db.execute(
                    select(SchoolClass.id, SchoolClass.name).where(SchoolClass.id.in_(class_ids))
                )
            ).all()
        )
    return [
        AppOut(
            id=a.id,
            school_id=a.school_id,
            branch_id=a.branch_id,
            branch_name=branch_names.get(a.branch_id, ""),
            first_name=a.first_name,
            last_name=a.last_name,
            gender=a.gender,
            date_of_birth=a.date_of_birth,
            class_id=a.class_id,
            class_name=class_names.get(a.class_id) if a.class_id is not None else None,
            academic_year_id=a.academic_year_id,
            guardian_name=a.guardian_name,
            guardian_phone=a.guardian_phone,
            guardian_email=a.guardian_email,
            guardian_relation=a.guardian_relation,
            address=a.address,
            previous_school=a.previous_school,
            source=a.source,
            status=a.status,
            notes=a.notes,
            rejection_reason=a.rejection_reason,
            student_id=a.student_id,
            created_by=a.created_by,
            privacy_notice_accepted_at=a.privacy_notice_accepted_at,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in apps
    ]


async def _out(db: AsyncSession, application: AdmissionApplication) -> AppOut:
    return (await _outs(db, [application]))[0]


def _doc_out(doc: AdmissionDocument) -> DocOut:
    return DocOut(
        id=doc.id,
        name=doc.name,
        content_type=doc.content_type.value,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
    )


async def _resolve_branch(db: AsyncSession, actor: User, branch_id: int | None) -> Branch:
    """Branch-level staff use their own branch; the school owner names one."""
    wanted = actor.branch_id if actor.branch_id is not None else branch_id
    if wanted is None:
        raise _unprocessable("branch_id is required", "branch_required")
    branch: Branch | None = await db.scalar(
        scope_branches(select(Branch), actor).where(Branch.id == wanted)
    )
    if branch is None:
        raise _not_found("Branch")
    return branch


async def _check_class(db: AsyncSession, branch: Branch, class_id: int) -> None:
    found = await db.scalar(
        select(SchoolClass.id).where(
            SchoolClass.id == class_id,
            SchoolClass.branch_id == branch.id,
            SchoolClass.school_id == branch.school_id,
        )
    )
    if found is None:
        raise _unprocessable("Class does not belong to this branch", "invalid_class")


async def _check_year(db: AsyncSession, school_id: int, year_id: int) -> None:
    found = await db.scalar(
        select(AcademicYear.id).where(
            AcademicYear.id == year_id, AcademicYear.school_id == school_id
        )
    )
    if found is None:
        raise _not_found("Academic year")


# ---- staff: list, create, read, update ----


async def list_applications(
    db: AsyncSession,
    actor: User,
    *,
    status_filter: ApplicationStatus | None,
    branch_id: int | None,
    q: str | None,
    page: int,
    page_size: int,
) -> AppPage:
    stmt = scope_admissions(select(AdmissionApplication), actor)
    if status_filter is not None:
        stmt = stmt.where(AdmissionApplication.status == status_filter)
    if branch_id is not None:
        stmt = stmt.where(AdmissionApplication.branch_id == branch_id)
    term = (q or "").strip().lower()
    if term:
        digits = "".join(ch for ch in term if ch.isdigit())
        conditions = [
            func.lower(AdmissionApplication.first_name).contains(term, autoescape=True),
            func.lower(AdmissionApplication.last_name).contains(term, autoescape=True),
            func.lower(
                AdmissionApplication.first_name + " " + AdmissionApplication.last_name
            ).contains(term, autoescape=True),
            func.lower(AdmissionApplication.guardian_name).contains(term, autoescape=True),
        ]
        if len(digits) >= 3:
            conditions.append(AdmissionApplication.guardian_phone.contains(digits, autoescape=True))
        stmt = stmt.where(or_(*conditions))
    total = await db.scalar(
        select(func.count()).select_from(stmt.with_only_columns(AdmissionApplication.id).subquery())
    )
    rows = list(
        await db.scalars(
            stmt.order_by(AdmissionApplication.created_at.desc(), AdmissionApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AppPage(
        items=await _outs(db, rows), total=total or 0, page=page, page_size=page_size
    )


async def create_application(db: AsyncSession, actor: User, data: AppCreate) -> AppOut:
    branch = await _resolve_branch(db, actor, data.branch_id)
    if data.class_id is not None:
        await _check_class(db, branch, data.class_id)
    if data.academic_year_id is not None:
        await _check_year(db, branch.school_id, data.academic_year_id)
    application = AdmissionApplication(
        school_id=branch.school_id,
        branch_id=branch.id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        class_id=data.class_id,
        academic_year_id=data.academic_year_id,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=str(data.guardian_email).lower() if data.guardian_email else None,
        guardian_relation=data.guardian_relation,
        address=data.address,
        previous_school=data.previous_school,
        source=ApplicationSource(data.source),
        status=ApplicationStatus.ENQUIRY,
        notes=data.notes,
        created_by=actor.id,
    )
    db.add(application)
    await db.flush()
    await audit.record(
        db, actor, "admission.created", "application", application.id,
        detail={"source": data.source}, school_id=branch.school_id, branch_id=branch.id,
    )
    await db.commit()
    return await _out(db, application)


async def get_application(db: AsyncSession, actor: User, application_id: int) -> AppDetail:
    application = await _get_application(db, actor, application_id)
    await audit.record(
        db, actor, "admission.viewed", "application", application.id,
        school_id=application.school_id, branch_id=application.branch_id, commit=True,
    )
    docs = await db.scalars(
        select(AdmissionDocument)
        .where(AdmissionDocument.application_id == application.id)
        .order_by(AdmissionDocument.id)
    )
    out = await _out(db, application)
    return AppDetail(**out.model_dump(), documents=[_doc_out(d) for d in docs])


async def update_application(
    db: AsyncSession, actor: User, application_id: int, data: AppUpdate
) -> AppOut:
    application = await _get_application(db, actor, application_id)
    if application.student_id is not None:
        raise _conflict("This application has already been converted", "already_converted")
    changes = data.model_dump(exclude_unset=True)
    for field in (
        "first_name", "last_name", "guardian_name", "guardian_phone", "guardian_relation"
    ):
        if field in changes and changes[field] is None:
            raise _unprocessable(f"{field} cannot be null", "required_field")
    if changes.get("class_id") is not None:
        await _check_class(db, await _branch_of(db, application), changes["class_id"])
    if changes.get("academic_year_id") is not None:
        await _check_year(db, application.school_id, changes["academic_year_id"])
    if changes.get("guardian_email") is not None:
        changes["guardian_email"] = str(changes["guardian_email"]).lower()
    for field, value in changes.items():
        setattr(application, field, value)
    await audit.record(
        db, actor, "admission.updated", "application", application.id,
        detail={"fields": ",".join(sorted(changes))},
        school_id=application.school_id, branch_id=application.branch_id,
    )
    await db.commit()
    return await _out(db, application)


async def _branch_of(db: AsyncSession, application: AdmissionApplication) -> Branch:
    branch = await db.get(Branch, application.branch_id)
    if branch is None:  # FK guarantees it
        raise _not_found("Branch")
    return branch


# ---- status ----


async def change_status(
    db: AsyncSession, actor: User, application_id: int, data: StatusChange
) -> AppOut:
    application = await _get_application(db, actor, application_id)
    current = application.status
    target = data.status
    if target not in TRANSITIONS[current]:
        raise _conflict(
            f"An application cannot move from {current.value} to {target.value}",
            "invalid_transition",
        )
    if target == ApplicationStatus.REJECTED and not data.reason:
        raise _unprocessable("A reason is required to reject an application", "reason_required")
    application.status = target
    application.rejection_reason = data.reason if target == ApplicationStatus.REJECTED else None
    await audit.record(
        db, actor, "admission.status_changed", "application", application.id,
        detail={"from": current.value, "to": target.value},
        school_id=application.school_id, branch_id=application.branch_id,
    )
    await db.commit()
    return await _out(db, application)


# ---- documents ----


async def add_document(
    db: AsyncSession,
    actor: User,
    application_id: int,
    name: str,
    declared: str | None,
    data: bytes,
) -> DocOut:
    application = await _get_application(db, actor, application_id)
    if not data:
        raise _unprocessable("The file is empty", "empty_file")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE, "File must be at most 2 MB", "file_too_large"
        )
    kind = sniff_document(data)
    if kind is None:
        raise _unprocessable("Only PDF, PNG and JPEG files are accepted", "unsupported_file")
    if declared in {t.value for t in DocumentType} and declared != kind.value:
        raise _unprocessable("The file content does not match its type", "file_type_mismatch")
    count = await db.scalar(
        select(func.count())
        .select_from(AdmissionDocument)
        .where(AdmissionDocument.application_id == application.id)
    )
    if (count or 0) >= MAX_DOCUMENTS_PER_APPLICATION:
        raise _conflict("An application can hold at most 10 documents", "document_limit")
    doc = AdmissionDocument(
        school_id=application.school_id,
        application_id=application.id,
        name=name,
        content_type=kind,
        size_bytes=len(data),
        data=data,
        uploaded_by=actor.id,
    )
    db.add(doc)
    await db.flush()
    await audit.record(
        db, actor, "admission.document_added", "application", application.id,
        detail={"content_type": kind.value}, school_id=application.school_id,
        branch_id=application.branch_id,
    )
    await db.commit()
    return _doc_out(doc)


async def _get_document(
    db: AsyncSession, actor: User, application_id: int, doc_id: int
) -> tuple[AdmissionApplication, AdmissionDocument]:
    application = await _get_application(db, actor, application_id)
    doc = await db.scalar(
        select(AdmissionDocument).where(
            AdmissionDocument.id == doc_id,
            AdmissionDocument.application_id == application.id,
        )
    )
    if doc is None:
        raise _not_found("Document")
    return application, doc


async def read_document(
    db: AsyncSession, actor: User, application_id: int, doc_id: int
) -> AdmissionDocument:
    application, doc = await _get_document(db, actor, application_id, doc_id)
    await audit.record(
        db, actor, "admission.document_read", "application", application.id,
        detail={"document": doc.id}, school_id=application.school_id,
        branch_id=application.branch_id, commit=True,
    )
    return doc


async def delete_document(db: AsyncSession, actor: User, application_id: int, doc_id: int) -> None:
    application, doc = await _get_document(db, actor, application_id, doc_id)
    await db.delete(doc)
    await audit.record(
        db, actor, "admission.document_deleted", "application", application.id,
        detail={"document": doc_id}, school_id=application.school_id,
        branch_id=application.branch_id,
    )
    await db.commit()


# ---- conversion ----


async def convert(
    db: AsyncSession, actor: User, application_id: int, data: ConvertRequest
) -> ConvertResult:
    """Turn an admitted application into a student, in one transaction with the status change."""
    application = await _get_application(db, actor, application_id)
    if application.status != ApplicationStatus.ADMITTED or application.student_id is not None:
        raise _conflict("Only an admitted application can be converted", "invalid_transition")
    if application.gender is None or application.date_of_birth is None:
        raise _unprocessable(
            "Gender and date of birth are needed before conversion", "conversion_incomplete"
        )
    try:
        student_data = StudentCreate(
            branch_id=application.branch_id,
            first_name=application.first_name,
            last_name=application.last_name,
            gender=Gender(application.gender),
            date_of_birth=application.date_of_birth,
            admission_date=data.admission_date,
            admission_no=data.admission_no,
            address=application.address,
            previous_school=application.previous_school,
            guardians=[
                NewGuardian(
                    full_name=application.guardian_name,
                    relation=GuardianRelation(application.guardian_relation),
                    phone=application.guardian_phone,
                    email=application.guardian_email,
                    is_primary=True,
                    # Same as the student form with logins requested: the primary guardian gets
                    # a parent login (or is linked to an existing one).
                    create_login=True,
                )
            ],
            enrollment=EnrollmentIn(
                academic_year_id=data.academic_year_id,
                class_id=data.class_id,
                section_id=data.section_id,
            ),
            create_student_login=False,
        )
    except ValidationError:
        raise _unprocessable(
            "The application details are not valid for enrolment", "conversion_invalid"
        ) from None

    async def link(student: Student) -> None:
        application.student_id = student.id
        application.status = ApplicationStatus.ENROLLED
        await audit.record(
            db, actor, "admission.converted", "application", application.id,
            detail={"student": student.id}, school_id=application.school_id,
            branch_id=application.branch_id,
        )

    created = await students_service.create_student(
        db, actor, student_data, before_commit=link
    )
    return ConvertResult(student_id=created.id, credentials=created.credentials)


# ---- summary ----


async def summary(db: AsyncSession, actor: User) -> SummaryOut:
    rows = await db.execute(
        scope_admissions(
            select(AdmissionApplication.status, func.count()).group_by(AdmissionApplication.status),
            actor,
        )
    )
    counts = {ApplicationStatus(s): n for s, n in rows.all()}
    return SummaryOut(
        total=sum(counts.values()),
        enquiry=counts.get(ApplicationStatus.ENQUIRY, 0),
        applied=counts.get(ApplicationStatus.APPLIED, 0),
        admitted=counts.get(ApplicationStatus.ADMITTED, 0),
        rejected=counts.get(ApplicationStatus.REJECTED, 0),
        enrolled=counts.get(ApplicationStatus.ENROLLED, 0),
    )


# ---- public online form ----

def _hidden() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "Not found", "not_found")


async def _public_school(db: AsyncSession, code: str) -> School:
    """The school for a public form. Unknown code, inactive school, module or form switched off:
    all give the same 404 so nothing about the school is revealed."""
    school: School | None = await db.scalar(
        select(School).where(School.code == code.lower(), School.is_active.is_(True))
    )
    if school is None:
        raise _hidden()
    if not await settings_service.feature_enabled(db, school.id, "admissions"):
        raise _hidden()
    if not await settings_service.get_bool(
        db, "admissions.online_form_enabled", school_id=school.id
    ):
        raise _hidden()
    return school


async def public_info(db: AsyncSession, code: str) -> PublicAdmissions:
    school = await _public_school(db, code)
    branches = list(
        await db.scalars(
            select(Branch)
            .where(Branch.school_id == school.id, Branch.is_active.is_(True))
            .order_by(Branch.name, Branch.id)
        )
    )
    classes: list[PublicClass] = []
    if branches:
        for c in await db.scalars(
            select(SchoolClass)
            .where(SchoolClass.branch_id.in_([b.id for b in branches]))
            .order_by(SchoolClass.branch_id, SchoolClass.level)
        ):
            classes.append(PublicClass(id=c.id, branch_id=c.branch_id, name=c.name))
    return PublicAdmissions(
        school_name=school.name,
        branches=[PublicBranch(id=b.id, name=b.name) for b in branches],
        classes=classes,
        open=bool(branches),
    )


async def public_apply(db: AsyncSession, code: str, data: PublicApply) -> PublicReference:
    school = await _public_school(db, code)
    if data.website.strip():
        # Honeypot: a filled hidden field means a bot. Answer like a real save, store nothing.
        return PublicReference(reference="APP-0")
    branch: Branch | None = await db.scalar(
        select(Branch).where(
            Branch.id == data.branch_id,
            Branch.school_id == school.id,
            Branch.is_active.is_(True),
        )
    )
    if branch is None:
        raise _unprocessable("Choose a branch of this school", "invalid_branch")
    if data.class_id is not None:
        await _check_class(db, branch, data.class_id)
    application = AdmissionApplication(
        school_id=school.id,
        branch_id=branch.id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        class_id=data.class_id,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=str(data.guardian_email).lower() if data.guardian_email else None,
        guardian_relation=data.guardian_relation,
        address=data.address,
        previous_school=data.previous_school,
        source=ApplicationSource.ONLINE,
        status=ApplicationStatus.APPLIED,
        privacy_notice_accepted_at=utcnow(),
    )
    db.add(application)
    await db.flush()
    await audit.record(
        db, None, "admission.online_applied", "application", application.id,
        school_id=school.id, branch_id=branch.id,
    )
    await db.commit()
    return PublicReference(reference=f"APP-{application.id}")

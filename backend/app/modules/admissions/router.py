from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.admissions import service
from app.modules.admissions.models import ApplicationStatus
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
    PublicReference,
    StatusChange,
    SummaryOut,
)
from app.modules.settings.deps import require_feature
from app.modules.users.models import Role

# Staff of the school: the owner (all branches) and branch-level office staff. Teachers,
# accountants, parents and students never reach admissions.
_staff = require_roles(Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK)

router = APIRouter(
    prefix="/admissions",
    tags=["admissions"],
    dependencies=[Depends(require_feature("admissions")), Depends(_staff)],
)

# Anyone on the internet: no sign-in. Responses carry only what the form needs.
public_router = APIRouter(prefix="/public/schools/{code}", tags=["public"])

# Any text is looked up; an unknown code gets the same 404 as a disabled form.
SchoolCode = Annotated[str, Path(min_length=1, max_length=200)]


# ---- staff ----


@router.get("/applications", response_model=AppPage)
async def list_applications(
    db: DbSession,
    actor: CurrentUser,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    branch_id: Annotated[int | None, Query(ge=1)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AppPage:
    return await service.list_applications(
        db,
        actor,
        status_filter=status_filter,
        branch_id=branch_id,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/applications", response_model=AppOut, status_code=status.HTTP_201_CREATED
)
async def create_application(data: AppCreate, db: DbSession, actor: CurrentUser) -> AppOut:
    return await service.create_application(db, actor, data)


@router.get("/applications/{application_id}", response_model=AppDetail)
async def get_application(application_id: int, db: DbSession, actor: CurrentUser) -> AppDetail:
    return await service.get_application(db, actor, application_id)


@router.patch("/applications/{application_id}", response_model=AppOut)
async def update_application(
    application_id: int, data: AppUpdate, db: DbSession, actor: CurrentUser
) -> AppOut:
    return await service.update_application(db, actor, application_id, data)


@router.post("/applications/{application_id}/status", response_model=AppOut)
async def change_status(
    application_id: int, data: StatusChange, db: DbSession, actor: CurrentUser
) -> AppOut:
    return await service.change_status(db, actor, application_id, data)


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: int,
    db: DbSession,
    actor: CurrentUser,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
) -> DocOut:
    # Read one byte past the limit so an oversized file is detected without loading all of it.
    data = await file.read(service.MAX_DOCUMENT_BYTES + 1)
    return await service.add_document(
        db, actor, application_id, name.strip(), file.content_type, data
    )


@router.get("/applications/{application_id}/documents/{doc_id}")
async def download_document(
    application_id: int, doc_id: int, db: DbSession, actor: CurrentUser
) -> Response:
    doc = await service.read_document(db, actor, application_id, doc_id)
    filename = f"document-{doc.id}.{service.extension_for(doc.content_type.value)}"
    return Response(
        content=doc.data,
        media_type=doc.content_type.value,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete(
    "/applications/{application_id}/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    application_id: int, doc_id: int, db: DbSession, actor: CurrentUser
) -> Response:
    await service.delete_document(db, actor, application_id, doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/applications/{application_id}/convert",
    response_model=ConvertResult,
    status_code=status.HTTP_201_CREATED,
)
async def convert_application(
    application_id: int, data: ConvertRequest, db: DbSession, actor: CurrentUser
) -> ConvertResult:
    return await service.convert(db, actor, application_id, data)


@router.get("/summary", response_model=SummaryOut)
async def summary(db: DbSession, actor: CurrentUser) -> SummaryOut:
    return await service.summary(db, actor)


# ---- public online form ----


@public_router.get("/admissions", response_model=PublicAdmissions)
async def public_admissions(code: SchoolCode, db: DbSession) -> PublicAdmissions:
    return await service.public_info(db, code)


@public_router.post(
    "/applications",
    response_model=PublicReference,
    status_code=status.HTTP_201_CREATED,
)
async def public_apply(code: SchoolCode, data: PublicApply, db: DbSession) -> PublicReference:
    return await service.public_apply(db, code, data)

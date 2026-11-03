"""Results endpoints: report card JSON and PDF, progress for charts, and the class summary.

Staff (exam staff of the school) and the family of the student may read a report; families only
their own children or themselves and only published exams. The class summary is staff only.
"""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.exams import results_service as service
from app.modules.exams.common import FAMILY_ROLES, RESULT_STAFF_ROLES
from app.modules.exams.report_schemas import ClassSummaryOut, ProgressOut, ReportOut
from app.modules.settings.deps import require_feature

router = APIRouter(
    prefix="/exams",
    tags=["exams"],
    dependencies=[Depends(require_feature("exams"))],
)

_readers = Depends(require_roles(*RESULT_STAFF_ROLES, *FAMILY_ROLES))
_staff = Depends(require_roles(*RESULT_STAFF_ROLES))

Id = Annotated[int, Query(ge=1)]
Flag = Annotated[bool, Query()]


@router.get("/results/student", response_model=ReportOut, dependencies=[_readers])
async def student_report(
    db: DbSession,
    actor: CurrentUser,
    student_id: Id,
    academic_year_id: Id,
    include_unpublished: Flag = False,
) -> ReportOut:
    report = await service.build_report(
        db,
        actor,
        student_id,
        academic_year_id,
        include_unpublished=include_unpublished,
        format_override=None,
    )
    return report


@router.get("/results/student.pdf", dependencies=[_readers])
async def student_report_pdf(
    db: DbSession,
    actor: CurrentUser,
    student_id: Id,
    academic_year_id: Id,
    include_unpublished: Flag = False,
    format: Annotated[Literal["cbse", "hpc"] | None, Query()] = None,
) -> Response:
    pdf = await service.report_card_pdf(
        db,
        actor,
        student_id,
        academic_year_id,
        include_unpublished=include_unpublished,
        format_override=format,
    )
    safe_year = re.sub(r"[^0-9A-Za-z_-]", "", str(academic_year_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="report-card-{student_id}-{safe_year}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/progress", response_model=ProgressOut, dependencies=[_readers])
async def progress(
    db: DbSession, actor: CurrentUser, student_id: Id, academic_year_id: Id
) -> ProgressOut:
    return await service.build_progress(db, actor, student_id, academic_year_id)


@router.get("/results/class", response_model=ClassSummaryOut, dependencies=[_staff])
async def class_summary(
    db: DbSession, actor: CurrentUser, exam_id: Id, section_id: Id
) -> ClassSummaryOut:
    return await service.build_class_summary(db, actor, exam_id, section_id)

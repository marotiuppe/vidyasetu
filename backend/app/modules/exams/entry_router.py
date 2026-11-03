"""Marks entry, aspect grades and term remarks, one section at a time.

Teachers, management, headmasters and the school owner may write. Clerks may read. Writes are
all-or-nothing and report bad rows with their row numbers (422 `row_errors`).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.exams import marks_service as service
from app.modules.exams.common import MARK_ROLES, RESULT_STAFF_ROLES
from app.modules.exams.schemas import (
    AspectGradesOut,
    AspectGradesPut,
    MarksOut,
    MarksPut,
    TermRemarksOut,
    TermRemarksPut,
)
from app.modules.settings.deps import require_feature

router = APIRouter(
    prefix="/exams",
    tags=["exams"],
    dependencies=[Depends(require_feature("exams"))],
)

_write = Depends(require_roles(*MARK_ROLES))
_read = Depends(require_roles(*RESULT_STAFF_ROLES))

Id = Annotated[int, Query(ge=1)]


@router.get("/marks", response_model=MarksOut, dependencies=[_read])
async def get_marks(
    db: DbSession,
    actor: CurrentUser,
    exam_id: Id,
    section_id: Id,
    subject_id: Id,
) -> MarksOut:
    return await service.get_marks(db, actor, exam_id, section_id, subject_id)


@router.put("/marks", response_model=MarksOut, dependencies=[_write])
async def put_marks(data: MarksPut, db: DbSession, actor: CurrentUser) -> MarksOut:
    return await service.put_marks(db, actor, data)


@router.get("/aspect-grades", response_model=AspectGradesOut, dependencies=[_read])
async def get_aspect_grades(
    db: DbSession, actor: CurrentUser, term_id: Id, section_id: Id
) -> AspectGradesOut:
    return await service.get_aspect_grades(db, actor, term_id, section_id)


@router.put("/aspect-grades", response_model=AspectGradesOut, dependencies=[_write])
async def put_aspect_grades(
    data: AspectGradesPut, db: DbSession, actor: CurrentUser
) -> AspectGradesOut:
    return await service.put_aspect_grades(db, actor, data)


@router.get("/term-remarks", response_model=TermRemarksOut, dependencies=[_read])
async def get_term_remarks(
    db: DbSession, actor: CurrentUser, term_id: Id, section_id: Id
) -> TermRemarksOut:
    return await service.get_term_remarks(db, actor, term_id, section_id)


@router.put("/term-remarks", response_model=TermRemarksOut, dependencies=[_write])
async def put_term_remarks(
    data: TermRemarksPut,
    db: DbSession,
    actor: CurrentUser,
    term_id: Id,
    section_id: Id,
) -> TermRemarksOut:
    return await service.put_term_remarks(db, actor, term_id, section_id, data)

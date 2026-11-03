"""Exam configuration endpoints: terms, subjects, class subjects, exams, grading and aspects.

Writes need a configuring role (school owner, management, headmaster). Teachers and clerks may
read the configuration of their branch. Marks, aspect grades and results have their own routers.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.exams import config_service as service
from app.modules.exams.common import CONFIG_ROLES, RESULT_STAFF_ROLES
from app.modules.exams.schemas import (
    AspectIn,
    AspectOut,
    AspectPatch,
    ClassSubjectsOut,
    ClassSubjectsPut,
    ExamIn,
    ExamOut,
    ExamPatch,
    GradingOut,
    GradingPut,
    SubjectIn,
    SubjectOut,
    SubjectPatch,
    TermIn,
    TermOut,
    TermPatch,
)
from app.modules.settings.deps import require_feature

router = APIRouter(
    prefix="/exams",
    tags=["exams"],
    dependencies=[Depends(require_feature("exams"))],
)

_configure = Depends(require_roles(*CONFIG_ROLES))
_read = Depends(require_roles(*RESULT_STAFF_ROLES))

BranchQuery = Annotated[int | None, Query(ge=1)]


# ---- terms ----


@router.get("/terms", response_model=list[TermOut], dependencies=[_read])
async def list_terms(
    db: DbSession,
    actor: CurrentUser,
    branch_id: BranchQuery = None,
    academic_year_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[TermOut]:
    return await service.list_terms(db, actor, branch_id, academic_year_id)


@router.post(
    "/terms", response_model=TermOut, status_code=status.HTTP_201_CREATED, dependencies=[_configure]
)
async def create_term(
    data: TermIn, db: DbSession, actor: CurrentUser, branch_id: BranchQuery = None
) -> TermOut:
    return await service.create_term(db, actor, branch_id, data)


@router.patch("/terms/{term_id}", response_model=TermOut, dependencies=[_configure])
async def update_term(
    term_id: Annotated[int, Path(ge=1)], data: TermPatch, db: DbSession, actor: CurrentUser
) -> TermOut:
    return await service.update_term(db, actor, term_id, data)


# ---- subjects ----


@router.get("/subjects", response_model=list[SubjectOut], dependencies=[_read])
async def list_subjects(
    db: DbSession,
    actor: CurrentUser,
    branch_id: BranchQuery = None,
    include_inactive: bool = False,
) -> list[SubjectOut]:
    return await service.list_subjects(db, actor, branch_id, include_inactive)


@router.post(
    "/subjects",
    response_model=SubjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_configure],
)
async def create_subject(
    data: SubjectIn, db: DbSession, actor: CurrentUser, branch_id: BranchQuery = None
) -> SubjectOut:
    return await service.create_subject(db, actor, branch_id, data)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut, dependencies=[_configure])
async def update_subject(
    subject_id: Annotated[int, Path(ge=1)], data: SubjectPatch, db: DbSession, actor: CurrentUser
) -> SubjectOut:
    return await service.update_subject(db, actor, subject_id, data)


# ---- class subjects ----


@router.get("/class-subjects", response_model=ClassSubjectsOut, dependencies=[_read])
async def get_class_subjects(
    db: DbSession, actor: CurrentUser, class_id: Annotated[int, Query(ge=1)]
) -> ClassSubjectsOut:
    return await service.class_subjects(db, actor, class_id)


@router.put("/class-subjects", response_model=ClassSubjectsOut, dependencies=[_configure])
async def put_class_subjects(
    data: ClassSubjectsPut, db: DbSession, actor: CurrentUser
) -> ClassSubjectsOut:
    return await service.replace_class_subjects(db, actor, data)


# ---- exams ----


@router.get("/exams", response_model=list[ExamOut], dependencies=[_read])
async def list_exams(
    db: DbSession,
    actor: CurrentUser,
    term_id: Annotated[int | None, Query(ge=1)] = None,
    branch_id: BranchQuery = None,
) -> list[ExamOut]:
    return await service.list_exams(db, actor, term_id, branch_id)


@router.post(
    "/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED, dependencies=[_configure]
)
async def create_exam(data: ExamIn, db: DbSession, actor: CurrentUser) -> ExamOut:
    return await service.create_exam(db, actor, data)


@router.patch("/exams/{exam_id}", response_model=ExamOut, dependencies=[_configure])
async def update_exam(
    exam_id: Annotated[int, Path(ge=1)], data: ExamPatch, db: DbSession, actor: CurrentUser
) -> ExamOut:
    return await service.update_exam(db, actor, exam_id, data)


# ---- grading ----


@router.get("/grading", response_model=GradingOut, dependencies=[_read])
async def get_grading(db: DbSession, actor: CurrentUser) -> GradingOut:
    return await service.get_grading(db, actor)


@router.put("/grading", response_model=GradingOut, dependencies=[_configure])
async def put_grading(data: GradingPut, db: DbSession, actor: CurrentUser) -> GradingOut:
    return await service.replace_grading(db, actor, data)


# ---- report aspects ----


@router.get("/aspects", response_model=list[AspectOut], dependencies=[_read])
async def list_aspects(
    db: DbSession, actor: CurrentUser, branch_id: BranchQuery = None
) -> list[AspectOut]:
    return await service.list_aspects(db, actor, branch_id)


@router.post(
    "/aspects",
    response_model=AspectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_configure],
)
async def create_aspect(
    data: AspectIn, db: DbSession, actor: CurrentUser, branch_id: BranchQuery = None
) -> AspectOut:
    return await service.create_aspect(db, actor, branch_id, data)


@router.patch("/aspects/{aspect_id}", response_model=AspectOut, dependencies=[_configure])
async def update_aspect(
    aspect_id: Annotated[int, Path(ge=1)], data: AspectPatch, db: DbSession, actor: CurrentUser
) -> AspectOut:
    return await service.update_aspect(db, actor, aspect_id, data)

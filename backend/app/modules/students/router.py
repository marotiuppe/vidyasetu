from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.students import service
from app.modules.students.models import StudentStatus
from app.modules.students.schemas import (
    EnrollmentIn,
    GuardianCreate,
    GuardianOut,
    GuardianUpdate,
    ImportRequest,
    ImportResult,
    LoginCreate,
    StudentCreate,
    StudentDetail,
    StudentPage,
    StudentUpdate,
)
from app.modules.users.models import Role

router = APIRouter(tags=["students"])

_writers = Depends(
    require_roles(
        Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK
    )
)
_exporters = Depends(
    require_roles(
        Role.SUPER_ADMIN,
        Role.SCHOOL_OWNER,
        Role.MANAGEMENT,
        Role.HEADMASTER,
        Role.CLERK,
        Role.TEACHER,
        Role.ACCOUNTANT,
    )
)


class _Filters:
    def __init__(
        self,
        branch_id: int | None = None,
        class_id: int | None = None,
        section_id: int | None = None,
        academic_year_id: int | None = None,
        status: StudentStatus | None = None,
        q: Annotated[str | None, Query(max_length=100)] = None,
    ) -> None:
        self.filters = service.StudentFilters(
            branch_id=branch_id,
            class_id=class_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            status=status,
            q=q,
        )


Filters = Annotated[_Filters, Depends()]


@router.get("/students", response_model=StudentPage)
async def list_students(
    db: DbSession,
    actor: CurrentUser,
    f: Filters,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> StudentPage:
    return await service.list_students(db, actor, f.filters, page, page_size)


@router.get("/students/export", dependencies=[_exporters])
async def export_students(db: DbSession, actor: CurrentUser, f: Filters) -> Response:
    content = await service.export_csv(db, actor, f.filters)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="students.csv"'},
    )


@router.post("/students/import", response_model=ImportResult, dependencies=[_writers])
async def import_students(data: ImportRequest, db: DbSession, actor: CurrentUser) -> ImportResult:
    return await service.import_students(db, actor, data)


@router.post(
    "/students",
    response_model=StudentDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_writers],
)
async def create_student(data: StudentCreate, db: DbSession, actor: CurrentUser) -> StudentDetail:
    return await service.create_student(db, actor, data)


@router.get("/students/{student_id}", response_model=StudentDetail)
async def get_student(student_id: int, db: DbSession, actor: CurrentUser) -> StudentDetail:
    return await service.get_student(db, actor, student_id)


@router.patch("/students/{student_id}", response_model=StudentDetail, dependencies=[_writers])
async def update_student(
    student_id: int, data: StudentUpdate, db: DbSession, actor: CurrentUser
) -> StudentDetail:
    return await service.update_student(db, actor, student_id, data)


@router.put(
    "/students/{student_id}/enrollment", response_model=StudentDetail, dependencies=[_writers]
)
async def set_enrollment(
    student_id: int, data: EnrollmentIn, db: DbSession, actor: CurrentUser
) -> StudentDetail:
    return await service.set_enrollment(db, actor, student_id, data)


@router.post(
    "/students/{student_id}/login", response_model=StudentDetail, dependencies=[_writers]
)
async def create_student_login(
    student_id: int, data: LoginCreate, db: DbSession, actor: CurrentUser
) -> StudentDetail:
    return await service.create_student_login(db, actor, student_id, data)


@router.post(
    "/students/{student_id}/guardians",
    response_model=GuardianOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_writers],
)
async def add_guardian(
    student_id: int, data: GuardianCreate, db: DbSession, actor: CurrentUser
) -> GuardianOut:
    return await service.add_guardian(db, actor, student_id, data)


@router.patch("/guardians/{guardian_id}", response_model=GuardianOut, dependencies=[_writers])
async def update_guardian(
    guardian_id: int, data: GuardianUpdate, db: DbSession, actor: CurrentUser
) -> GuardianOut:
    return await service.update_guardian(db, actor, guardian_id, data)


@router.delete(
    "/guardians/{guardian_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_writers]
)
async def delete_guardian(guardian_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_guardian(db, actor, guardian_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/guardians/{guardian_id}/login", response_model=GuardianOut, dependencies=[_writers])
async def create_guardian_login(
    guardian_id: int, data: LoginCreate, db: DbSession, actor: CurrentUser
) -> GuardianOut:
    return await service.create_guardian_login(db, actor, guardian_id, data)


@router.delete(
    "/guardians/{guardian_id}/login",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_writers],
)
async def remove_guardian_login(guardian_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.remove_guardian_login(db, actor, guardian_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

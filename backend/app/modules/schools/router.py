from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.modules.schools.models import School
from app.modules.schools.schemas import SchoolCreate, SchoolOut, SchoolUpdate
from app.modules.users.models import Role, User

router = APIRouter(prefix="/schools", tags=["schools"])

_platform = require_roles(Role.SUPER_ADMIN)


@router.get("/me", response_model=SchoolOut)
async def my_school(db: DbSession, user: CurrentUser) -> SchoolOut:
    school = await db.get(School, user.school_id) if user.school_id else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No school")
    return SchoolOut.model_validate(school)


@router.get("", response_model=list[SchoolOut], dependencies=[Depends(_platform)])
async def list_schools(db: DbSession) -> list[SchoolOut]:
    result = await db.scalars(select(School).order_by(School.id))
    return [SchoolOut.model_validate(s) for s in result]


@router.post(
    "",
    response_model=SchoolOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_platform)],
)
async def create_school(data: SchoolCreate, db: DbSession) -> SchoolOut:
    """Create a new school together with its owner account."""
    school = School(name=data.name, code=data.code, board=data.board)
    db.add(school)
    try:
        await db.flush()
        db.add(
            User(
                school_id=school.id,
                email=data.owner_email.lower(),
                full_name=data.owner_full_name,
                password_hash=hash_password(data.owner_password),
                role=Role.SCHOOL_OWNER,
            )
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="School code or owner email already used"
        ) from None
    return SchoolOut.model_validate(school)


@router.patch("/{school_id}", response_model=SchoolOut, dependencies=[Depends(_platform)])
async def update_school(school_id: int, data: SchoolUpdate, db: DbSession) -> SchoolOut:
    school = await db.get(School, school_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="School not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)
    await db.commit()
    return SchoolOut.model_validate(school)

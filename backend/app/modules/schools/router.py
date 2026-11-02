import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.modules.schools import service
from app.modules.schools.models import School, SchoolLogo
from app.modules.schools.schemas import SchoolCreate, SchoolOut, SchoolOwnerUpdate, SchoolUpdate
from app.modules.users.models import Role, User
from app.modules.users.service import derive_unique_username, ensure_identity_available

router = APIRouter(prefix="/schools", tags=["schools"])

_platform = require_roles(Role.SUPER_ADMIN)
_owner = require_roles(Role.SCHOOL_OWNER)


@router.get("/me", response_model=SchoolOut)
async def my_school(db: DbSession, user: CurrentUser) -> SchoolOut:
    school = await db.get(School, user.school_id) if user.school_id else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No school")
    return await service.school_out(db, school)


@router.patch("/me", response_model=SchoolOut, dependencies=[Depends(_owner)])
async def update_my_school(data: SchoolOwnerUpdate, db: DbSession, user: CurrentUser) -> SchoolOut:
    """A school owner edits their own school's name and board (nothing else)."""
    school = await db.get(School, user.school_id) if user.school_id else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No school")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)
    await db.commit()
    return await service.school_out(db, school)


@router.get("", response_model=list[SchoolOut], dependencies=[Depends(_platform)])
async def list_schools(db: DbSession) -> list[SchoolOut]:
    result = await db.scalars(select(School).order_by(School.id))
    return await service.schools_out(db, result)


@router.get("/{school_id}", response_model=SchoolOut, dependencies=[Depends(_platform)])
async def get_school(school_id: int, db: DbSession) -> SchoolOut:
    school = await db.get(School, school_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="School not found")
    return await service.school_out(db, school)


@router.post(
    "",
    response_model=SchoolOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_platform)],
)
async def create_school(data: SchoolCreate, db: DbSession) -> SchoolOut:
    """Create a new school together with its owner account."""
    email = data.owner_email.lower()
    username = data.owner_username or await derive_unique_username(db, email)
    await ensure_identity_available(db, username=username, email=email)
    school = School(name=data.name, code=data.code, board=data.board)
    db.add(school)
    try:
        await db.flush()
        db.add(
            User(
                school_id=school.id,
                username=username,
                email=email,
                full_name=data.owner_full_name,
                password_hash=hash_password(data.owner_password),
                role=Role.SCHOOL_OWNER,
            )
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="School code or owner login already used"
        ) from None
    return await service.school_out(db, school)


@router.patch("/{school_id}", response_model=SchoolOut, dependencies=[Depends(_platform)])
async def update_school(school_id: int, data: SchoolUpdate, db: DbSession) -> SchoolOut:
    school = await db.get(School, school_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="School not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(school, field, value)
    await db.commit()
    return await service.school_out(db, school)


# ---- logo ----


async def _logo_target(db: DbSession, user: CurrentUser, school_id: int) -> School:
    """The school whose logo `user` may change: super admin any, owner their own only."""
    if user.role not in (Role.SUPER_ADMIN, Role.SCHOOL_OWNER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
    school = await db.get(School, school_id) if service.can_manage_logo(user, school_id) else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="School not found")
    return school


@router.put("/{school_id}/logo", response_model=SchoolOut)
async def upload_logo(
    school_id: int,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    content_type: Annotated[str | None, Header()] = None,
) -> SchoolOut:
    """Raw image body (image/png, image/jpeg or image/webp, max 1 MB)."""
    school = await _logo_target(db, user, school_id)
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in service.ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Logo must be image/png, image/jpeg or image/webp",
        )
    raw = await service.read_capped_body(request)
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image")
    png = await run_in_threadpool(service.normalise_logo, raw)
    await service.set_logo(db, school.id, png)
    return await service.school_out(db, school)


@router.delete("/{school_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logo(school_id: int, db: DbSession, user: CurrentUser) -> Response:
    school = await _logo_target(db, user, school_id)
    await service.delete_logo(db, school.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{school_id}/logo")
async def get_logo(
    school_id: int,
    db: DbSession,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """Public on purpose: used in <img> tags and on pre-login screens; a logo is not sensitive."""
    logo = await db.get(SchoolLogo, school_id)
    if logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No logo")
    etag = f'"{hashlib.sha256(logo.data).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=300"}
    if if_none_match is not None:
        tags = {t.strip().removeprefix("W/") for t in if_none_match.split(",")}
        if etag in tags or "*" in tags:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=logo.data, media_type=logo.content_type, headers=headers)

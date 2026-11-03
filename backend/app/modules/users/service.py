from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from app.core.errors import ApiError, IdentityInUse
from app.core.password_policy import enforce_password, random_password
from app.core.schema_types import ImportRowError, RowRejected, validation_message
from app.core.security import hash_password
from app.core.tenant import scope_users
from app.modules.audit import service as audit
from app.modules.auth import mfa
from app.modules.auth.service import revoke_user_sessions
from app.modules.branches.models import Branch
from app.modules.settings import service as settings_service
from app.modules.users.identity import suggest_username
from app.modules.users.models import BRANCH_ROLES, Role, User
from app.modules.users.schemas import (
    ImportCredential,
    UserCreate,
    UserImportRequest,
    UserImportResult,
    UserUpdate,
)

IDENTITY_TAKEN_CODE = "identity_taken"

# Which roles each role may create.
CREATABLE: dict[Role, set[Role]] = {
    Role.SUPER_ADMIN: set(Role),
    Role.SCHOOL_OWNER: set(Role) - {Role.SUPER_ADMIN},
    Role.MANAGEMENT: {Role.TEACHER, Role.ACCOUNTANT, Role.CLERK, Role.STUDENT, Role.PARENT},
    Role.HEADMASTER: {Role.TEACHER, Role.ACCOUNTANT, Role.CLERK, Role.STUDENT, Role.PARENT},
}


async def list_users(
    db: AsyncSession,
    actor: User,
    *,
    role: Role | None = None,
    branch_id: int | None = None,
    is_active: bool | None = None,
    q: str | None = None,
) -> list[User]:
    stmt = scope_users(select(User), actor)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if branch_id is not None:
        stmt = stmt.where(User.branch_id == branch_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
                User.username.like(like),
            )
        )
    result = await db.scalars(stmt.order_by(User.id))
    return list(result)


async def get_user(db: AsyncSession, actor: User, user_id: int) -> User:
    user: User | None = await db.scalar(scope_users(select(User), actor).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def _other_user_has(
    db: AsyncSession, condition: ColumnElement[bool], exclude_id: int | None
) -> bool:
    stmt = select(User.id).where(condition)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return await db.scalar(stmt) is not None


async def ensure_identity_available(
    db: AsyncSession,
    *,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    phone_school_id: int | None = None,
    exclude_id: int | None = None,
) -> None:
    """Raise IdentityInUse (409) if another account already uses one of these identifiers.

    Username and email are unique across schools. A mobile number is unique only within one
    school (`phone_school_id`; NULL means the platform admins), so two schools may share it.
    """
    if username is not None and await _other_user_has(db, User.username == username, exclude_id):
        raise IdentityInUse("Username already in use", "username_taken")
    if email is not None and await _other_user_has(db, User.email == email, exclude_id):
        raise IdentityInUse("Email already in use", "email_taken")
    if phone is not None:
        same_school = (
            User.school_id.is_(None)
            if phone_school_id is None
            else User.school_id == phone_school_id
        )
        if await _other_user_has(db, (User.phone == phone) & same_school, exclude_id):
            raise IdentityInUse("Mobile number already in use", "phone_taken")


async def derive_unique_username(db: AsyncSession, email: str) -> str:
    """Username from the email's local part, with a numeric suffix when it is taken."""
    base = suggest_username(email)
    candidate = base
    n = 2
    while await _other_user_has(db, User.username == candidate, None):
        candidate = f"{base[:45]}{n}"
        n += 1
    return candidate


async def build_user(db: AsyncSession, actor: User, data: UserCreate) -> User:
    """Check the rules for a new account and add it to the session (no commit, no audit).

    Shared by the single-account form and the bulk import, so both apply the same rules.
    """
    if data.role not in CREATABLE.get(actor.role, set()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed to create this role")
    school_id: int | None
    branch_id: int | None = None

    if data.role == Role.SUPER_ADMIN:
        school_id = None
    else:
        school_id = data.school_id if actor.role == Role.SUPER_ADMIN else actor.school_id
        if school_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="school_id required")
        if data.role in BRANCH_ROLES:
            # Branch-level creators can only create inside their own branch.
            branch_id = actor.branch_id if actor.branch_id is not None else data.branch_id
            if branch_id is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail="branch_id required"
                )
            branch = await db.scalar(
                select(Branch).where(Branch.id == branch_id, Branch.school_id == school_id)
            )
            if branch is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")

    enforce_password(
        data.password,
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        min_length=await settings_service.password_min_length(db, school_id),
    )
    await ensure_identity_available(
        db,
        username=data.username,
        email=data.email,
        phone=data.phone,
        phone_school_id=school_id,
    )
    user = User(
        school_id=school_id,
        branch_id=branch_id,
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=data.role,
        # The admin knows this password, so the user must replace it at first sign-in (school
        # setting; on by default).
        must_change_password=await settings_service.force_password_change(db, school_id),
    )
    db.add(user)
    return user


async def create_user(db: AsyncSession, actor: User, data: UserCreate) -> User:
    user = await build_user(db, actor, data)
    try:
        await db.flush()
        await audit.record(
            db, actor, "user.created", "user", user.id,
            detail={"role": user.role.value}, school_id=user.school_id, branch_id=user.branch_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise IdentityInUse(
            "Username, email or mobile number already in use", IDENTITY_TAKEN_CODE
        ) from None
    return user


def _import_role(value: object) -> Role:
    try:
        return Role(str(value or "").strip().lower())
    except ValueError:
        raise RowRejected("Unknown role") from None


async def import_users(db: AsyncSession, actor: User, data: UserImportRequest) -> UserImportResult:
    """Bulk staff accounts from rows. Each row goes through `build_user`, the same rules as the
    single form, inside its own savepoint. Credentials are returned once and never stored or
    audited; the audit row holds counts only."""
    school_id = data.school_id if actor.role == Role.SUPER_ADMIN else actor.school_id
    min_length = await settings_service.password_min_length(db, school_id)
    creatable = CREATABLE.get(actor.role, set())
    # A dry run works inside one savepoint that is rolled back at the end, so duplicates inside the
    # file are caught exactly as in a real import.
    savepoint = await db.begin_nested() if data.dry_run else None
    created = 0
    errors: list[ImportRowError] = []
    credentials: list[ImportCredential] = []
    for number, row in enumerate(data.rows, start=1):
        try:
            role = _import_role(row.get("role"))
            if role not in creatable:
                raise RowRejected("Not allowed to create this role")
            username = str(row.get("username") or "").strip()
            full_name = str(row.get("full_name") or "").strip()
            password = random_password(username, full_name, min_length=min_length)
            payload = UserCreate.model_validate(
                {
                    "username": row.get("username"),
                    "full_name": row.get("full_name"),
                    "role": role,
                    "email": row.get("email"),
                    "phone": row.get("mobile"),
                    "password": password,
                    "school_id": data.school_id,
                    "branch_id": data.branch_id,
                }
            )
            async with db.begin_nested():
                user = await build_user(db, actor, payload)
                await db.flush()
            created += 1
            credentials.append(
                ImportCredential(
                    username=user.username,
                    full_name=user.full_name,
                    role=user.role,
                    temporary_password=password,
                )
            )
        except ValidationError as exc:
            errors.append(ImportRowError(row=number, message=validation_message(exc)))
        except RowRejected as exc:
            errors.append(ImportRowError(row=number, message=str(exc)))
        except IntegrityError:
            errors.append(
                ImportRowError(
                    row=number, message="Username, email or mobile number already in use"
                )
            )
        except (HTTPException, ApiError, IdentityInUse) as exc:
            errors.append(ImportRowError(row=number, message=str(exc.detail)))
    if savepoint is not None:
        await savepoint.rollback()
        return UserImportResult(
            created=0, would_create=created, failed=len(errors), errors=errors, credentials=[]
        )
    await audit.record(
        db, actor, "user.imported", "user", None,
        detail={"created": created, "failed": len(errors)},
        school_id=school_id, branch_id=actor.branch_id,
    )
    await db.commit()
    return UserImportResult(
        created=created, failed=len(errors), errors=errors, credentials=credentials
    )


async def _get_manageable(db: AsyncSession, actor: User, user_id: int) -> User:
    """Target must be in the actor's scope (else 404) and of a role the actor may manage."""
    target = await get_user(db, actor, user_id)
    if target.role not in CREATABLE.get(actor.role, set()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed to manage this user")
    return target


async def update_user(db: AsyncSession, actor: User, user_id: int, data: UserUpdate) -> User:
    target = await _get_manageable(db, actor, user_id)
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="full_name cannot be null")
    if changes.get("is_active", True) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="is_active cannot be null")
    if changes.get("is_active") is False and target.id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself")
    await ensure_identity_available(
        db,
        email=changes.get("email"),
        phone=changes.get("phone"),
        phone_school_id=target.school_id,
        exclude_id=target.id,
    )
    for field, value in changes.items():
        setattr(target, field, value)
    if changes.get("is_active") is False:
        await revoke_user_sessions(db, target)
    if changes:
        sid, bid = target.school_id, target.branch_id
        if changes.get("is_active") is False:
            await audit.record(
                db, actor, "user.deactivated", "user", target.id, school_id=sid, branch_id=bid
            )
        elif changes.get("is_active") is True:
            await audit.record(
                db, actor, "user.reactivated", "user", target.id, school_id=sid, branch_id=bid
            )
        if set(changes) - {"is_active"}:
            await audit.record(
                db, actor, "user.updated", "user", target.id,
                detail={"fields": ",".join(sorted(set(changes) - {"is_active"}))},
                school_id=sid, branch_id=bid,
            )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise IdentityInUse("Email or mobile number already in use", IDENTITY_TAKEN_CODE) from None
    return target


async def reset_password(db: AsyncSession, actor: User, user_id: int, new_password: str) -> None:
    target = await _get_manageable(db, actor, user_id)
    enforce_password(
        new_password,
        username=target.username,
        email=target.email,
        full_name=target.full_name,
        min_length=await settings_service.password_min_length(db, target.school_id),
    )
    target.password_hash = hash_password(new_password)
    target.must_change_password = await settings_service.force_password_change(
        db, target.school_id
    )
    target.failed_login_count = 0
    target.locked_until = None
    await revoke_user_sessions(db, target)
    await audit.record(
        db, actor, "user.password_reset", "user", target.id,
        school_id=target.school_id, branch_id=target.branch_id,
    )
    await db.commit()


async def unlock_user(db: AsyncSession, actor: User, user_id: int) -> None:
    """Clear the failed-sign-in counter and any lock (same scope rules as a password reset)."""
    target = await _get_manageable(db, actor, user_id)
    target.failed_login_count = 0
    target.locked_until = None
    await audit.record(
        db, actor, "user.unlocked", "user", target.id,
        school_id=target.school_id, branch_id=target.branch_id,
    )
    await db.commit()


async def reset_mfa(db: AsyncSession, actor: User, user_id: int) -> None:
    """Remove a user's two-factor sign-in (lost device). Ends all their sessions.

    School owners may do this for users of their own school; platform admins for anyone. The
    caller has checked the role; the target must be in the actor's scope (else 404).
    """
    target = await get_user(db, actor, user_id)
    if target.id == actor.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Use the two-factor settings for your own account"
        )
    await mfa.clear_factor(db, target)
    await revoke_user_sessions(db, target)
    await audit.record(
        db, actor, "mfa.reset", "user", target.id,
        school_id=target.school_id, branch_id=target.branch_id,
    )
    await db.commit()

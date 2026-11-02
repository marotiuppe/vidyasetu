from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_branches, scope_notices, scope_tenant
from app.modules.academics.models import SchoolClass, Section
from app.modules.branches.models import Branch
from app.modules.notices.models import Notice, NoticeCategory, NoticeRead, TargetType
from app.modules.notices.schemas import (
    Author,
    NoticeCreate,
    NoticeOut,
    NoticePage,
    NoticeUpdate,
    TargetIn,
)
from app.modules.users.models import Role, User

IST = timezone(timedelta(hours=5, minutes=30))  # no DST, so a fixed offset is exact
PIN_ROLES = {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER}
BRANCH_MANAGERS = {Role.MANAGEMENT, Role.HEADMASTER}


def today() -> date:
    return datetime.now(IST).date()


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Notice not found")


def _forbidden(detail: str = "Not allowed") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _can_manage(actor: User, notice: Notice) -> bool:
    """Author, school owner, or management/headmaster of the notice's branch."""
    if notice.school_id != actor.school_id:
        return False
    if actor.role == Role.SCHOOL_OWNER or notice.created_by == actor.id:
        return True
    return (
        actor.role in BRANCH_MANAGERS
        and notice.branch_id is not None
        and notice.branch_id == actor.branch_id
    )


# ---- output building (batched) ----


async def _build(
    db: AsyncSession, actor: User, notices: list[Notice], day: date
) -> list[NoticeOut]:
    if not notices:
        return []
    ids = [n.id for n in notices]

    authors = {
        u.id: u
        for u in (
            await db.scalars(select(User).where(User.id.in_({n.created_by for n in notices})))
        ).all()
    }
    read_ids = set(
        (
            await db.scalars(
                select(NoticeRead.notice_id).where(
                    NoticeRead.user_id == actor.id, NoticeRead.notice_id.in_(ids)
                )
            )
        ).all()
    )
    managed = {n.id for n in notices if _can_manage(actor, n)}
    counts: dict[int, int] = {}
    if managed:
        rows = await db.execute(
            select(NoticeRead.notice_id, func.count())
            .where(NoticeRead.notice_id.in_(managed))
            .group_by(NoticeRead.notice_id)
        )
        counts = {nid: c for nid, c in rows.all()}

    branch_ids = {n.branch_id for n in notices if n.target_type == TargetType.BRANCH}
    branches = {}
    if branch_ids:
        found = await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))
        branches = {b.id: b.name for b in found}
    section_ids = {n.section_id for n in notices if n.section_id is not None}
    sections = {}
    if section_ids:
        sections = {
            s.id: s for s in (await db.scalars(select(Section).where(Section.id.in_(section_ids))))
        }
    class_ids = {n.class_id for n in notices if n.class_id is not None}
    class_ids |= {s.class_id for s in sections.values()}
    classes = {}
    if class_ids:
        classes = {
            c.id: c.name
            for c in (await db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))))
        }

    def label(n: Notice) -> str:
        if n.target_type == TargetType.SCHOOL:
            return "Whole school"
        if n.target_type == TargetType.BRANCH:
            return branches.get(n.branch_id or 0, "")
        if n.target_type == TargetType.CLASS:
            return classes.get(n.class_id or 0, "")
        sec = sections.get(n.section_id or 0)
        if sec is None:
            return ""
        return f"{classes.get(sec.class_id, '')} - {sec.name}"

    out: list[NoticeOut] = []
    for n in notices:
        author = authors.get(n.created_by)
        out.append(
            NoticeOut(
                id=n.id,
                title=n.title,
                body=n.body,
                category=n.category,
                is_pinned=n.is_pinned,
                expires_on=n.expires_on,
                is_expired=n.expires_on is not None and n.expires_on < day,
                target_type=n.target_type,
                target_label=label(n),
                branch_id=n.branch_id,
                class_id=n.class_id,
                section_id=n.section_id,
                author=(
                    Author(id=author.id, full_name=author.full_name, role=author.role.value)
                    if author
                    else None
                ),
                created_at=n.created_at,
                is_read=n.id in read_ids,
                read_count=counts.get(n.id, 0) if n.id in managed else None,
                can_edit=_can_manage(actor, n),
            )
        )
    return out


async def _visible(db: AsyncSession, actor: User, notice_id: int) -> Notice:
    notice = await db.scalar(
        scope_notices(select(Notice).where(Notice.id == notice_id), actor, today())
    )
    if notice is None:
        raise _not_found()
    return notice


# ---- queries ----


async def unread_count(db: AsyncSession, actor: User) -> int:
    stmt = scope_notices(select(func.count(Notice.id)), actor, today(), only_active=True).where(
        ~exists().where(NoticeRead.notice_id == Notice.id, NoticeRead.user_id == actor.id)
    )
    return int(await db.scalar(stmt) or 0)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_notices(
    db: AsyncSession,
    actor: User,
    *,
    category: NoticeCategory | None,
    q: str | None,
    unread_only: bool,
    pinned: bool | None,
    page: int,
    page_size: int,
) -> NoticePage:
    day = today()
    base = scope_notices(select(Notice), actor, day)
    if category is not None:
        base = base.where(Notice.category == category)
    if pinned is not None:
        base = base.where(Notice.is_pinned.is_(pinned))
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        base = base.where(
            Notice.title.ilike(pattern, escape="\\") | Notice.body.ilike(pattern, escape="\\")
        )
    if unread_only:
        base = base.where(
            ~exists().where(NoticeRead.notice_id == Notice.id, NoticeRead.user_id == actor.id)
        )
    total = int(
        await db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    )
    rows = (
        await db.scalars(
            base.order_by(Notice.is_pinned.desc(), Notice.created_at.desc(), Notice.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return NoticePage(
        items=await _build(db, actor, list(rows), day),
        total=total,
        page=page,
        page_size=page_size,
        unread_count=await unread_count(db, actor),
    )


async def get_notice(db: AsyncSession, actor: User, notice_id: int) -> NoticeOut:
    notice = await _visible(db, actor, notice_id)
    return (await _build(db, actor, [notice], today()))[0]


# ---- create / update / delete ----


async def _resolve_target(
    db: AsyncSession, actor: User, target: TargetIn
) -> tuple[int | None, int | None, int | None]:
    """Validate the target for `actor`; return (branch_id, class_id, section_id) to store."""
    kind = target.type
    if kind == TargetType.SCHOOL:
        if target.branch_id or target.class_id or target.section_id:
            raise _unprocessable("A school-wide notice cannot have a branch, class or section")
        return None, None, None

    if kind == TargetType.BRANCH:
        if target.class_id or target.section_id:
            raise _unprocessable("A branch notice cannot have a class or section")
        branch_id = target.branch_id if target.branch_id is not None else actor.branch_id
        if branch_id is None:
            raise _unprocessable("branch_id is required")
        branch = await db.scalar(
            scope_branches(select(Branch).where(Branch.id == branch_id), actor)
        )
        if branch is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
        return branch.id, None, None

    if kind == TargetType.CLASS:
        if target.section_id:
            raise _unprocessable("A class notice cannot have a section")
        if target.class_id is None:
            raise _unprocessable("class_id is required")
        klass = await db.scalar(
            scope_tenant(
                select(SchoolClass).where(SchoolClass.id == target.class_id), SchoolClass, actor
            )
        )
        if klass is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Class not found")
        if target.branch_id is not None and target.branch_id != klass.branch_id:
            raise _unprocessable("The class does not belong to that branch")
        return klass.branch_id, klass.id, None

    if target.section_id is None:
        raise _unprocessable("section_id is required")
    section = await db.scalar(
        scope_tenant(select(Section).where(Section.id == target.section_id), Section, actor)
    )
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Section not found")
    if target.class_id is not None and target.class_id != section.class_id:
        raise _unprocessable("The section does not belong to that class")
    if target.branch_id is not None and target.branch_id != section.branch_id:
        raise _unprocessable("The section does not belong to that branch")
    return section.branch_id, section.class_id, section.id


def _check_may_post(actor: User, kind: TargetType) -> None:
    if actor.school_id is None:
        raise _forbidden()
    if actor.role == Role.SCHOOL_OWNER:
        return
    if actor.role in BRANCH_MANAGERS and kind != TargetType.SCHOOL:
        return
    if actor.role == Role.TEACHER and kind in (TargetType.CLASS, TargetType.SECTION):
        return
    raise _forbidden("You are not allowed to post a notice for this audience")


async def create_notice(db: AsyncSession, actor: User, data: NoticeCreate) -> NoticeOut:
    _check_may_post(actor, data.target.type)
    if data.is_pinned and actor.role not in PIN_ROLES:
        raise _forbidden("You are not allowed to pin notices")
    day = today()
    if data.expires_on is not None and data.expires_on < day:
        raise _unprocessable("expires_on cannot be in the past")
    branch_id, class_id, section_id = await _resolve_target(db, actor, data.target)
    assert actor.school_id is not None
    notice = Notice(
        school_id=actor.school_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
        target_type=data.target.type,
        title=data.title,
        body=data.body,
        category=data.category,
        is_pinned=bool(data.is_pinned),
        expires_on=data.expires_on,
        created_by=actor.id,
    )
    db.add(notice)
    await db.commit()
    await db.refresh(notice)
    return (await _build(db, actor, [notice], day))[0]


async def update_notice(
    db: AsyncSession, actor: User, notice_id: int, data: NoticeUpdate
) -> NoticeOut:
    notice = await _visible(db, actor, notice_id)
    if not _can_manage(actor, notice):
        raise _forbidden()
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_pinned") and actor.role not in PIN_ROLES:
        raise _forbidden("You are not allowed to pin notices")
    day = today()
    new_expiry = changes.get("expires_on")
    if new_expiry is not None and new_expiry < day:
        raise _unprocessable("expires_on cannot be in the past")
    for field, value in changes.items():
        setattr(notice, field, value)
    await db.commit()
    await db.refresh(notice)
    return (await _build(db, actor, [notice], day))[0]


async def delete_notice(db: AsyncSession, actor: User, notice_id: int) -> None:
    notice = await _visible(db, actor, notice_id)
    if not _can_manage(actor, notice):
        raise _forbidden()
    await db.execute(delete(NoticeRead).where(NoticeRead.notice_id == notice.id))
    await db.delete(notice)
    await db.commit()


# ---- read tracking ----


async def mark_read(db: AsyncSession, actor: User, notice_id: int) -> None:
    notice = await _visible(db, actor, notice_id)
    already = await db.scalar(
        select(NoticeRead.id).where(
            NoticeRead.notice_id == notice.id, NoticeRead.user_id == actor.id
        )
    )
    if already is not None:
        return
    db.add(NoticeRead(notice_id=notice.id, user_id=actor.id))
    try:
        await db.commit()
    except IntegrityError:  # a concurrent request already marked it
        await db.rollback()


async def mark_all_read(db: AsyncSession, actor: User) -> None:
    stmt = scope_notices(select(Notice.id), actor, today(), only_active=True).where(
        ~exists().where(NoticeRead.notice_id == Notice.id, NoticeRead.user_id == actor.id)
    )
    ids = (await db.scalars(stmt)).all()
    if not ids:
        return
    db.add_all(NoticeRead(notice_id=i, user_id=actor.id) for i in ids)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


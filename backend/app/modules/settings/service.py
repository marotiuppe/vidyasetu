"""The one place that reads and writes settings.

School and branch ids come from the signed-in user. Only a platform admin may name a school, and
only a school owner may name one of their own branches. Setting values are never logged.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import utcnow
from app.modules.branches.models import Branch
from app.modules.schools.models import School
from app.modules.settings import crypto
from app.modules.settings.models import Setting, UserPreference
from app.modules.settings.registry import (
    FEATURES,
    INTEGRATIONS,
    LEVELS,
    REGISTRY,
    SettingDef,
    defs_for_level,
)
from app.modules.settings.schemas import (
    IntegrationTestResult,
    LevelInfo,
    LevelsOut,
    SettingItem,
)
from app.modules.users.models import Role, User

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DEFAULT_MAX_LEN = {"string": 200, "text": 2000, "secret": 500, "email": 254}
_BRANCH_LEVEL_ROLES = frozenset(
    {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.TEACHER, Role.ACCOUNTANT, Role.CLERK}
)

Rows = dict[str, dict[str, Any]]  # level -> key -> Setting | UserPreference


def _err(status_code: int, detail: str, code: str) -> ApiError:
    return ApiError(status_code, detail, code)


def _forbidden() -> ApiError:
    return _err(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")


def _invalid(detail: str) -> ApiError:
    return _err(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, "invalid_setting")


# ---------------------------------------------------------------- resolution


@dataclass(frozen=True)
class Ctx:
    school_id: int | None = None
    branch_id: int | None = None
    user_id: int | None = None


@dataclass(frozen=True)
class Resolved:
    value: Any
    source: str  # the level name of a stored value, or "env" / "default"
    row: Any = None


def _closure(keys: Iterable[str]) -> set[str]:
    """The keys plus every key they inherit from or are bounded by."""
    out: set[str] = set()
    stack = list(keys)
    while stack:
        k = stack.pop()
        if k in out:
            continue
        out.add(k)
        d = REGISTRY[k]
        stack.extend(x for x in (d.inherit, *d.bounded_by) if x)
    return out


async def _load_rows(db: AsyncSession, ctx: Ctx, keys: set[str]) -> Rows:
    scopes = ["platform"]
    if ctx.school_id is not None:
        scopes.append(f"s:{ctx.school_id}")
    if ctx.branch_id is not None:
        scopes.append(f"b:{ctx.branch_id}")
    rows: Rows = {lvl: {} for lvl in LEVELS}
    result = await db.scalars(
        select(Setting).where(Setting.scope.in_(scopes), Setting.key.in_(keys))
    )
    for row in result:
        rows[row.level][row.key] = row
    if ctx.user_id is not None:
        prefs = await db.scalars(
            select(UserPreference).where(
                UserPreference.user_id == ctx.user_id, UserPreference.key.in_(keys)
            )
        )
        for pref in prefs:
            rows["user"][pref.key] = pref
    return rows


def _env_value(d: SettingDef) -> Any:
    if d.env is None:
        return None
    value = getattr(get_settings(), d.env, None)
    if value is None:
        return None
    # A value equal to the built-in default counts as "default", not as an .env override.
    field = Settings.model_fields.get(d.env)
    if field is not None and field.default == value:
        return None
    return value


def _resolve_def(d: SettingDef, rows: Rows) -> Resolved:
    row = rows.get(d.level, {}).get(d.key)
    if row is not None:
        return Resolved(row.value, d.level, row)
    if d.inherit is not None:
        inherited = _resolve_def(REGISTRY[d.inherit], rows)
        if inherited.source != "default" or REGISTRY[d.inherit].default is not None:
            return Resolved(inherited.value, inherited.source, inherited.row)
    env = _env_value(d)
    if env is not None:
        return Resolved(env, "env")
    return Resolved(d.default, "default")


def _bounds(d: SettingDef, rows: Rows) -> tuple[int | None, int | None]:
    lo, hi = d.min, d.max
    lo_key, hi_key = d.bounded_by
    if lo_key is not None:
        v = _resolve_def(REGISTRY[lo_key], rows).value
        if isinstance(v, int) and not isinstance(v, bool):
            lo = max(lo, v) if lo is not None else v
    if hi_key is not None:
        v = _resolve_def(REGISTRY[hi_key], rows).value
        if isinstance(v, int) and not isinstance(v, bool):
            hi = min(hi, v) if hi is not None else v
    if lo is not None and hi is not None and lo > hi:
        hi = lo
    return lo, hi


def _effective(d: SettingDef, rows: Rows) -> Resolved:
    res = _resolve_def(d, rows)
    value = res.value
    if d.secret:
        plain = crypto.decrypt(value) if isinstance(value, str) else None
        return Resolved(plain, res.source, res.row)
    if d.bounded_by != (None, None) and isinstance(value, int) and not isinstance(value, bool):
        lo, hi = _bounds(d, rows)
        if lo is not None:
            value = max(value, lo)
        if hi is not None:
            value = min(value, hi)
    return Resolved(value, res.source, res.row)


async def resolve_many(db: AsyncSession, keys: Iterable[str], ctx: Ctx) -> dict[str, Any]:
    """Effective values (user > branch > school > platform > env > default) for several keys.

    Stored values of bounded settings are clamped into the platform limits; secrets are
    decrypted (internal use only, never return them from an endpoint).
    """
    wanted = list(keys)
    rows = await _load_rows(db, ctx, _closure(wanted))
    return {k: _effective(REGISTRY[k], rows).value for k in wanted}


def ctx_for(
    user: User | None = None, school_id: int | None = None, branch_id: int | None = None
) -> Ctx:
    if user is not None:
        return Ctx(user.school_id, user.branch_id, user.id)
    return Ctx(school_id, branch_id)


async def resolve(
    db: AsyncSession,
    key: str,
    *,
    user: User | None = None,
    school_id: int | None = None,
    branch_id: int | None = None,
) -> Any:
    return (await resolve_many(db, [key], ctx_for(user, school_id, branch_id)))[key]


async def get_int(db: AsyncSession, key: str, **scope: Any) -> int:
    return int(await resolve(db, key, **scope))


async def get_bool(db: AsyncSession, key: str, **scope: Any) -> bool:
    return bool(await resolve(db, key, **scope))


async def get_str(db: AsyncSession, key: str, **scope: Any) -> str | None:
    value = await resolve(db, key, **scope)
    return None if value is None else str(value)


# ----------------------------------------------------- consumer helpers


async def lockout_limits(db: AsyncSession, school_id: int | None) -> tuple[int, int]:
    """(max failed attempts, lockout minutes) for a school; platform accounts use .env defaults."""
    keys = ["security.login_max_attempts", "security.login_lockout_minutes"]
    if school_id is None:
        s = get_settings()
        return s.login_max_attempts_default, s.login_lockout_minutes_default
    values = await resolve_many(db, keys, Ctx(school_id=school_id))
    return int(values[keys[0]]), int(values[keys[1]])


async def school_lockouts(
    db: AsyncSession, school_ids: Iterable[int]
) -> dict[int, tuple[int, int]]:
    ids = list(school_ids)
    keys = {"security.login_max_attempts", "security.login_lockout_minutes"}
    wanted = _closure(keys)
    platform = await _load_rows(db, Ctx(), wanted)
    stored = await db.scalars(
        select(Setting).where(
            Setting.scope.in_([f"s:{i}" for i in ids]), Setting.key.in_(keys)
        )
    )
    per_school: dict[int, dict[str, Any]] = {i: {} for i in ids}
    for row in stored:
        if row.school_id is not None:
            per_school[row.school_id][row.key] = row
    out: dict[int, tuple[int, int]] = {}
    for sid in ids:
        rows: Rows = {**platform, "school": per_school[sid]}
        a = _effective(REGISTRY["security.login_max_attempts"], rows).value
        m = _effective(REGISTRY["security.login_lockout_minutes"], rows).value
        out[sid] = (int(a), int(m))
    return out


async def password_min_length(db: AsyncSession, school_id: int | None) -> int:
    key = "security.password_min_length"
    if school_id is None:
        return int((await resolve_many(db, ["limits.password_min_length"], Ctx()))[
            "limits.password_min_length"
        ])
    return max(10, int(await resolve(db, key, school_id=school_id)))


async def school_features(db: AsyncSession, school_id: int) -> dict[str, bool]:
    keys = [f"feature.{f}" for f in FEATURES]
    values = await resolve_many(db, keys, Ctx(school_id=school_id))
    return {f: bool(values[f"feature.{f}"]) for f in FEATURES}


async def feature_enabled(db: AsyncSession, school_id: int, feature: str) -> bool:
    return bool(await resolve(db, f"feature.{feature}", school_id=school_id))


async def legal_values(db: AsyncSession, school_id: int | None) -> dict[str, Any]:
    keys = [k for k in REGISTRY if k.startswith("legal.")]
    return await resolve_many(db, keys, Ctx(school_id=school_id))


# ----------------------------------------------------------- validation


def _coerce(d: SettingDef, raw: Any, lo: int | None, hi: int | None) -> Any:
    t = d.type
    if t in ("string", "text", "secret", "email", "choice", "date", "time"):
        if not isinstance(raw, str):
            raise _invalid(f"{d.label}: must be text")
        text = raw.strip()
        if "\x00" in text:
            raise _invalid(f"{d.label}: invalid characters")
        if len(text) > (d.max_len or _DEFAULT_MAX_LEN.get(t, 200)):
            raise _invalid(f"{d.label}: too long")
        if t == "choice" and text not in d.choices:
            raise _invalid(f"{d.label}: must be one of {', '.join(d.choices)}")
        if t == "email":
            local, sep, domain = text.partition("@")
            if not (local and sep and "." in domain and " " not in text):
                raise _invalid(f"{d.label}: must be an email address")
        if t == "date":
            try:
                date.fromisoformat(text)
            except ValueError:
                raise _invalid(f"{d.label}: must be a date (YYYY-MM-DD)") from None
        if t == "time" and not _TIME.match(text):
            raise _invalid(f"{d.label}: must be a time (HH:MM)")
        if d.pattern is not None and not re.match(d.pattern, text):
            raise _invalid(f"{d.label}: invalid format")
        return text
    if t == "bool":
        if not isinstance(raw, bool):
            raise _invalid(f"{d.label}: must be true or false")
        return raw
    if t == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise _invalid(f"{d.label}: must be a whole number")
        if (lo is not None and raw < lo) or (hi is not None and raw > hi):
            raise _invalid(f"{d.label}: must be between {lo} and {hi}")
        return raw
    raise _invalid("Unsupported setting type")  # pragma: no cover


_PAIRS = {
    "limits.lockout_attempts_min": ("limits.lockout_attempts_max", True),
    "limits.lockout_attempts_max": ("limits.lockout_attempts_min", False),
    "limits.lockout_minutes_min": ("limits.lockout_minutes_max", True),
    "limits.lockout_minutes_max": ("limits.lockout_minutes_min", False),
}


# --------------------------------------------------------------- targets


@dataclass(frozen=True)
class Target:
    level: str
    school_id: int | None = None
    branch_id: int | None = None
    user_id: int | None = None

    @property
    def ctx(self) -> Ctx:
        return Ctx(self.school_id, self.branch_id, self.user_id)

    @property
    def scope(self) -> str:
        if self.level == "platform":
            return "platform"
        if self.level == "school":
            return f"s:{self.school_id}"
        return f"b:{self.branch_id}"


def _viewable(user: User, d: SettingDef) -> bool:
    return user.role == Role.SUPER_ADMIN or user.role in d.view_roles


def _editable(user: User, d: SettingDef) -> bool:
    if d.level == "user":
        return True
    return user.role == Role.SUPER_ADMIN or user.role in d.edit_roles


async def _target(
    db: AsyncSession, user: User, level: str, school_id: int | None, branch_id: int | None
) -> Target:
    admin = user.role == Role.SUPER_ADMIN
    if level == "user":
        return Target("user", user.school_id, user.branch_id, user.id)
    if level == "platform":
        if not admin:
            raise _forbidden()
        return Target("platform")
    if level == "school":
        if admin:
            if school_id is None:
                raise _invalid("school_id is required")
            if await db.get(School, school_id) is None:
                raise _err(status.HTTP_404_NOT_FOUND, "School not found", "not_found")
            return Target("school", school_id)
        if user.school_id is None or (school_id is not None and school_id != user.school_id):
            raise _forbidden()
        return Target("school", user.school_id)
    # branch level
    if admin:
        if branch_id is None:
            raise _invalid("branch_id is required")
        branch = await db.get(Branch, branch_id)
        if branch is None:
            raise _err(status.HTTP_404_NOT_FOUND, "Branch not found", "not_found")
        return Target("branch", branch.school_id, branch.id)
    if user.school_id is None or user.role not in _BRANCH_LEVEL_ROLES:
        raise _forbidden()
    if user.role == Role.SCHOOL_OWNER:
        if branch_id is None:
            raise _invalid("branch_id is required")
        branch = await db.get(Branch, branch_id)
        if branch is None or branch.school_id != user.school_id:
            raise _err(status.HTTP_404_NOT_FOUND, "Branch not found", "not_found")
        return Target("branch", user.school_id, branch.id)
    if user.branch_id is None or (branch_id is not None and branch_id != user.branch_id):
        raise _forbidden()
    return Target("branch", user.school_id, user.branch_id)


def _find_def(level: str, key: str) -> SettingDef:
    d = REGISTRY.get(key)
    if d is None or d.level != level:
        raise _err(status.HTTP_404_NOT_FOUND, "Unknown setting", "not_found")
    return d


# ----------------------------------------------------------------- items


async def _names(db: AsyncSession, rows: Iterable[Any]) -> dict[int, str]:
    ids = {r.updated_by for r in rows if isinstance(r, Setting) and r.updated_by is not None}
    if not ids:
        return {}
    found = await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
    return {uid: name for uid, name in found}


async def _items(
    db: AsyncSession, user: User, target: Target, defs: list[SettingDef]
) -> list[SettingItem]:
    rows = await _load_rows(db, target.ctx, _closure(d.key for d in defs))
    own = [rows[target.level].get(d.key) for d in defs]
    names = await _names(db, [r for r in own if r is not None])
    items: list[SettingItem] = []
    for d, row in zip(defs, own, strict=True):
        res = _effective(d, rows)
        lo, hi = _bounds(d, rows) if d.type == "int" else (None, None)
        source = "own" if res.source == d.level else res.source
        items.append(
            SettingItem(
                key=d.key,
                group=d.group,
                label=d.label,
                help=d.help,
                type=d.type,
                choices=list(d.choices),
                min=lo,
                max=hi,
                secret=d.secret,
                value=None if d.secret else res.value,
                is_set=row is not None,
                source=source,
                default=None if d.secret else d.default,
                can_edit=_editable(user, d),
                updated_by_name=(
                    names.get(row.updated_by)
                    if isinstance(row, Setting) and row.updated_by is not None
                    else None
                ),
                updated_at=row.updated_at if row is not None else None,
            )
        )
    return items


async def list_items(
    db: AsyncSession, user: User, level: str, school_id: int | None, branch_id: int | None
) -> list[SettingItem]:
    defs = [d for d in defs_for_level(level) if _viewable(user, d)]
    if not defs:
        raise _forbidden()
    target = await _target(db, user, level, school_id, branch_id)
    return await _items(db, user, target, defs)


# ---------------------------------------------------------------- writes


async def put_value(
    db: AsyncSession,
    user: User,
    level: str,
    key: str,
    raw: Any,
    school_id: int | None,
    branch_id: int | None,
) -> SettingItem:
    d = _find_def(level, key)
    if not _viewable(user, d) or not _editable(user, d):
        raise _forbidden()
    target = await _target(db, user, level, school_id, branch_id)
    if raw is None or (isinstance(raw, str) and raw.strip() == "" and d.type != "bool"):
        return await _reset(db, user, d, target)

    pair = _PAIRS.get(d.key)
    rows = await _load_rows(db, target.ctx, _closure([d.key, *([pair[0]] if pair else [])]))
    lo, hi = _bounds(d, rows)
    value = _coerce(d, raw, lo, hi)
    if pair is not None:
        other = int(_resolve_def(REGISTRY[pair[0]], rows).value)
        if (pair[1] and value > other) or (not pair[1] and value < other):
            raise _invalid(f"{d.label}: the lowest limit cannot be above the highest")
    stored: Any = value
    if d.secret:
        try:
            stored = crypto.encrypt(value)
        except crypto.SecretsUnavailableError:
            raise _err(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Secret storage is not configured on the server",
                "secrets_unavailable",
            ) from None
    await _upsert(db, user, d, target, stored)
    return (await _items(db, user, target, [d]))[0]


async def _upsert(db: AsyncSession, user: User, d: SettingDef, target: Target, stored: Any) -> None:
    now = utcnow()
    for attempt in (1, 2):
        if d.level == "user":
            pref = await db.scalar(
                select(UserPreference).where(
                    UserPreference.user_id == user.id, UserPreference.key == d.key
                )
            )
            if pref is None:
                db.add(UserPreference(user_id=user.id, key=d.key, value=stored, updated_at=now))
            else:
                pref.value = stored
                pref.updated_at = now
        else:
            row = await db.scalar(
                select(Setting).where(Setting.scope == target.scope, Setting.key == d.key)
            )
            if row is None:
                db.add(
                    Setting(
                        level=d.level,
                        school_id=target.school_id if d.level != "platform" else None,
                        branch_id=target.branch_id if d.level == "branch" else None,
                        scope=target.scope,
                        key=d.key,
                        value=stored,
                        is_secret=d.secret,
                        updated_by=user.id,
                        updated_at=now,
                    )
                )
            else:
                row.value = stored
                row.is_secret = d.secret
                row.updated_by = user.id
                row.updated_at = now
        try:
            await db.commit()
            return
        except IntegrityError:
            await db.rollback()  # a concurrent first write; retry as an update once
            if attempt == 2:
                raise


async def _reset(db: AsyncSession, user: User, d: SettingDef, target: Target) -> SettingItem:
    await _delete_row(db, user, d, target)
    await db.commit()
    return (await _items(db, user, target, [d]))[0]


async def _delete_row(db: AsyncSession, user: User, d: SettingDef, target: Target) -> None:
    if d.level == "user":
        pref = await db.scalar(
            select(UserPreference).where(
                UserPreference.user_id == user.id, UserPreference.key == d.key
            )
        )
        if pref is not None:
            await db.delete(pref)
        return
    row = await db.scalar(
        select(Setting).where(Setting.scope == target.scope, Setting.key == d.key)
    )
    if row is not None:
        await db.delete(row)


async def reset_value(
    db: AsyncSession,
    user: User,
    level: str,
    key: str,
    school_id: int | None,
    branch_id: int | None,
) -> None:
    d = _find_def(level, key)
    if not _viewable(user, d) or not _editable(user, d):
        raise _forbidden()
    target = await _target(db, user, level, school_id, branch_id)
    await _delete_row(db, user, d, target)
    await db.commit()


async def set_school_value(
    db: AsyncSession, actor: User, school_id: int, key: str, value: int
) -> None:
    """Write a school setting for another module (the school profile page) with full validation.

    `actor` must be the school's owner or a platform admin; callers have already checked that.
    """
    d = _find_def("school", key)
    target = Target("school", school_id)
    rows = await _load_rows(db, target.ctx, _closure([key]))
    lo, hi = _bounds(d, rows)
    await _upsert(db, actor, d, target, _coerce(d, value, lo, hi))


# --------------------------------------------------------------- levels


async def levels(db: AsyncSession, user: User) -> LevelsOut:
    admin = user.role == Role.SUPER_ADMIN
    out: list[LevelInfo] = []
    if admin:
        out.append(LevelInfo(level="platform", can_edit=True, requires=None))
        out.append(LevelInfo(level="school", can_edit=True, requires="school"))
        out.append(LevelInfo(level="branch", can_edit=True, requires="branch"))
    else:
        if user.school_id is not None:
            school_defs = defs_for_level("school")
            if any(user.role in d.view_roles for d in school_defs):
                out.append(
                    LevelInfo(
                        level="school",
                        can_edit=any(user.role in d.edit_roles for d in school_defs),
                        requires=None,
                    )
                )
            if user.role == Role.SCHOOL_OWNER:
                out.append(LevelInfo(level="branch", can_edit=True, requires="branch"))
            elif user.role in _BRANCH_LEVEL_ROLES and user.branch_id is not None:
                branch_defs = defs_for_level("branch")
                out.append(
                    LevelInfo(
                        level="branch",
                        can_edit=any(user.role in d.edit_roles for d in branch_defs),
                        requires=None,
                    )
                )
    out.append(LevelInfo(level="user", can_edit=True, requires=None))
    if admin or user.school_id is None:
        features = {f: True for f in FEATURES}
    else:
        features = await school_features(db, user.school_id)
    return LevelsOut(levels=out, features=features)


# ------------------------------------------------------ integration test


async def check_integration(
    db: AsyncSession, user: User, name: str, school_id: int | None
) -> IntegrationTestResult:
    d = REGISTRY[f"integrations.{name}.enabled"]
    if not _viewable(user, d) or not _editable(user, d):
        raise _forbidden()
    target = await _target(db, user, "school", school_id, None)
    keys = [f"integrations.{name}.{part}" for part in INTEGRATIONS[name]]
    rows = await _load_rows(db, target.ctx, set(keys))
    missing = []
    for k in keys:
        res = _effective(REGISTRY[k], rows)
        if res.value is None or res.value == "":
            missing.append(REGISTRY[k].label)
    if missing:
        return IntegrationTestResult(ok=False, detail="Missing: " + ", ".join(missing))
    # The adapters arrive in phase 11; no network call is made here.
    return IntegrationTestResult(ok=False, detail="Adapter not installed yet")

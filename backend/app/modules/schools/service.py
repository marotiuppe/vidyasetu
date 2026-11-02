"""School helpers: logo storage, image normalisation and logo_url computation."""

import io
import warnings
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.modules.schools.models import School, SchoolLogo
from app.modules.schools.schemas import SchoolOut
from app.modules.users.models import Role, User

MAX_UPLOAD_BYTES = 1_000_000
MAX_SOURCE_PIXELS = 4000  # per side
LOGO_BOX = 512
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
_FORMATS = ["PNG", "JPEG", "WEBP"]


def _invalid() -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image")


def normalise_logo(raw: bytes) -> bytes:
    """Decode untrusted bytes and re-encode as a metadata-free RGBA PNG within 512x512."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(raw), formats=_FORMATS)
            width, height = probe.size
            if width < 1 or height < 1:
                raise _invalid()
            if width > MAX_SOURCE_PIXELS or height > MAX_SOURCE_PIXELS:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Image too large (max {MAX_SOURCE_PIXELS}x{MAX_SOURCE_PIXELS} pixels)",
                )
            probe.verify()
            img = Image.open(io.BytesIO(raw), formats=_FORMATS)
            img.seek(0)  # first frame only
            img.load()
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA")
            img.thumbnail((LOGO_BOX, LOGO_BOX), Image.Resampling.LANCZOS)  # never upscales
            out = io.BytesIO()
            img.save(out, format="PNG", optimize=True)  # no metadata is carried over
            return out.getvalue()
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        ValueError,
        EOFError,
    ):
        raise _invalid() from None


async def read_capped_body(request: Request) -> bytes:
    """Read the request body, refusing anything over the cap without trusting Content-Length."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE, detail="Logo must be at most 1 MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite drops tzinfo


def logo_url(school_id: int, updated_at: datetime) -> str:
    return f"/api/v1/schools/{school_id}/logo?v={int(_aware(updated_at).timestamp())}"


async def logo_versions(db: AsyncSession, ids: Iterable[int]) -> dict[int, datetime]:
    """One query: school_id -> logo updated_at for the schools that have a logo."""
    id_list = list(ids)
    if not id_list:
        return {}
    rows = await db.execute(
        select(SchoolLogo.school_id, SchoolLogo.updated_at).where(SchoolLogo.school_id.in_(id_list))
    )
    return {sid: ts for sid, ts in rows}


async def schools_out(db: AsyncSession, schools: Iterable[School]) -> list[SchoolOut]:
    items = list(schools)
    versions = await logo_versions(db, (s.id for s in items))
    result = []
    for s in items:
        out = SchoolOut.model_validate(s)
        if s.id in versions:
            out.logo_url = logo_url(s.id, versions[s.id])
        result.append(out)
    return result


async def school_out(db: AsyncSession, school: School) -> SchoolOut:
    return (await schools_out(db, [school]))[0]


def can_manage_logo(user: User, school_id: int) -> bool:
    return user.role == Role.SUPER_ADMIN or (
        user.role == Role.SCHOOL_OWNER and user.school_id == school_id
    )


async def set_logo(db: AsyncSession, school_id: int, png: bytes) -> None:
    logo = await db.get(SchoolLogo, school_id)
    if logo is None:
        db.add(SchoolLogo(school_id=school_id, content_type="image/png", data=png))
    else:
        logo.data = png
        logo.content_type = "image/png"
        logo.updated_at = utcnow()
    await db.commit()


async def delete_logo(db: AsyncSession, school_id: int) -> None:
    logo = await db.get(SchoolLogo, school_id)
    if logo is not None:
        await db.delete(logo)
        await db.commit()

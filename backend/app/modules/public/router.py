from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.core.deps import DbSession
from app.modules.public import service
from app.modules.public.schemas import LegalInfo

PUBLIC_CACHE = "public, max-age=300"
TEXT_CACHE = "public, max-age=3600"

router = APIRouter(prefix="/public", tags=["public"])

# Served outside /api/v1 (mounted at the site root in main.py, before the SPA mount).
site_router = APIRouter(tags=["public"], include_in_schema=False)


@router.get("/legal", response_model=LegalInfo)
async def get_legal_info(
    response: Response,
    db: DbSession,
    school: Annotated[str | None, Query(max_length=50, pattern=r"^[A-Za-z0-9_-]+$")] = None,
) -> LegalInfo:
    # The global middleware sets no-store on /api paths only when no Cache-Control is present.
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return await service.legal_info(db, school)


@site_router.get("/.well-known/security.txt")
async def security_txt(db: DbSession) -> PlainTextResponse:
    body = await service.security_txt(db)
    if body is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return PlainTextResponse(body, headers={"Cache-Control": TEXT_CACHE})


@site_router.get("/robots.txt")
async def robots() -> PlainTextResponse:
    return PlainTextResponse(service.robots_txt(), headers={"Cache-Control": TEXT_CACHE})

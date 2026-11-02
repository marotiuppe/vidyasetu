from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import PlainTextResponse

from app.modules.public import service
from app.modules.public.schemas import LegalInfo

PUBLIC_CACHE = "public, max-age=300"
TEXT_CACHE = "public, max-age=3600"

router = APIRouter(prefix="/public", tags=["public"])

# Served outside /api/v1 (mounted at the site root in main.py, before the SPA mount).
site_router = APIRouter(tags=["public"], include_in_schema=False)


@router.get("/legal", response_model=LegalInfo)
async def get_legal_info(response: Response) -> LegalInfo:
    # The global middleware sets no-store on /api paths only when no Cache-Control is present.
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return service.legal_info()


@site_router.get("/.well-known/security.txt")
async def security_txt() -> PlainTextResponse:
    body = service.security_txt()
    if body is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return PlainTextResponse(body, headers={"Cache-Control": TEXT_CACHE})


@site_router.get("/robots.txt")
async def robots() -> PlainTextResponse:
    return PlainTextResponse(service.robots_txt(), headers={"Cache-Control": TEXT_CACHE})

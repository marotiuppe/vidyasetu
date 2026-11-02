from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.core.config import get_settings
from app.core.errors import IdentityInUse
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.academics.router import router as academics_router
from app.modules.attendance.router import router as attendance_router
from app.modules.auth.router import router as auth_router
from app.modules.branches.router import router as branches_router
from app.modules.fees.router import router as fees_router
from app.modules.notices.router import router as notices_router
from app.modules.schools.router import router as schools_router
from app.modules.students.router import router as students_router
from app.modules.users.identity import suggest_username
from app.modules.users.models import Role, User
from app.modules.users.router import router as users_router

settings = get_settings()


async def _seed_super_admin() -> None:
    """Optionally create the first platform admin from env vars (only if no users exist)."""
    if not (settings.first_superadmin_email and settings.first_superadmin_password):
        return
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).limit(1)) is not None:
            return
        email = settings.first_superadmin_email.lower()
        db.add(
            User(
                username=suggest_username(email),
                email=email,
                full_name="Platform Admin",
                password_hash=hash_password(settings.first_superadmin_password),
                role=Role.SUPER_ADMIN,
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _seed_super_admin()
    yield


app = FastAPI(
    title="School Management System",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)


@app.exception_handler(IdentityInUse)
async def _identity_in_use(_: Request, exc: IdentityInUse) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.detail, "code": exc.code})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(auth_router)
api.include_router(schools_router)
api.include_router(branches_router)
api.include_router(users_router)
api.include_router(academics_router)
api.include_router(students_router)
api.include_router(attendance_router)
api.include_router(notices_router)
api.include_router(fees_router)
app.include_router(api)


@app.get("/api/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


class SPAStaticFiles(StaticFiles):
    """Serve the built Angular app; unknown non-API paths fall back to index.html."""

    async def get_response(self, path: str, scope: Scope):  # type: ignore[no-untyped-def]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api"):
                return FileResponse(settings.frontend_dist / "index.html")
            raise


if settings.frontend_dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=settings.frontend_dist, html=True), name="spa")

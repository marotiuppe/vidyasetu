from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
INSECURE_SECRET = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    environment: str = "development"
    secret_key: str = INSECURE_SECRET
    database_url: str = "sqlite+aiosqlite:///./sms.db"
    allowed_origins: list[str] = ["http://localhost:4200"]
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    # Optional: create the first platform super admin on startup if no users exist.
    first_superadmin_email: str | None = None
    first_superadmin_password: str | None = None

    frontend_dist: Path = REPO_ROOT / "frontend" / "dist" / "frontend" / "browser"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # Render provides postgres:// or postgresql:// URLs; SQLAlchemy async needs asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix) :]
        return v

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == INSECURE_SECRET:
            raise ValueError("SECRET_KEY must be set in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

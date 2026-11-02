from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
INSECURE_SECRET = "change-me"
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    environment: str = "development"
    secret_key: str = INSECURE_SECRET
    database_url: str = "sqlite+aiosqlite:///./sms.db"
    allowed_origins: list[str] = ["http://localhost:4200"]
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    # Host header allow-list (TrustedHostMiddleware). Must be set without "*" in production.
    trusted_hosts: list[str] = ["*"]
    # Largest accepted request body, in bytes.
    max_body_bytes: int = Field(default=12_000_000, ge=1024)
    # Take the client IP from the last X-Forwarded-For entry (only behind a trusted proxy).
    trust_proxy_headers: bool = False

    # Account lockout defaults, used for platform accounts and as the start value for new schools.
    login_max_attempts_default: int = Field(default=3, ge=3, le=10)
    login_lockout_minutes_default: int = Field(default=60, ge=5, le=1440)

    # Requests per minute per client IP.
    rate_limit_login_per_minute: int = Field(default=10, ge=1)
    rate_limit_refresh_per_minute: int = Field(default=30, ge=1)
    rate_limit_change_password_per_minute: int = Field(default=10, ge=1)
    rate_limit_api_per_minute: int = Field(default=300, ge=1)

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
    def _production_guards(self) -> "Settings":
        if not self.is_production:
            return self
        problems: list[str] = []
        weak_secret = (
            self.secret_key == INSECURE_SECRET
            or len(self.secret_key) < MIN_PRODUCTION_SECRET_LENGTH
        )
        if weak_secret:
            problems.append(
                f"SECRET_KEY must be a random value of at least {MIN_PRODUCTION_SECRET_LENGTH} "
                "characters in production"
            )
        if "*" in self.allowed_origins:
            problems.append("ALLOWED_ORIGINS must not contain '*' in production")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            problems.append("TRUSTED_HOSTS must list your host names (not '*') in production")
        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

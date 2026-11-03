from datetime import date
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
    # Refresh-token lifetime of a session without "keep me signed in" (server side and in the
    # cookie's life). Rotation keeps the same policy.
    short_session_hours: int = Field(default=12, ge=1, le=72)
    # Fallback for "keep me signed in" days, used when the school has not chosen a value
    # (school setting security.remember_me_days, capped by the platform limit).
    refresh_token_days: int = Field(default=14, ge=1, le=365)

    # Host header allow-list (TrustedHostMiddleware). Must be set without "*" in production.
    trusted_hosts: list[str] = ["*"]
    # Largest accepted request body, in bytes.
    max_body_bytes: int = Field(default=12_000_000, ge=1024)
    # Key that protects secret settings (SMS, SMTP, payment keys) stored in the database.
    # Development falls back to SECRET_KEY; production refuses to store secrets without it.
    settings_encryption_key: str | None = None
    # Take the client IP from the last X-Forwarded-For entry (only behind a trusted proxy).
    trust_proxy_headers: bool = False

    # Account lockout defaults, used for platform accounts and as the start value for new schools.
    login_max_attempts_default: int = Field(default=3, ge=3, le=10)
    login_lockout_minutes_default: int = Field(default=60, ge=5, le=1440)

    # Requests per minute per client IP.
    # A whole school often signs in from one NAT address, so the default is generous. Lockout per
    # account (login_max_attempts) is what protects individual accounts.
    rate_limit_login_per_minute: int = Field(default=30, ge=1)
    rate_limit_refresh_per_minute: int = Field(default=30, ge=1)
    rate_limit_change_password_per_minute: int = Field(default=10, ge=1)
    rate_limit_mfa_per_minute: int = Field(default=10, ge=1)
    rate_limit_export_per_minute: int = Field(default=5, ge=1)
    # Public online admission form: per client IP (applications are never shown back).
    rate_limit_public_apply_per_minute: int = Field(default=10, ge=1)
    rate_limit_api_per_minute: int = Field(default=300, ge=1)

    # Optional: create the first platform super admin on startup if no users exist.
    first_superadmin_email: str | None = None
    first_superadmin_password: str | None = None

    # Legal and contact details (phase 5.5). All optional: empty means "not configured yet".
    operator_name: str | None = None
    operator_address: str | None = None
    operator_email: str | None = None
    operator_phone: str | None = None
    grievance_officer_name: str | None = None
    grievance_officer_email: str | None = None
    grievance_officer_phone: str | None = None
    grievance_response_days: int = Field(default=15, ge=1, le=90)
    security_contact_email: str | None = None
    privacy_contact_email: str | None = None
    hosting_region: str | None = None
    # ISO date (YYYY-MM-DD) from which the published policies apply.
    policy_effective_date: str | None = None
    data_retention_note: str | None = None

    frontend_dist: Path = REPO_ROOT / "frontend" / "dist" / "frontend" / "browser"

    @field_validator(
        "operator_name",
        "operator_address",
        "operator_email",
        "operator_phone",
        "grievance_officer_name",
        "grievance_officer_email",
        "grievance_officer_phone",
        "security_contact_email",
        "privacy_contact_email",
        "hosting_region",
        "policy_effective_date",
        "data_retention_note",
        "settings_encryption_key",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        # An empty line in .env (KEY=) means the value is not set.
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @field_validator(
        "operator_email",
        "grievance_officer_email",
        "security_contact_email",
        "privacy_contact_email",
    )
    @classmethod
    def _loose_email(cls, v: str | None) -> str | None:
        # Only a sanity check: something@something.tld, no spaces. Real delivery is not tested here.
        if v is None:
            return None
        local, sep, domain = v.partition("@")
        if not (local and sep and "." in domain and " " not in v and len(v) <= 254):
            raise ValueError("must be an email address")
        return v

    @field_validator("policy_effective_date")
    @classmethod
    def _iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("must be an ISO date (YYYY-MM-DD)") from exc
        return v

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

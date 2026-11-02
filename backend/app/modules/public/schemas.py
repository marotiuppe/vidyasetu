from pydantic import BaseModel


class SiteInfo(BaseModel):
    """Platform-wide text shown to every visitor (set by the platform admin in Settings)."""

    platform_name: str | None
    support_contact: str | None
    announcement_banner: str | None
    maintenance_message: str | None


class LegalInfo(BaseModel):
    """Operator, grievance and contact details shown on the public legal pages.

    Values come from the stored settings with .env as fallback; unset values are null.
    Nothing else is exposed.
    """

    configured: bool
    # Set when a valid `?school=<code>` was given.
    school_name: str | None = None
    operator_name: str | None
    operator_address: str | None
    operator_email: str | None
    operator_phone: str | None
    grievance_officer_name: str | None
    grievance_officer_email: str | None
    grievance_officer_phone: str | None
    grievance_response_days: int
    security_contact_email: str | None
    privacy_contact_email: str | None
    hosting_region: str | None
    policy_effective_date: str | None
    data_retention_note: str | None

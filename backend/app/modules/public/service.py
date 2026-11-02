from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.modules.public.schemas import LegalInfo


def legal_info() -> LegalInfo:
    s = get_settings()
    return LegalInfo(
        # The public pages count as configured once the operator and the grievance contact
        # are known; the other values are optional.
        configured=bool(s.operator_name and s.grievance_officer_email),
        operator_name=s.operator_name,
        operator_address=s.operator_address,
        operator_email=s.operator_email,
        operator_phone=s.operator_phone,
        grievance_officer_name=s.grievance_officer_name,
        grievance_officer_email=s.grievance_officer_email,
        grievance_officer_phone=s.grievance_officer_phone,
        grievance_response_days=s.grievance_response_days,
        security_contact_email=s.security_contact_email,
        privacy_contact_email=s.privacy_contact_email,
        hosting_region=s.hosting_region,
        policy_effective_date=s.policy_effective_date,
        data_retention_note=s.data_retention_note,
    )


def security_txt() -> str | None:
    """RFC 9116 security.txt, or None when no security contact is configured."""
    s = get_settings()
    if not s.security_contact_email:
        return None
    expires = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Canonical is omitted: the public origin is not configured and the Host header is not trusted.
    return (
        f"Contact: mailto:{s.security_contact_email}\n"
        f"Expires: {expires}\n"
        "Preferred-Languages: en, mr\n"
    )


def robots_txt() -> str:
    return "User-agent: *\nDisallow: /api/\n"

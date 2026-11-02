from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.public.schemas import LegalInfo, SiteInfo
from app.modules.schools.models import School
from app.modules.settings import service as settings_service


async def legal_info(db: AsyncSession, school_code: str | None = None) -> LegalInfo:
    """Legal details: school contacts from that school's settings, operator details from the
    platform settings, each falling back to .env. An unknown school code behaves like none."""
    school = None
    if school_code:
        school = await db.scalar(
            select(School).where(School.code == school_code.lower(), School.is_active.is_(True))
        )
    v = await settings_service.legal_values(db, school.id if school is not None else None)
    return LegalInfo(
        # The public pages count as configured once the operator and the grievance contact
        # are known; the other values are optional.
        configured=bool(v["legal.operator_name"] and v["legal.grievance_officer_email"]),
        school_name=school.name if school is not None else None,
        operator_name=v["legal.operator_name"],
        operator_address=v["legal.operator_address"],
        operator_email=v["legal.operator_email"],
        operator_phone=v["legal.operator_phone"],
        grievance_officer_name=v["legal.grievance_officer_name"],
        grievance_officer_email=v["legal.grievance_officer_email"],
        grievance_officer_phone=v["legal.grievance_officer_phone"],
        grievance_response_days=v["legal.grievance_response_days"],
        security_contact_email=v["legal.security_contact_email"],
        privacy_contact_email=v["legal.privacy_contact_email"],
        hosting_region=v["legal.hosting_region"],
        policy_effective_date=v["legal.policy_effective_date"],
        data_retention_note=v["legal.data_retention_note"],
    )


async def site_info(db: AsyncSession) -> SiteInfo:
    """Platform name, support contact, banner and maintenance text (platform settings)."""
    keys = [
        "platform.name",
        "platform.support_contact",
        "platform.announcement_banner",
        "platform.maintenance_message",
    ]
    v = await settings_service.resolve_many(db, keys, settings_service.ctx_for())
    return SiteInfo(
        platform_name=v["platform.name"],
        support_contact=v["platform.support_contact"],
        announcement_banner=v["platform.announcement_banner"],
        maintenance_message=v["platform.maintenance_message"],
    )


async def security_txt(db: AsyncSession) -> str | None:
    """RFC 9116 security.txt, or None when no security contact is configured."""
    contact = await settings_service.get_str(db, "legal.security_contact_email")
    if not contact:
        return None
    expires = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Canonical is omitted: the public origin is not configured and the Host header is not trusted.
    return (
        f"Contact: mailto:{contact}\n"
        f"Expires: {expires}\n"
        "Preferred-Languages: en, mr\n"
    )


def robots_txt() -> str:
    return "User-agent: *\nDisallow: /api/\n"

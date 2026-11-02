from pydantic import BaseModel


class LegalInfo(BaseModel):
    """Operator, grievance and contact details shown on the public legal pages.

    Every value comes from settings (.env); unset values are null. Nothing else is exposed.
    """

    configured: bool
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

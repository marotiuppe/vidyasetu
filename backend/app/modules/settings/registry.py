"""Typed registry of every setting. The Settings page is built from this list.

Later phases register their own settings here instead of adding env variables or new pages.
Lookup order for a value: user > branch > school > platform > env fallback > code default.
"""

from dataclasses import dataclass, field
from typing import Any

from app.modules.users.models import Role

LEVELS = ("platform", "school", "branch", "user")
TYPES = ("string", "text", "int", "bool", "choice", "date", "email", "time", "secret")

_SUPER = frozenset({Role.SUPER_ADMIN})
_OWNER = frozenset({Role.SCHOOL_OWNER})
_OWNER_MGMT = frozenset({Role.SCHOOL_OWNER, Role.MANAGEMENT})
_SCHOOL_VIEW = frozenset({Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER})
_BRANCH_EDIT = frozenset({Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER})
_BRANCH_VIEW = frozenset(
    {
        Role.SCHOOL_OWNER,
        Role.MANAGEMENT,
        Role.HEADMASTER,
        Role.TEACHER,
        Role.ACCOUNTANT,
        Role.CLERK,
    }
)
_EVERYONE = frozenset(Role)

DAYS_PATTERN = r"^(mon|tue|wed|thu|fri|sat|sun)(,(mon|tue|wed|thu|fri|sat|sun))*$"
NOTIFY_CHOICES = ("off", "app", "sms", "whatsapp", "email")
FEATURES = (
    "students",
    "attendance",
    "notices",
    "fees",
    "exams",
    "timetable",
    "staff",
    "extras",
    "admissions",
)


@dataclass(frozen=True)
class SettingDef:
    key: str
    level: str
    type: str
    default: Any
    group: str
    label: str
    help: str
    edit_roles: frozenset[Role]
    view_roles: frozenset[Role]
    min: int | None = None
    max: int | None = None
    choices: tuple[str, ...] = ()
    secret: bool = False
    # Attribute on core Settings (.env) used when no stored value exists.
    env: str | None = None
    # Another key whose value is used when this one has no stored value.
    inherit: str | None = None
    # Keys of platform limits that bound this value: (minimum key, maximum key).
    bounded_by: tuple[str | None, str | None] = (None, None)
    pattern: str | None = None
    max_len: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


REGISTRY: dict[str, SettingDef] = {}


def _add(d: SettingDef) -> None:
    assert d.key not in REGISTRY, d.key
    assert d.level in LEVELS and d.type in TYPES, d.key
    REGISTRY[d.key] = d


def _platform(key: str, type_: str, group: str, label: str, help_: str, default: Any = None,
              **kw: Any) -> None:
    _add(SettingDef(key, "platform", type_, default, group, label, help_, _SUPER, _SUPER, **kw))


def _school(key: str, type_: str, group: str, label: str, help_: str, default: Any = None,
            edit: frozenset[Role] = _OWNER, **kw: Any) -> None:
    _add(SettingDef(key, "school", type_, default, group, label, help_, edit, _SCHOOL_VIEW, **kw))


# ---- platform ----
G = "Operator and legal"
_platform("legal.operator_name", "string", G, "Operator name",
          "Legal name of the organisation that runs this platform.", env="operator_name",
          max_len=200)
_platform("legal.operator_address", "text", G, "Operator address",
          "Postal address shown on the legal pages.", env="operator_address", max_len=500)
_platform("legal.operator_email", "email", G, "Operator email",
          "General contact email of the operator.", env="operator_email")
_platform("legal.operator_phone", "string", G, "Operator phone",
          "General contact phone of the operator.", env="operator_phone", max_len=30)
_platform("legal.security_contact_email", "email", G, "Security contact email",
          "Where security researchers report problems (published in security.txt).",
          env="security_contact_email")
_platform("legal.hosting_region", "string", G, "Hosting region",
          "Where the data is hosted, for example a country or cloud region.",
          env="hosting_region", max_len=100)
_platform("legal.policy_effective_date", "date", G, "Policy effective date",
          "Date from which the published policies apply.", env="policy_effective_date")
_platform("legal.privacy_version", "string", G, "Privacy policy version",
          "Raise this when the privacy policy changes; everyone is asked to accept it again.",
          "1", max_len=20, pattern=r"^[A-Za-z0-9._-]{1,20}$")
_platform("legal.terms_version", "string", G, "Terms of use version",
          "Raise this when the terms change; everyone is asked to accept them again.",
          "1", max_len=20, pattern=r"^[A-Za-z0-9._-]{1,20}$")
G = "Security"
_platform("security.mfa_required_super_admin", "bool", G, "Two-factor for platform admins",
          "Platform admins must set up two-factor sign-in before using the app.", True)
G = "Platform"
_platform("platform.name", "string", G, "Platform name", "Product name shown to visitors.",
          max_len=100)
_platform("platform.support_contact", "string", G, "Support contact",
          "Email or phone that schools can use for help.", max_len=200)
_platform("platform.announcement_banner", "text", G, "Announcement banner",
          "Optional message shown to all users. Leave empty for none.", max_len=500)
_platform("platform.maintenance_message", "text", G, "Maintenance message",
          "Optional notice about planned maintenance.", max_len=500)
G = "Limits for schools"
_platform("limits.lockout_attempts_min", "int", G, "Lowest allowed failed attempts",
          "Schools may not set fewer failed sign-in attempts than this.", 3, min=3, max=10)
_platform("limits.lockout_attempts_max", "int", G, "Highest allowed failed attempts",
          "Schools may not allow more failed sign-in attempts than this.", 10, min=3, max=10)
_platform("limits.lockout_minutes_min", "int", G, "Shortest lockout (minutes)",
          "Schools may not lock accounts for less time than this.", 5, min=5, max=1440)
_platform("limits.lockout_minutes_max", "int", G, "Longest lockout (minutes)",
          "Schools may not lock accounts for longer than this.", 1440, min=5, max=1440)
_platform("limits.password_min_length", "int", G, "Minimum password length",
          "Schools may require longer passwords, never shorter than this (and never below 10).",
          10, min=10, max=64)
_platform("limits.remember_me_max_days", "int", G, "Longest remember-me (days)",
          "Schools may not keep people signed in for longer than this.", 30, min=1, max=365)
G = "Defaults for new schools"
_platform("defaults.language", "choice", G, "Default language",
          "Language used when a school has not chosen one.", "en", choices=("en", "mr"))
_platform("defaults.board", "string", G, "Default board",
          "Board suggested for new schools.", "CBSE", max_len=50)

# ---- school ----
G = "Legal contacts"
_school("legal.grievance_officer_name", "string", G, "Grievance officer name",
        "Person who handles complaints about personal data.", env="grievance_officer_name",
        max_len=200)
_school("legal.grievance_officer_email", "email", G, "Grievance officer email",
        "Email for complaints about personal data.", env="grievance_officer_email")
_school("legal.grievance_officer_phone", "string", G, "Grievance officer phone",
        "Phone of the grievance officer.", env="grievance_officer_phone", max_len=30)
_school("legal.grievance_response_days", "int", G, "Grievance response time (days)",
        "How many days the school takes to answer a complaint.", 15, env="grievance_response_days",
        min=1, max=90)
_school("legal.privacy_contact_email", "email", G, "Privacy contact email",
        "Email for privacy questions.", env="privacy_contact_email")
_school("legal.data_retention_note", "text", G, "Data retention note",
        "Plain-language note on how long records are kept.", env="data_retention_note",
        max_len=2000)
G = "Security"
_school("security.login_max_attempts", "int", G, "Failed sign-ins before lockout",
        "An account is locked after this many wrong passwords in a row.", 3,
        env="login_max_attempts_default", min=3, max=10,
        bounded_by=("limits.lockout_attempts_min", "limits.lockout_attempts_max"))
_school("security.login_lockout_minutes", "int", G, "Lockout time (minutes)",
        "How long a locked account stays locked.", 60, env="login_lockout_minutes_default",
        min=5, max=1440, bounded_by=("limits.lockout_minutes_min", "limits.lockout_minutes_max"))
_school("security.password_min_length", "int", G, "Minimum password length",
        "New passwords must be at least this long (never below 10).", 10, min=10, max=64,
        bounded_by=("limits.password_min_length", None))
_school("security.remember_me_days", "int", G, "Remember-me days",
        "How long 'keep me signed in' lasts. Without it, sessions end after the short session "
        "time set on the server.", 14, env="refresh_token_days", min=1, max=365,
        bounded_by=(None, "limits.remember_me_max_days"))
_school("security.force_password_change_new_accounts", "bool", G, "Force password change",
        "New and reset accounts must choose their own password at first sign-in.", True)
_school("security.mfa_required_school_owner", "bool", G, "Two-factor for school owners",
        "School owners must set up two-factor sign-in. Only a platform admin can switch this off.",
        True, edit=_SUPER)
_school("security.mfa_required_management", "bool", G, "Two-factor for management",
        "Management users must set up two-factor sign-in.", False)
_school("security.mfa_required_headmaster", "bool", G, "Two-factor for headmasters",
        "Headmasters must set up two-factor sign-in.", False)
_school("security.mfa_required_accountant", "bool", G, "Two-factor for accountants",
        "Accountants must set up two-factor sign-in.", False)
G = "Academics"
_school("academic.year_start_month", "int", G, "Academic year start month",
        "Month number (1 to 12) when the academic year starts.", 4, min=1, max=12)
_school("academic.default_language", "choice", G, "Default language",
        "Language for users who have not chosen one.", "en", choices=("en", "mr"),
        inherit="defaults.language")
_school("academic.attendance_edit_days_back", "int", G, "Attendance edit window (days)",
        "How many days back staff may change attendance.", 7, edit=_OWNER_MGMT, min=0, max=365)
_school("academic.attendance_absent_alerts", "bool", G, "Absent alerts",
        "Send an alert to parents when a student is marked absent.", False, edit=_OWNER_MGMT)
_school("academic.notice_default_expiry_days", "int", G, "Notice default expiry (days)",
        "New notices expire after this many days. 0 means no expiry.", 0, edit=_OWNER_MGMT,
        min=0, max=365)
G = "Fees"
_school("fees.receipt_prefix", "string", G, "Receipt prefix",
        "Letters or digits at the start of every receipt number.", "RCT", max_len=10,
        pattern=r"^[A-Za-z0-9]{1,10}$")
_school("fees.receipt_footer", "text", G, "Receipt footer",
        "Optional line printed at the bottom of receipts.", max_len=150)
_school("fees.payment_link_enabled", "bool", G, "Payment link",
        "Allow online payment links when a payment gateway is connected.", True)
G = "Year-end promotion"
_school("promotion.undo_hours", "int", G, "Undo window (hours)",
        "How long after a year-end promotion it can still be undone.", 48,
        min=1, max=720)
G = "Parent and student portal"
_school("portal.parent_sees_fees", "bool", G, "Parents see fees", "Show fees to parents.", True)
_school("portal.parent_sees_marks", "bool", G, "Parents see marks", "Show marks to parents.", True)
_school("portal.parent_sees_attendance", "bool", G, "Parents see attendance",
        "Show attendance to parents.", True)
_school("portal.student_logins_enabled", "bool", G, "Student logins",
        "Allow students to have their own logins.", True)
G = "Students and identifiers"
_school("students.gov_ids_enabled", "bool", G, "Store PEN and APAAR IDs",
        "Allow staff to record the PEN and APAAR IDs of students. Aadhaar numbers are never "
        "stored.", False)
G = "Admissions"
_school("admissions.online_form_enabled", "bool", G, "Online admission form",
        "Let families apply through the public admission form for this school.", False)
G = "Data"
_school("data.retention_days", "int", G, "Retention (days)",
        "Days to keep records after a student leaves. 0 means keep until deleted.", 0,
        min=0, max=3650)

G = "SMS"
_school("integrations.sms.enabled", "bool", G, "SMS enabled", "Switch SMS alerts on.", False)
_school("integrations.sms.provider", "string", G, "SMS provider", "Name of the SMS provider.",
        max_len=50)
_school("integrations.sms.sender_id", "string", G, "SMS sender id", "Registered sender id.",
        max_len=20)
_school("integrations.sms.api_key", "secret", G, "SMS API key", "Key from the SMS provider.",
        secret=True)
_school("integrations.sms.dlt_entity_id", "string", G, "DLT entity id",
        "Registered DLT entity id (India).", max_len=50)
G = "WhatsApp"
_school("integrations.whatsapp.enabled", "bool", G, "WhatsApp enabled",
        "Switch WhatsApp messages on.", False)
_school("integrations.whatsapp.phone_id", "string", G, "WhatsApp phone id",
        "Phone number id from the WhatsApp business account.", max_len=50)
_school("integrations.whatsapp.token", "secret", G, "WhatsApp token", "Access token.",
        secret=True)
G = "Email (SMTP)"
_school("integrations.smtp.enabled", "bool", G, "Email enabled", "Switch email on.", False)
_school("integrations.smtp.host", "string", G, "SMTP host", "Mail server host name.", max_len=200)
_school("integrations.smtp.port", "int", G, "SMTP port", "Mail server port.", 587,
        min=1, max=65535)
_school("integrations.smtp.user", "string", G, "SMTP user", "Mail server user name.",
        max_len=200)
_school("integrations.smtp.password", "secret", G, "SMTP password", "Mail server password.",
        secret=True)
G = "Razorpay"
_school("integrations.razorpay.enabled", "bool", G, "Razorpay enabled",
        "Switch online payments on.", False)
_school("integrations.razorpay.key_id", "string", G, "Razorpay key id", "Public key id.",
        max_len=100)
_school("integrations.razorpay.key_secret", "secret", G, "Razorpay key secret", "Secret key.",
        secret=True)
G = "File storage"
_school("integrations.storage.enabled", "bool", G, "Storage enabled",
        "Switch external file storage on.", False)
_school("integrations.storage.bucket", "string", G, "Bucket", "Bucket name.", max_len=200)
_school("integrations.storage.key", "string", G, "Access key", "Access key id.", max_len=200)
_school("integrations.storage.secret", "secret", G, "Secret key", "Secret access key.",
        secret=True)

G = "Modules"
for _name in FEATURES:
    _school(f"feature.{_name}", "bool", G, f"Module: {_name}",
            f"Switch the {_name} module on or off for this school.", True, edit=_SUPER)

# ---- branch ----
G = "Branch"
for _d in (
    SettingDef("branch.working_days", "branch", "string", "mon,tue,wed,thu,fri,sat", G,
               "Working days", "Comma-separated days, for example mon,tue,wed,thu,fri.",
               _BRANCH_EDIT, _BRANCH_VIEW, pattern=DAYS_PATTERN, max_len=40),
    SettingDef("branch.start_time", "branch", "time", None, G, "Start time",
               "When the school day starts (HH:MM).", _BRANCH_EDIT, _BRANCH_VIEW),
    SettingDef("branch.end_time", "branch", "time", None, G, "End time",
               "When the school day ends (HH:MM).", _BRANCH_EDIT, _BRANCH_VIEW),
    SettingDef("branch.contact", "branch", "string", None, G, "Contact",
               "Headmaster or management contact for this branch.", _BRANCH_EDIT, _BRANCH_VIEW,
               max_len=200),
):
    _add(_d)

# ---- user ----
G = "Personal"
_add(SettingDef("user.language", "user", "choice", "en", G, "Language",
                "Language of the app.", _EVERYONE, _EVERYONE, choices=("en", "mr"),
                inherit="academic.default_language"))
for _n in ("attendance", "fees", "notices", "results"):
    _add(SettingDef(f"user.notify_{_n}", "user", "choice", "app", G, f"Notify: {_n}",
                    f"How you want to hear about {_n}.", _EVERYONE, _EVERYONE,
                    choices=NOTIFY_CHOICES))
_add(SettingDef("user.display_density", "user", "choice", "comfortable", G, "Display density",
                "Spacing used on screens.", _EVERYONE, _EVERYONE,
                choices=("comfortable", "compact")))

INTEGRATIONS: dict[str, tuple[str, ...]] = {
    "sms": ("provider", "sender_id", "api_key"),
    "whatsapp": ("phone_id", "token"),
    "smtp": ("host", "port", "user", "password"),
    "razorpay": ("key_id", "key_secret"),
    "storage": ("bucket", "key", "secret"),
}


def defs_for_level(level: str) -> list[SettingDef]:
    return [d for d in REGISTRY.values() if d.level == level]

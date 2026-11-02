import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, as_utc, utcnow


class Role(enum.StrEnum):
    SUPER_ADMIN = "super_admin"  # platform, all schools
    SCHOOL_OWNER = "school_owner"  # all branches of one school
    MANAGEMENT = "management"  # one branch
    HEADMASTER = "headmaster"  # one branch
    TEACHER = "teacher"
    ACCOUNTANT = "accountant"
    CLERK = "clerk"
    PARENT = "parent"  # school-wide login; sees only own children (can span branches)
    STUDENT = "student"


# Roles that belong to a single branch.
BRANCH_ROLES = {
    Role.MANAGEMENT,
    Role.HEADMASTER,
    Role.TEACHER,
    Role.ACCOUNTANT,
    Role.CLERK,
    Role.STUDENT,
}


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # A mobile number is unique per school (NULLs are allowed many times).
        UniqueConstraint("school_id", "phone", name="uq_users_school_phone"),
        ForeignKeyConstraint(
            ["branch_id", "school_id"], ["branches.id", "branches.school_id"]
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL school_id only for the platform super admin.
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True)
    # NULL branch_id for super admin, school owner and parents.
    branch_id: Mapped[int | None] = mapped_column(index=True)
    # Login handles. Stored lower-case; the username is immutable, email and phone are optional.
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(
            Role,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set for admin-created accounts and resets; cleared when the user changes their password.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # Bumped to invalidate every outstanding access token (password change, reset, deactivation).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Failed sign-ins since the last success or lock; the lock applies until locked_until.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and as_utc(self.locked_until) > utcnow()

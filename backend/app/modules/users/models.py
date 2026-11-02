import enum

from sqlalchemy import Boolean, Enum, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


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
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(
            Role,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

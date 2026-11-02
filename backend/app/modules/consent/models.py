import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Policy(enum.StrEnum):
    PRIVACY = "privacy"
    TERMS = "terms"


class Purpose(enum.StrEnum):
    DATA_PROCESSING = "data_processing"
    COMMUNICATION = "communication"
    PHOTOS = "photos"
    GOVERNMENT_IDS = "government_ids"


class ConsentStatus(enum.StrEnum):
    GRANTED = "granted"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"


class ConsentMethod(enum.StrEnum):
    ONLINE = "online"
    PAPER = "paper"
    IN_PERSON = "in_person"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class PolicyAcceptance(Base):
    """A user accepted one version of a policy (privacy or terms)."""

    __tablename__ = "policy_acceptances"
    __table_args__ = (UniqueConstraint("user_id", "policy", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    policy: Mapped[Policy] = mapped_column(_enum(Policy))
    version: Mapped[str] = mapped_column(String(20))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64))


class GuardianConsent(Base):
    """One consent decision about one student. Append-only: the latest row per purpose wins."""

    __tablename__ = "guardian_consents"
    __table_args__ = (
        ForeignKeyConstraint(["student_id", "branch_id"], ["students.id", "students.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        Index("ix_guardian_consents_student_purpose", "student_id", "purpose", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column()
    student_id: Mapped[int] = mapped_column()
    purpose: Mapped[Purpose] = mapped_column(_enum(Purpose))
    status: Mapped[ConsentStatus] = mapped_column(_enum(ConsentStatus))
    # Set when a parent signed in and decided online; empty for paper and in-person records.
    given_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    method: Mapped[ConsentMethod] = mapped_column(_enum(ConsentMethod))
    note: Mapped[str | None] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

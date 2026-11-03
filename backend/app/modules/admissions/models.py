import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow
from app.modules.students.models import Gender, GuardianRelation


class ApplicationStatus(enum.StrEnum):
    ENQUIRY = "enquiry"
    APPLIED = "applied"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    ENROLLED = "enrolled"


class ApplicationSource(enum.StrEnum):
    ENQUIRY = "enquiry"
    ONLINE = "online"
    WALK_IN = "walk_in"


class DocumentType(enum.StrEnum):
    PDF = "application/pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class AdmissionApplication(TimestampMixin, Base):
    """An enquiry or application for a seat in one branch; becomes a student on conversion."""

    __tablename__ = "admission_applications"
    __table_args__ = (
        UniqueConstraint("id", "school_id", name="uq_admission_applications_id_school"),
        UniqueConstraint("student_id", name="uq_admission_applications_student_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        Index("ix_admission_applications_school_status", "school_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[Gender | None] = mapped_column(_enum(Gender))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    class_id: Mapped[int | None] = mapped_column()
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"))
    guardian_name: Mapped[str] = mapped_column(String(200))
    guardian_phone: Mapped[str] = mapped_column(String(20))
    guardian_email: Mapped[str | None] = mapped_column(String(254))
    guardian_relation: Mapped[GuardianRelation] = mapped_column(_enum(GuardianRelation))
    address: Mapped[str | None] = mapped_column(Text)
    previous_school: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[ApplicationSource] = mapped_column(_enum(ApplicationSource))
    status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus),
        default=ApplicationStatus.ENQUIRY,
        server_default=ApplicationStatus.ENQUIRY.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    # Set when the guardian agreed to the privacy notice on the public form (online only).
    privacy_notice_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    student_id: Mapped[int | None] = mapped_column()
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AdmissionDocument(Base):
    """A scanned document attached to an application (stored in the database, small files only)."""

    __tablename__ = "admission_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "school_id"],
            ["admission_applications.id", "admission_applications.school_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    application_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[DocumentType] = mapped_column(_enum(DocumentType, length=30))
    size_bytes: Mapped[int] = mapped_column()
    data: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

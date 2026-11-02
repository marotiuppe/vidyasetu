import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class RequestType(enum.StrEnum):
    ACCESS = "access"
    CORRECTION = "correction"
    ERASURE = "erasure"


class RequestStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class DataRequest(Base):
    """A data-rights request (access, correction or erasure). A workflow record only: the school
    decides and acts; nothing is deleted automatically."""

    __tablename__ = "data_requests"
    __table_args__ = (
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        Index("ix_data_requests_school_status", "school_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL only for requests by platform admins.
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"))
    # The student's branch (or the requester's) so branch managers see their own requests only.
    branch_id: Mapped[int | None] = mapped_column(index=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[int | None] = mapped_column()
    type: Mapped[RequestType] = mapped_column(_enum(RequestType))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus), default=RequestStatus.OPEN)
    response_note: Mapped[str | None] = mapped_column(Text)
    handled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    due_on: Mapped[date] = mapped_column(Date)

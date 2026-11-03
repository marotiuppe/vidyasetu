import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.students.models import StudentStatus


class PromotionAction(enum.StrEnum):
    PROMOTED = "promoted"
    DETAINED = "detained"
    LEFT = "left"
    PASSED_OUT = "passed_out"
    TRANSFERRED = "transferred"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class PromotionBatch(TimestampMixin, Base):
    """One year-end promotion run. Undo is possible until `undo_until`, once."""

    __tablename__ = "promotion_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    from_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"))
    to_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    undo_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    carry_over: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted: Mapped[int] = mapped_column(Integer, default=0)
    detained: Mapped[int] = mapped_column(Integer, default=0)
    left: Mapped[int] = mapped_column(Integer, default=0)
    passed_out: Mapped[int] = mapped_column(Integer, default=0)
    transferred: Mapped[int] = mapped_column(Integer, default=0)
    carried_invoices: Mapped[int] = mapped_column(Integer, default=0)
    carried_paise: Mapped[int] = mapped_column(BigInteger, default=0)


class PromotionItem(Base):
    """What one batch did to one student. Kept after an undo as history (links are cleared)."""

    __tablename__ = "promotion_items"
    __table_args__ = (
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_batches.id", ondelete="CASCADE"), index=True
    )
    school_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[PromotionAction] = mapped_column(_enum(PromotionAction))
    from_enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("enrollments.id"))
    to_enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("enrollments.id"))
    from_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    to_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    from_status: Mapped[StudentStatus] = mapped_column(_enum(StudentStatus))
    to_status: Mapped[StudentStatus] = mapped_column(_enum(StudentStatus))
    carry_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    carried_paise: Mapped[int] = mapped_column(BigInteger, default=0)

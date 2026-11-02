import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# All money is stored as integer paise (never floats).


class PaymentMethod(enum.StrEnum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK = "bank"
    CHEQUE = "cheque"
    ONLINE = "online"


class PaymentStatus(enum.StrEnum):
    RECEIVED = "received"
    REVERSED = "reversed"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class FeeHead(TimestampMixin, Base):
    """A school-wide kind of fee (tuition, transport, ...)."""

    __tablename__ = "fee_heads"
    __table_args__ = (
        UniqueConstraint("school_id", "name_key"),
        UniqueConstraint("id", "school_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100))  # lower-cased name, for uniqueness
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FeeStructureItem(TimestampMixin, Base):
    """What one class pays for one fee head in one academic year."""

    __tablename__ = "fee_structure_items"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "class_id", "fee_head_id"),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        ForeignKeyConstraint(["fee_head_id", "school_id"], ["fee_heads.id", "fee_heads.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    class_id: Mapped[int] = mapped_column(index=True)
    fee_head_id: Mapped[int] = mapped_column(index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("school_id", "invoice_no"),
        UniqueConstraint("student_id", "academic_year_id", "title"),
        UniqueConstraint("id", "branch_id"),
        UniqueConstraint("id", "student_id"),
        ForeignKeyConstraint(["student_id", "branch_id"], ["students.id", "students.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        Index("ix_invoices_school_branch", "school_id", "branch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column()
    branch_id: Mapped[int] = mapped_column()
    student_id: Mapped[int] = mapped_column(index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    invoice_no: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(100))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    gross_paise: Mapped[int] = mapped_column(BigInteger)
    discount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_reason: Mapped[str | None] = mapped_column(String(200))
    status_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    fee_head_id: Mapped[int | None] = mapped_column(ForeignKey("fee_heads.id"))
    description: Mapped[str] = mapped_column(String(150))
    amount_paise: Mapped[int] = mapped_column(BigInteger)


class Payment(TimestampMixin, Base):
    """A payment against an invoice. Never deleted; a wrong one is reversed."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("school_id", "receipt_no"),
        ForeignKeyConstraint(["invoice_id", "branch_id"], ["invoices.id", "invoices.branch_id"]),
        ForeignKeyConstraint(["invoice_id", "student_id"], ["invoices.id", "invoices.student_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        Index("ix_payments_school_paid_on", "school_id", "paid_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column()
    branch_id: Mapped[int] = mapped_column(index=True)
    invoice_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    receipt_no: Mapped[str] = mapped_column(String(30))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod))
    reference: Mapped[str | None] = mapped_column(String(100))
    paid_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus), default=PaymentStatus.RECEIVED
    )
    reversed_reason: Mapped[str | None] = mapped_column(String(200))
    reversed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Branch(TimestampMixin, Base):
    """A branch of a school (e.g. Primary 1-5, Secondary 6-10)."""

    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("school_id", "code"),
        # Lets other tables use a composite FK (branch_id, school_id) so a row can never
        # point to a branch of a different school.
        UniqueConstraint("id", "school_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50))
    # Timings and management details are entered later through the app.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

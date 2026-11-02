from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class School(TimestampMixin, Base):
    """A tenant. Everything else belongs to exactly one school."""

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    board: Mapped[str] = mapped_column(String(50), default="CBSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

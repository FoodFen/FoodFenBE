"""ORM models for the mascot catalogue (edited with SQL) and which ones users bought."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.mascot import Mascot
from src.infrastructure.db.base import Base


class MascotORM(Base):
    __tablename__ = "mascots"
    __table_args__ = (CheckConstraint("coin_cost >= 0", name="coin_cost"),)

    # The slug is the PK on purpose: the app's artwork registry keys on it, so a UUID would be indirection.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    coin_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def to_domain(self) -> Mascot:
        return Mascot(id=self.id, name=self.name, coin_cost=self.coin_cost)


class UserMascotORM(Base):
    """A purchase. Free mascots get no row."""

    __tablename__ = "user_mascots"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    mascot_id: Mapped[str] = mapped_column(String(32), ForeignKey("mascots.id"), primary_key=True)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

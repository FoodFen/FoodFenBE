"""ORM models for the mascot catalogue (managed by admin), its per-state artwork and which ones users bought."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.mascot import Mascot
from src.domain.enums import MascotState
from src.infrastructure.db.base import Base
from src.infrastructure.db.types import enum_column


class MascotORM(Base):
    __tablename__ = "mascots"
    __table_args__ = (CheckConstraint("coin_cost >= 0", name="coin_cost"),)

    # The slug is the PK on purpose: the app's artwork registry keys on it, so a UUID would be indirection.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    coin_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    body_color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # "#RRGGBB"; NULL = app theme default

    # delete-orphan: the FK's ON DELETE CASCADE isn't enforced everywhere (SQLite tests), the ORM must cover it too.
    images: Mapped[list[MascotImageORM]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    def to_domain(self) -> Mascot:
        return Mascot(
            id=self.id,
            name=self.name,
            coin_cost=self.coin_cost,
            active=self.active,
            images={i.state: i.url for i in self.images},
            body_color=self.body_color,
        )

    @classmethod
    def from_domain(cls, mascot: Mascot) -> MascotORM:
        return cls(
            id=mascot.id,
            name=mascot.name,
            coin_cost=mascot.coin_cost,
            active=mascot.active,
            body_color=mascot.body_color,
            images=[MascotImageORM(state=s, url=u) for s, u in mascot.images.items()],
        )


class MascotImageORM(Base):
    """One image per (mascot, state). `idle` is the base the app falls back to."""

    __tablename__ = "mascot_images"

    mascot_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("mascots.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[MascotState] = mapped_column(enum_column(MascotState, "mascot_state"), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)


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

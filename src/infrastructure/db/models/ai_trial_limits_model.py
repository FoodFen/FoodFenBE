"""The admin-set free AI trial limits. A single row; see ``SQLAlchemyAiTrialRepository.limits``."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class AiTrialLimitsORM(UUIDPrimaryKey, Base):
    __tablename__ = "ai_trial_limits"
    # Bare names: the naming convention prefixes ck_<table>_.
    __table_args__ = (
        CheckConstraint("guest_limit BETWEEN 0 AND 100", name="guest_limit"),
        CheckConstraint("signed_in_limit BETWEEN 0 AND 100", name="signed_in_limit"),
    )

    guest_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    signed_in_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

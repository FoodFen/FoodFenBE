"""Free-trial AI analyses used, per owner (``device:<id>`` or ``user:<id>``) and input method."""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import AiTrialMethod
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class AiTrialUsageORM(UUIDPrimaryKey, Base):
    __tablename__ = "ai_trial_usage"
    __table_args__ = (
        UniqueConstraint("owner_key", "input_method", name="uq_ai_trial_usage_owner_method"),
    )

    # Not a FK: an anonymous device has no user row.
    owner_key: Mapped[str] = mapped_column(String(80), nullable=False)
    input_method: Mapped[AiTrialMethod] = mapped_column(
        enum_column(AiTrialMethod, "ai_trial_method"), nullable=False
    )
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

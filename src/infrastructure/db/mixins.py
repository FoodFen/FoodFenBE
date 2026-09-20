"""Declarative mixins for columns every table repeats."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


# Negative sort_order puts mixin columns before the ones the model declares;
# without it SQLAlchemy appends them, leaving `id` as the last column.
class UUIDPrimaryKey:
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, sort_order=-100)


class IntPrimaryKey:
    """Autoincrement integer PK. Only ``users`` uses this — the front-end contract
    types ``User.id`` as a number. Every other table keeps a UUID PK."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, sort_order=-100)


class UserOwned:
    """FK to ``users.id`` (an integer PK). Rows are deleted with their owner.

    ``declared_attr`` is required here (unlike the plain column above) because a
    ForeignKey object cannot be shared between tables.
    """

    @declared_attr
    @classmethod
    def user_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            sort_order=-90,
        )

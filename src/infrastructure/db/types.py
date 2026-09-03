"""Reusable SQLAlchemy column types."""

from __future__ import annotations

from enum import StrEnum

import sqlalchemy as sa


def enum_column(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    """A VARCHAR column constrained by CHECK to the enum's values.

    ``native_enum=False`` keeps adding a member a code change rather than an
    ``ALTER TYPE`` migration, and ``values_callable`` stores the value
    (``"very_active"``) instead of the member name (``"VERY_ACTIVE"``).
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        # Must be explicit: SQLAlchemy has defaulted this to False since 1.4, so
        # without it the column is a plain VARCHAR with no CHECK at all.
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
        name=name,
    )

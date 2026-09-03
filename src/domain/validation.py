"""Shared invariant checks used by entity ``__post_init__``. Standard library only.

Each helper takes the exception type to raise so an entity can keep its own
error class throughout: ``User`` raises ``InvalidUserAttributeException`` for
every one of its fields, not just the ones it checks inline.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.domain.exceptions import InvalidAttributeException

Number = int | float | Decimal

_Exc = type[InvalidAttributeException]


def require_non_negative(
    value: Number, field: str, exc_type: _Exc = InvalidAttributeException
) -> None:
    if value < 0:
        raise exc_type(f"{field} must not be negative, got {value!r}")


def require_positive(
    value: Number, field: str, exc_type: _Exc = InvalidAttributeException
) -> None:
    if value <= 0:
        raise exc_type(f"{field} must be greater than zero, got {value!r}")


def require_non_empty(
    value: str, field: str, exc_type: _Exc = InvalidAttributeException
) -> str:
    """Return the stripped text, or raise if it is blank."""
    text = (value or "").strip()
    if not text:
        raise exc_type(f"{field} must not be empty")
    return text


def require_not_before(
    later: date,
    earlier: date,
    later_field: str,
    earlier_field: str,
    exc_type: _Exc = InvalidAttributeException,
) -> None:
    if later < earlier:
        raise exc_type(
            f"{later_field} ({later}) must not be before {earlier_field} ({earlier})"
        )

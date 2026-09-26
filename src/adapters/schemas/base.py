"""Shared Pydantic base for the camelCase-over-the-wire contract.

The front end's API contract is camelCase (`accessToken`, `displayName`, ...);
our Python stays snake_case internally. ``alias_generator`` derives the wire
name from the field name so we declare fields once, in Python style, and get
both directions of translation for free: camelCase JSON in, camelCase JSON out
(``populate_by_name`` still accepts snake_case input too, harmlessly).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# Decimal is the correct internal type for money, but has no native JSON
# representation — Pydantic serializes it as a string by default, which
# breaks clients (e.g. Zod) expecting a number. Use this for any money field
# on a response schema so the wire gets a JSON number while Decimal is kept
# everywhere else.
MoneyField = Annotated[Decimal, PlainSerializer(float, return_type=float)]

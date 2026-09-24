"""Input DTO for partial profile updates.

``updates`` carries only the fields the client actually sent (built by the
controller via Pydantic's ``exclude_unset``) — a plain ``dict`` rather than
one optional field per profile attribute, since every one of the 13
editable fields would otherwise need its own sentinel-vs-None handling for
no benefit: the use case only ever needs to know *which* fields to apply,
not carry a fixed shape for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdateUserProfileInputDTO:
    user_id: int
    updates: dict[str, Any]

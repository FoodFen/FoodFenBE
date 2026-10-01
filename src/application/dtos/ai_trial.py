"""Who is calling an AI endpoint. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiCallerDTO:
    # Quota owners: "device:<id>" and/or "user:<id>". Never empty.
    keys: tuple[str, ...]
    is_premium: bool

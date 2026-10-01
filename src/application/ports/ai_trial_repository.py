"""Persistence port for free-trial AI usage. Structural typing via Protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.domain.enums import AiTrialMethod


class AiTrialRepositoryProtocol(Protocol):
    async def used(self, owner_keys: Sequence[str]) -> dict[AiTrialMethod, int]:
        """Trials used per method — the highest count across ``owner_keys``."""
        ...

    async def increment(self, owner_keys: Sequence[str], method: AiTrialMethod) -> None:
        """Add one used trial for ``method`` to every owner key."""
        ...

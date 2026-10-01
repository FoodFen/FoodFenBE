"""Free-trial quota for AI food analysis: ``AI_TRIAL_LIMIT`` successes per input method."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.ports.ai_trial_repository import AiTrialRepositoryProtocol
from src.domain.enums import AiTrialMethod
from src.domain.exceptions import AiTrialExhaustedException

AI_TRIAL_LIMIT = 3


@dataclass
class AiTrialUseCase:
    usage: AiTrialRepositoryProtocol

    async def remaining(self, caller: AiCallerDTO) -> dict[AiTrialMethod, int] | None:
        """Trials left per method, or ``None`` for Premium (unlimited)."""
        if caller.is_premium:
            return None
        used = await self.usage.used(caller.keys)
        return {m: max(0, AI_TRIAL_LIMIT - used.get(m, 0)) for m in AiTrialMethod}

    async def ensure_available(self, caller: AiCallerDTO, method: AiTrialMethod) -> None:
        left = await self.remaining(caller)
        if left is not None and left[method] == 0:
            raise AiTrialExhaustedException(method)

    async def consume(self, caller: AiCallerDTO, method: AiTrialMethod) -> None:
        # ponytail: check-then-consume isn't atomic, so concurrent requests can overshoot the
        # limit by a few. The per-IP limit bounds it; lock the owner rows if it ever matters.
        if not caller.is_premium:
            await self.usage.increment(caller.keys, method)

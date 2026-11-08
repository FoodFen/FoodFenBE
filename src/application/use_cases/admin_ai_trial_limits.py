"""Use cases: admin reads / edits the free AI trial limits. The 0..100 rule lives in ``AiTrialLimits``."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.ai_trial_repository import AiTrialRepositoryProtocol
from src.domain.entities.ai_trial_limits import AiTrialLimits


@dataclass
class GetAiTrialLimitsUseCase:
    usage: AiTrialRepositoryProtocol

    async def execute(self) -> AiTrialLimits:
        return await self.usage.limits()


@dataclass
class UpdateAiTrialLimitsUseCase:
    usage: AiTrialRepositoryProtocol

    async def execute(self, guest: int, signed_in: int) -> AiTrialLimits:
        limits = AiTrialLimits(guest, signed_in)
        await self.usage.save_limits(limits)
        return limits

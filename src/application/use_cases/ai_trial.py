"""Free-trial quota for AI food analysis: successes per input method per day.

A guest gets ``AI_TRIAL_LIMIT_GUEST``, a signed-in free user ``AI_TRIAL_LIMIT_SIGNED_IN``.

A day is a calendar day in Vietnam (UTC+7, no DST), matching the app's diary days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.ports.ai_trial_repository import AiTrialRepositoryProtocol
from src.domain.enums import AiTrialMethod
from src.domain.exceptions import AiTrialExhaustedException

AI_TRIAL_LIMIT_GUEST = 3
AI_TRIAL_LIMIT_SIGNED_IN = 5

_VN = timezone(timedelta(hours=7))


def _now() -> datetime:
    return datetime.now(_VN)


def _today() -> date:
    return _now().astimezone(_VN).date()


@dataclass
class AiTrialUseCase:
    usage: AiTrialRepositoryProtocol

    def limit_for(self, caller: AiCallerDTO) -> int:
        return AI_TRIAL_LIMIT_SIGNED_IN if caller.signed_in else AI_TRIAL_LIMIT_GUEST

    def resets_at(self) -> datetime:
        """The next Vietnam midnight, when every counter starts over."""
        return datetime.combine(_today() + timedelta(days=1), time.min, tzinfo=_VN)

    async def remaining(self, caller: AiCallerDTO) -> dict[AiTrialMethod, int] | None:
        """Trials left today per method, or ``None`` for Premium (unlimited)."""
        if caller.is_premium:
            return None
        used = await self.usage.used(caller.keys, _today())
        limit = self.limit_for(caller)
        return {m: max(0, limit - used.get(m, 0)) for m in AiTrialMethod}

    async def ensure_available(self, caller: AiCallerDTO, method: AiTrialMethod) -> None:
        left = await self.remaining(caller)
        if left is not None and left[method] == 0:
            raise AiTrialExhaustedException(method, self.resets_at())

    async def consume(self, caller: AiCallerDTO, method: AiTrialMethod) -> None:
        # ponytail: check-then-consume isn't atomic, so concurrent requests can overshoot the
        # limit by a few. The per-IP limit bounds it; lock the owner rows if it ever matters.
        if not caller.is_premium:
            await self.usage.increment(caller.keys, method, _today())

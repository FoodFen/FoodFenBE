"""Free AI analyses per input method per day, for guests and signed-in free users. Admin-editable."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import InvalidAiTrialLimitsException

AI_TRIAL_LIMIT_MAX = 100


@dataclass(frozen=True)
class AiTrialLimits:
    guest: int
    signed_in: int

    def __post_init__(self) -> None:
        for field, value in (("guest_limit", self.guest), ("signed_in_limit", self.signed_in)):
            # bool is an int subclass, so `True` would otherwise pass as 1.
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= AI_TRIAL_LIMIT_MAX:
                raise InvalidAiTrialLimitsException(
                    f"{field} must be an integer between 0 and {AI_TRIAL_LIMIT_MAX}, got {value!r}",
                    "limit_out_of_range",
                    field,
                )


DEFAULT_AI_TRIAL_LIMITS = AiTrialLimits(guest=3, signed_in=5)

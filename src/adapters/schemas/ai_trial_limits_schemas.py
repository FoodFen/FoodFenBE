"""HTTP wire models for the admin AI trial limits."""

from __future__ import annotations

from src.adapters.schemas.base import CamelModel
from src.domain.entities.ai_trial_limits import AiTrialLimits


class AiTrialLimitsRequest(CamelModel):
    # No pydantic bounds: the entity enforces 0..100 and answers with a coded 422.
    guest_limit: int
    signed_in_limit: int


class AiTrialLimitsResponse(CamelModel):
    guest_limit: int
    signed_in_limit: int

    @classmethod
    def from_entity(cls, limits: AiTrialLimits) -> AiTrialLimitsResponse:
        return cls(guest_limit=limits.guest, signed_in_limit=limits.signed_in)

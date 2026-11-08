"""AiTrialLimits entity bounds and AiTrialUseCase reading the limits from the repository."""

import pytest

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.use_cases.admin_ai_trial_limits import GetAiTrialLimitsUseCase, UpdateAiTrialLimitsUseCase
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.domain.entities.ai_trial_limits import AiTrialLimits
from src.domain.exceptions import InvalidAiTrialLimitsException


class FakeRepo:
    def __init__(self, limits: AiTrialLimits = AiTrialLimits(3, 5)) -> None:
        self._limits = limits

    async def used(self, owner_keys, day):
        return {}

    async def limits(self) -> AiTrialLimits:
        return self._limits

    async def save_limits(self, limits: AiTrialLimits) -> None:
        self._limits = limits


@pytest.mark.parametrize("value", [0, 100])
def test_limits_accept_the_bounds(value):
    assert AiTrialLimits(value, value) == AiTrialLimits(guest=value, signed_in=value)


@pytest.mark.parametrize("guest, signed_in, field", [(-1, 5, "guest_limit"), (3, 101, "signed_in_limit"), (True, 5, "guest_limit")])
def test_limits_reject_out_of_range_and_bool(guest, signed_in, field):
    with pytest.raises(InvalidAiTrialLimitsException) as exc:
        AiTrialLimits(guest, signed_in)
    assert (exc.value.code, exc.value.field) == ("limit_out_of_range", field)


async def test_limit_for_reads_the_repository():
    trial = AiTrialUseCase(usage=FakeRepo(AiTrialLimits(1, 9)))

    assert await trial.limit_for(AiCallerDTO(keys=("d",), is_premium=False, signed_in=False)) == 1
    assert await trial.limit_for(AiCallerDTO(keys=("u",), is_premium=False, signed_in=True)) == 9


async def test_remaining_uses_the_stored_limit():
    trial = AiTrialUseCase(usage=FakeRepo(AiTrialLimits(0, 2)))

    left = await trial.remaining(AiCallerDTO(keys=("d",), is_premium=False, signed_in=False))

    assert set(left.values()) == {0}


async def test_update_saves_and_get_returns_it():
    repo = FakeRepo()

    assert await UpdateAiTrialLimitsUseCase(repo).execute(7, 8) == AiTrialLimits(7, 8)
    assert await GetAiTrialLimitsUseCase(repo).execute() == AiTrialLimits(7, 8)


async def test_update_rejects_invalid_without_saving():
    repo = FakeRepo()

    with pytest.raises(InvalidAiTrialLimitsException):
        await UpdateAiTrialLimitsUseCase(repo).execute(3, 101)

    assert await repo.limits() == AiTrialLimits(3, 5)

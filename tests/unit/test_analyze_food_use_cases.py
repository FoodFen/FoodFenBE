"""AnalyzeFoodImage/TextUseCase unit tests: fake vision + fake storage. No DB, no real LLM call."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from catalog_foods import make_food

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.application.food_catalog_cache import FoodCatalogCache
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.application.use_cases.analyze_food_image import AnalyzeFoodImageUseCase
from src.application.use_cases.analyze_food_text import AnalyzeFoodTextUseCase
from src.domain.entities.ai_trial_limits import AiTrialLimits
from src.domain.enums import AiTrialMethod

_INGREDIENT = IngredientSuggestionDTO(
    name="pho beef",
    quantity_g=350.0,
    kcal=450,
    carbs_g=50.0,
    protein_g=30.0,
    fat_g=12.0,
    fiber_g=2.0,
    confidence=0.8,
)


class FakeVisionProvider:
    def __init__(self, result: FoodAnalysisDTO) -> None:
        self._result = result
        self.image_calls: list[tuple[bytes, str, str]] = []
        self.text_calls: list[tuple[str, str]] = []
        self.catalogs: list = []  # the `catalog` argument of every call

    async def analyze_image(
        self, image_bytes: bytes, content_type: str, language: str, catalog=None
    ) -> FoodAnalysisDTO:
        self.image_calls.append((image_bytes, content_type, language))
        self.catalogs.append(catalog)
        return self._result

    async def analyze_text(self, description: str, language: str, catalog=None) -> FoodAnalysisDTO:
        self.text_calls.append((description, language))
        self.catalogs.append(catalog)
        return self._result


class FakeCatalogRepo:
    def __init__(self, foods=()) -> None:
        self.foods = list(foods)
        self.reads = 0

    async def list_active(self):
        self.reads += 1
        return self.foods

    async def get_by_slug(self, slug):
        raise AssertionError("not used")


class FakeMisses:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.recorded: list[tuple[list[tuple[str, str]], str]] = []  # (entries, language) per call

    async def record(self, misses, language, at):
        if self.fail:
            raise RuntimeError("db down")
        self.recorded.append((list(misses), language))


def _catalog(foods=(), grounding=True, misses=None) -> dict:
    """The catalog-related use case fields; a fresh cache per use case."""
    return dict(
        catalog=FakeCatalogRepo(foods),
        catalog_cache=FoodCatalogCache(),
        misses=misses or FakeMisses(),
        grounding=grounding,
    )


class FakeTrialUsage:
    """Premium callers never reach it; free-tier counting is covered by tests/api."""

    async def used(self, owner_keys):
        raise AssertionError("premium must not read trial usage")

    async def increment(self, owner_keys, method):
        raise AssertionError("premium must not consume a trial")


_TRIAL = AiTrialUseCase(usage=FakeTrialUsage())
_CALLER = AiCallerDTO(keys=("user:1",), is_premium=True, signed_in=True)


class FakeImageStorage:
    def __init__(self, url: str = "https://cdn.example/meal.jpg") -> None:
        self.url = url
        self.uploads: list[tuple[bytes, str]] = []

    async def upload(self, data: bytes, content_type: str) -> str:
        self.uploads.append((data, content_type))
        return self.url


async def test_analyze_image_uploads_and_sets_image_url():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    storage = FakeImageStorage()
    uc = AnalyzeFoodImageUseCase(vision=vision, images=storage, trial=_TRIAL, **_catalog())

    result = await uc.execute(_CALLER, b"fake-bytes", "image/jpeg", "en")

    assert result.meal_name == "Pho"
    assert result.ingredients == [_INGREDIENT]
    assert result.image_url == storage.url
    assert vision.image_calls == [(b"fake-bytes", "image/jpeg", "en")]
    assert storage.uploads == [(b"fake-bytes", "image/jpeg")]


class _CountingTrialUsage:
    """Free-tier caller: records increments."""

    def __init__(self) -> None:
        self.increments = 0

    async def used(self, owner_keys, day):
        return {}

    async def increment(self, owner_keys, method, day):
        self.increments += 1

    async def limits(self):
        return AiTrialLimits(3, 5)


_FREE_CALLER = AiCallerDTO(keys=("user:1",), is_premium=False, signed_in=True)


async def test_analyze_image_runs_vision_and_upload_concurrently():
    both_started = {"vision": asyncio.Event(), "upload": asyncio.Event()}

    class Vision(FakeVisionProvider):
        async def analyze_image(self, image_bytes, content_type, language, catalog=None):
            both_started["vision"].set()
            await asyncio.wait_for(both_started["upload"].wait(), 1)  # needs upload to have started
            return self._result

    class Storage(FakeImageStorage):
        async def upload(self, data, content_type):
            both_started["upload"].set()
            await asyncio.wait_for(both_started["vision"].wait(), 1)  # needs vision to have started
            return self.url

    vision = Vision(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    storage = Storage()
    uc = AnalyzeFoodImageUseCase(vision=vision, images=storage, trial=_TRIAL, **_catalog())

    result = await uc.execute(_CALLER, b"x", "image/jpeg", "en")

    assert result.image_url == storage.url


async def test_analyze_image_upload_failure_still_returns_analysis_and_consumes_trial():
    class BrokenStorage:
        async def upload(self, data, content_type):
            raise RuntimeError("cloudinary down")

    usage = _CountingTrialUsage()
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    uc = AnalyzeFoodImageUseCase(
        vision=vision, images=BrokenStorage(), trial=AiTrialUseCase(usage=usage), **_catalog()
    )

    result = await uc.execute(_FREE_CALLER, b"x", "image/jpeg", "en")

    assert result.image_url is None
    assert result.ingredients == [_INGREDIENT]
    assert usage.increments == 1


async def test_analyze_image_vision_failure_propagates_and_does_not_consume_trial():
    class BrokenVision(FakeVisionProvider):
        async def analyze_image(self, image_bytes, content_type, language, catalog=None):
            raise ValueError("vision down")

    usage = _CountingTrialUsage()
    uc = AnalyzeFoodImageUseCase(
        vision=BrokenVision(FoodAnalysisDTO("", [], image_url=None)),
        images=FakeImageStorage(),
        trial=AiTrialUseCase(usage=usage),
        **_catalog(),
    )

    with pytest.raises(ValueError, match="vision down"):
        await uc.execute(_FREE_CALLER, b"x", "image/jpeg", "en")

    assert usage.increments == 0


async def test_analyze_text_never_touches_image_storage():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL, **_catalog())

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "a bowl of beef pho", "vi")

    assert result.image_url is None
    assert vision.text_calls == [("a bowl of beef pho", "vi")]


async def test_no_food_recognized_returns_empty_result_not_an_error():
    vision = FakeVisionProvider(FoodAnalysisDTO("", [], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL, **_catalog())

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "asdf", "vi")

    assert result.meal_name == ""
    assert result.ingredients == []


def _model_row(slug: str | None) -> IngredientSuggestionDTO:
    return IngredientSuggestionDTO(
        name="pho", quantity_g=550.0, kcal=999, carbs_g=1.0, protein_g=1.0, fat_g=1.0,
        fiber_g=None, confidence=0.8, catalog_food_id=slug,
    )


async def test_grounding_on_passes_the_catalog_and_grounds_the_result():
    food = make_food()
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_model_row("pho-bo")], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL, **_catalog([food]))

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "pho", "vi")

    assert vision.catalogs == [[food]]
    assert result.ingredients[0].kcal == 446
    assert result.ingredients[0].catalog_food_id == "pho-bo"


async def test_grounding_on_for_images_too():
    food = make_food()
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_model_row("pho-bo")], image_url=None))
    uc = AnalyzeFoodImageUseCase(
        vision=vision, images=FakeImageStorage(), trial=_TRIAL, **_catalog([food])
    )

    result = await uc.execute(_CALLER, b"x", "image/jpeg", "vi")

    assert vision.catalogs == [[food]]
    assert result.ingredients[0].kcal == 446


async def test_grounding_off_sends_no_catalog_and_never_reads_the_repo():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_model_row("pho-bo")], image_url=None))
    kw = _catalog([make_food()], grounding=False)
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL, **kw)

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "pho", "vi")

    assert vision.catalogs == [None]
    assert kw["catalog"].reads == 0
    row = result.ingredients[0]
    assert (row.kcal, row.catalog_name, row.verified, row.per100g) == (999, None, False, None)


async def test_empty_catalog_means_ungrounded():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_model_row("pho-bo")], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL, **_catalog([]))

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "pho", "vi")

    assert vision.catalogs == [None]
    assert result.ingredients[0].kcal == 999


def _named(name: str, slug: str | None = None) -> IngredientSuggestionDTO:
    return replace(_model_row(slug), name=name)


async def test_unmatched_rows_are_recorded_with_normalised_keys():
    kw = _catalog([make_food()])
    result = FoodAnalysisDTO(
        "Meal",
        [_named("Egg (x3)"), _named("Bánh xèo!"), _named("pho", "pho-bo"), _named("egg"), _named("ghost", "nope"), _named(" (x2)")],
        image_url=None,
    )
    uc = AnalyzeFoodTextUseCase(vision=FakeVisionProvider(result), trial=_TRIAL, **kw)

    await uc.execute(_CALLER, AiTrialMethod.TEXT, "x", "en")

    # matched "pho" is not recorded; "egg" twice in one analysis is one sighting (first display name wins);
    # a name that is only a count suffix has an empty key and is dropped.
    assert kw["misses"].recorded == [([("egg", "Egg"), ("banh xeo", "Bánh xèo"), ("ghost", "ghost")], "en")]


async def test_image_analysis_records_misses_too():
    kw = _catalog([make_food()])
    vision = FakeVisionProvider(FoodAnalysisDTO("M", [_named("Egg")], image_url=None))
    uc = AnalyzeFoodImageUseCase(vision=vision, images=FakeImageStorage(), trial=_TRIAL, **kw)

    await uc.execute(_CALLER, b"x", "image/jpeg", "vi")

    assert kw["misses"].recorded == [([("egg", "Egg")], "vi")]


async def test_fully_matched_analysis_records_nothing():
    kw = _catalog([make_food()])
    uc = AnalyzeFoodTextUseCase(
        vision=FakeVisionProvider(FoodAnalysisDTO("M", [_named("pho", "pho-bo")], image_url=None)), trial=_TRIAL, **kw
    )

    await uc.execute(_CALLER, AiTrialMethod.TEXT, "x", "vi")

    assert kw["misses"].recorded == []


async def test_grounding_off_or_empty_catalog_records_nothing():
    for kw in (_catalog([make_food()], grounding=False), _catalog([])):
        uc = AnalyzeFoodTextUseCase(
            vision=FakeVisionProvider(FoodAnalysisDTO("M", [_named("Egg")], image_url=None)), trial=_TRIAL, **kw
        )
        await uc.execute(_CALLER, AiTrialMethod.TEXT, "x", "vi")
        assert kw["misses"].recorded == []


async def test_a_failing_miss_record_does_not_fail_the_analysis_or_skip_the_trial():
    usage = _CountingTrialUsage()
    kw = _catalog([make_food()], misses=FakeMisses(fail=True))
    uc = AnalyzeFoodTextUseCase(
        vision=FakeVisionProvider(FoodAnalysisDTO("M", [_named("Egg")], image_url=None)),
        trial=AiTrialUseCase(usage=usage),
        **kw,
    )

    result = await uc.execute(_FREE_CALLER, AiTrialMethod.TEXT, "x", "vi")

    assert [r.name for r in result.ingredients] == ["Egg"]
    assert usage.increments == 1

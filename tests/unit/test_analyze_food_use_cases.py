"""AnalyzeFoodImage/TextUseCase unit tests: fake vision + fake storage. No DB, no real LLM call."""

from __future__ import annotations

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.application.use_cases.analyze_food_image import AnalyzeFoodImageUseCase
from src.application.use_cases.analyze_food_text import AnalyzeFoodTextUseCase
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

    async def analyze_image(
        self, image_bytes: bytes, content_type: str, language: str
    ) -> FoodAnalysisDTO:
        self.image_calls.append((image_bytes, content_type, language))
        return self._result

    async def analyze_text(self, description: str, language: str) -> FoodAnalysisDTO:
        self.text_calls.append((description, language))
        return self._result


class FakeTrialUsage:
    """Premium callers never reach it; free-tier counting is covered by tests/api."""

    async def used(self, owner_keys):
        raise AssertionError("premium must not read trial usage")

    async def increment(self, owner_keys, method):
        raise AssertionError("premium must not consume a trial")


_TRIAL = AiTrialUseCase(usage=FakeTrialUsage())
_CALLER = AiCallerDTO(keys=("user:1",), is_premium=True)


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
    uc = AnalyzeFoodImageUseCase(vision=vision, images=storage, trial=_TRIAL)

    result = await uc.execute(_CALLER, b"fake-bytes", "image/jpeg", "en")

    assert result.meal_name == "Pho"
    assert result.ingredients == [_INGREDIENT]
    assert result.image_url == storage.url
    assert vision.image_calls == [(b"fake-bytes", "image/jpeg", "en")]
    assert storage.uploads == [(b"fake-bytes", "image/jpeg")]


async def test_analyze_text_never_touches_image_storage():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL)

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "a bowl of beef pho", "vi")

    assert result.image_url is None
    assert vision.text_calls == [("a bowl of beef pho", "vi")]


async def test_no_food_recognized_returns_empty_result_not_an_error():
    vision = FakeVisionProvider(FoodAnalysisDTO("", [], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision, trial=_TRIAL)

    result = await uc.execute(_CALLER, AiTrialMethod.TEXT, "asdf", "vi")

    assert result.meal_name == ""
    assert result.ingredients == []

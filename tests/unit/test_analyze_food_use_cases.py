"""AnalyzeFoodImage/TextUseCase unit tests: fake vision + fake storage. No DB, no real LLM call."""

from __future__ import annotations

from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.application.use_cases.analyze_food_image import AnalyzeFoodImageUseCase
from src.application.use_cases.analyze_food_text import AnalyzeFoodTextUseCase

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
        self.image_calls: list[tuple[bytes, str]] = []
        self.text_calls: list[str] = []

    async def analyze_image(self, image_bytes: bytes, content_type: str) -> FoodAnalysisDTO:
        self.image_calls.append((image_bytes, content_type))
        return self._result

    async def analyze_text(self, description: str) -> FoodAnalysisDTO:
        self.text_calls.append(description)
        return self._result


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
    uc = AnalyzeFoodImageUseCase(vision=vision, images=storage)

    result = await uc.execute(b"fake-bytes", "image/jpeg")

    assert result.meal_name == "Pho"
    assert result.ingredients == [_INGREDIENT]
    assert result.image_url == storage.url
    assert vision.image_calls == [(b"fake-bytes", "image/jpeg")]
    assert storage.uploads == [(b"fake-bytes", "image/jpeg")]


async def test_analyze_text_never_touches_image_storage():
    vision = FakeVisionProvider(FoodAnalysisDTO("Pho", [_INGREDIENT], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision)

    result = await uc.execute("a bowl of beef pho")

    assert result.image_url is None
    assert vision.text_calls == ["a bowl of beef pho"]


async def test_no_food_recognized_returns_empty_result_not_an_error():
    vision = FakeVisionProvider(FoodAnalysisDTO("", [], image_url=None))
    uc = AnalyzeFoodTextUseCase(vision=vision)

    result = await uc.execute("asdf")

    assert result.meal_name == ""
    assert result.ingredients == []

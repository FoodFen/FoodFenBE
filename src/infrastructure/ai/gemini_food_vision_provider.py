"""Gemini implementation of ``FoodVisionProviderProtocol``.

Uses Gemini's structured-output mode (``response_schema``) so the model's
JSON is validated and parsed for us — no hand-rolled parsing of free text.
"""

from __future__ import annotations

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO


class _IngredientSchema(BaseModel):
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None
    confidence: float


class _AnalysisSchema(BaseModel):
    meal_name: str
    ingredients: list[_IngredientSchema]


_LANGUAGE_NAMES = {"vi": "Vietnamese", "en": "English"}


class GeminiFoodVisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        system_prompt: str,
        client: genai.Client | None = None,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        self._client = client or genai.Client(api_key=api_key)

    async def analyze_image(
        self, image_bytes: bytes, content_type: str, language: str
    ) -> FoodAnalysisDTO:
        part = types.Part.from_bytes(data=image_bytes, mime_type=content_type)
        return await self._generate([part], language)

    async def analyze_text(self, description: str, language: str) -> FoodAnalysisDTO:
        return await self._generate([description], language)

    async def _generate(self, contents: list, language: str) -> FoodAnalysisDTO:
        language_name = _LANGUAGE_NAMES.get(language, language)
        system_instruction = (
            f"{self._system_prompt}\n\nRespond entirely in {language_name}. Do not mix "
            "languages within mealName or any ingredient name."
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=_AnalysisSchema,
                # No tools configured — see gemini_chat_provider.py for why this
                # is set explicitly rather than left on the SDK's noisy default.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        parsed: _AnalysisSchema = response.parsed
        return FoodAnalysisDTO(
            meal_name=parsed.meal_name,
            ingredients=[
                IngredientSuggestionDTO(
                    name=i.name,
                    quantity_g=i.quantity_g,
                    kcal=i.kcal,
                    carbs_g=i.carbs_g,
                    protein_g=i.protein_g,
                    fat_g=i.fat_g,
                    fiber_g=i.fiber_g,
                    confidence=i.confidence,
                )
                for i in parsed.ingredients
            ],
            image_url=None,
        )

"""Gemini implementation of ``FoodVisionProviderProtocol``.

Uses Gemini's structured-output mode (``response_schema``) so the model's
JSON is validated and parsed for us — no hand-rolled parsing of free text.

With a catalog the model only recognises foods and grams and names a catalog id; the server
computes the nutrition (see ``application/food_grounding.py``). The catalog block is the very start
of the prompt and identical across requests and languages, so it is stored once as an explicit
Gemini context cache (implicit caching never hit on gemini-3.8-flash) and referenced per request;
the language instruction travels in ``contents`` instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Sequence

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.domain.entities.catalog_food import CatalogFood
from src.infrastructure.ai.usage import log_usage


_log = logging.getLogger("foodfenbe.ai")

_CACHE_TTL_SECONDS = 3600
_CACHE_REFRESH_MARGIN_SECONDS = 300


class _IngredientSchema(BaseModel):
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None
    confidence: float
    catalog_id: str | None = None


class _AnalysisSchema(BaseModel):
    meal_name: str
    ingredients: list[_IngredientSchema]


_LANGUAGE_NAMES = {"vi": "Vietnamese", "en": "English"}

# Shared by both prompts: counted units, meal_name, the empty-result rule.
_COMMON_RULES = """\
If the photo or description shows or mentions more than one discrete unit of
the same food (e.g. "two slices of pizza", three eggs, two cans of soda),
represent it as a single row whose name states the count in parentheses —
e.g. "Pizza slice (x2)", "Egg (x3)" — rather than silently folding the count
into a bigger portion with no indication of how many there are. quantity_g
and every macro on that row must be the TOTAL across all units combined, not
a single unit's amount. Do not do this for a dish that is naturally one
continuous portion (a bowl of soup, a plate of stir-fry) just because it
could serve more than one person — only for genuinely discrete, countable
units.

Also provide meal_name: a short, natural name for the overall meal (e.g.
"Grilled chicken with rice").

If you cannot identify any food at all (blank/unrelated image, empty or
nonsensical description), return meal_name as an empty string and an empty
ingredients list — do not guess or fabricate items, and do not treat this as
an error."""

# No catalog (grounding off or catalog empty): the model estimates every number itself.
_LEGACY_PROMPT = (
    """\
You extract a structured ingredient breakdown from a photo of a meal, or from a
one-sentence description of one. You are not a chat assistant — respond only
with the requested JSON, no commentary.

For each distinct food item you can identify, estimate:
- name: a short, human-readable label (e.g. "grilled chicken breast").
- quantity_g: your best-guess portion size in grams for what's actually shown
  or described — not a generic 100 g reference amount.
- kcal, carbs_g, protein_g, fat_g: scaled to that estimated quantity_g, not
  to 100 g.
- fiber_g: your best estimate scaled to quantity_g. Omit it (leave null) only
  when you have no reasonable basis to estimate it at all — do not use 0 as
  a stand-in for "unsure"; use 0 only when you are confident the item has
  essentially no fiber.
- confidence: 0 to 1, your own certainty in that row's numbers. Low for a
  rough guess (e.g. a vague or unclear description/photo), high when the
  food and portion are clearly identifiable. This is shown to the user to
  flag uncertain rows — it is not stored, so err toward being genuinely
  calibrated rather than uniformly high or low.

"""
    + _COMMON_RULES
)

_GROUNDED_PROMPT = (
    """\
You extract a structured food breakdown from a photo of a meal, or from a
one-sentence description of one. You are not a chat assistant — respond only
with the requested JSON, no commentary.

The FOOD CATALOG above lists foods with sourced nutrition. For the meal:
1. List each distinct food. If one catalog food is the whole dish (e.g. a bowl
   of phở bò, a plate of cơm tấm sườn), return ONE row for that dish. Only when
   no catalog food is the whole dish, list its components as separate rows.
2. catalog_id: the id of the catalog food that truly is the same food as the
   row, or null. Never pick a merely similar food (another dish, cut, cooking
   method or flavour): a wrong match is worse than none.
3. name: a short, human-readable label for the row.
4. quantity_g: your best estimate of the grams actually shown or described,
   not a generic 100 g. For a row with a catalog_id, use that food's default
   serving grams as a size anchor, then adjust for what you see.
5. kcal, carbs_g, protein_g, fat_g, fiber_g: always your own estimate scaled
   to quantity_g, for every row, including rows with a catalog_id. Leave
   fiber_g null only when you have no reasonable basis to estimate it; never
   use 0 for "unsure".
6. confidence: 0 to 1, your own certainty in the row (food and portion). Low
   for a rough guess, high when clearly identifiable. Be calibrated.

"""
    + _COMMON_RULES
)

_CATALOG_HEADER = "FOOD CATALOG (one food per line: id | name | aliases | default serving grams):"


def _catalog_block(catalog: Sequence[CatalogFood]) -> str:
    lines = [
        f"{f.slug} | {f.name} | {', '.join(f.aliases)} | {next(s.grams for s in f.servings if s.default)}"
        for f in catalog
    ]
    return "\n".join([_CATALOG_HEADER, *lines])


class GeminiFoodVisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: genai.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = model
        self._client = client or genai.Client(api_key=api_key)
        self._clock = clock
        # (prefix_key, cache name, expires_at on self._clock); old caches just expire server-side.
        self._cache: tuple[str, str, float] | None = None
        self._cache_lock = asyncio.Lock()

    async def analyze_image(
        self,
        image_bytes: bytes,
        content_type: str,
        language: str,
        catalog: Sequence[CatalogFood] | None = None,
    ) -> FoodAnalysisDTO:
        part = types.Part.from_bytes(data=image_bytes, mime_type=content_type)
        return await self._generate([part], language, catalog)

    async def analyze_text(
        self, description: str, language: str, catalog: Sequence[CatalogFood] | None = None
    ) -> FoodAnalysisDTO:
        return await self._generate([description], language, catalog)

    async def _cache_for(self, prefix: str) -> str | None:
        """Name of a live cache holding ``prefix``, creating one if needed; None if that fails."""
        key = hashlib.sha256(prefix.encode()).hexdigest()
        async with self._cache_lock:
            cached = self._cache
            if cached and cached[0] == key and cached[2] - self._clock() > _CACHE_REFRESH_MARGIN_SECONDS:
                return cached[1]
            try:
                cache = await self._client.aio.caches.create(
                    model=self._model,
                    config=types.CreateCachedContentConfig(
                        system_instruction=prefix,
                        ttl=f"{_CACHE_TTL_SECONDS}s",
                        display_name="food-analysis-catalog",
                    ),
                )
            except Exception:
                _log.warning("gemini food-analysis cache creation failed", exc_info=True)
                return None
            self._cache = (key, cache.name, self._clock() + _CACHE_TTL_SECONDS)
            usage = getattr(cache, "usage_metadata", None)
            _log.info(
                "gemini food-analysis cache created: name=%s tokens=%s ttl=%ss",
                cache.name,
                getattr(usage, "total_token_count", None),
                _CACHE_TTL_SECONDS,
            )
            return cache.name

    def _call(self, contents: list, system_instruction: str | None, cache_name: str | None):
        return self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                cached_content=cache_name,
                response_mime_type="application/json",
                response_schema=_AnalysisSchema,
                # No tools configured — see gemini_chat_provider.py for why this
                # is set explicitly rather than left on the SDK's noisy default.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                # LOW, not MINIMAL: newer models (gemini-3.8-flash) reject MINIMAL with a 400. Same level as chat.
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                # Headroom for LOW thinking plus a few hundred tokens of JSON; the cap only stops a runaway reply.
                max_output_tokens=4096,
            ),
        )

    async def _generate(
        self, contents: list, language: str, catalog: Sequence[CatalogFood] | None
    ) -> FoodAnalysisDTO:
        language_name = _LANGUAGE_NAMES.get(language, language)
        language_rule = (
            f"Respond entirely in {language_name}. Do not mix "
            "languages within mealName or any ingredient name."
        )
        if not catalog:
            response = await self._call(contents, f"{_LEGACY_PROMPT}\n\n{language_rule}", None)
        else:
            prefix = f"{_catalog_block(catalog)}\n\n{_GROUNDED_PROMPT}"
            contents = [*contents, language_rule]
            name = await self._cache_for(prefix)
            try:
                response = await self._call(contents, None if name else prefix, name)
            except errors.ClientError as e:
                # The cache expired or was deleted server-side: drop it, make a new one and retry
                # once. Any other error, or a failure on the retry, propagates.
                if not name or not (e.code in (403, 404) or "cache" in str(e).lower()):
                    raise
                async with self._cache_lock:
                    if self._cache and self._cache[1] == name:
                        self._cache = None
                name = await self._cache_for(prefix)
                response = await self._call(contents, None if name else prefix, name)
        log_usage("food-analysis", response.usage_metadata)
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
                    catalog_food_id=i.catalog_id if catalog else None,
                )
                for i in parsed.ingredients
            ],
            image_url=None,
        )

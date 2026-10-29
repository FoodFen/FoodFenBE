"""Fen's dish recommendations: the DISHES context section, the marker stripper, card id validation.

Standard library only; pure so it is tested without fakes. Fen writes ``[[dish:<id>]]`` after each dish
it recommends; the server strips those from the stream and turns the valid ids into cards.
"""

from __future__ import annotations

from collections.abc import Iterable
from string import hexdigits
from uuid import UUID

from src.application.dish_fit import RankedDish, diet_ok
from src.application.dtos.chat import ChatDishDTO
from src.application.dtos.restaurant import PublicDishDTO, PublicRestaurantSummaryDTO
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import DietType

# ponytail: every diet-ok public dish goes into the prompt up to this cap; past it, pick candidates by
# retrieval (e.g. pgvector) before ranking.
MAX_CHAT_DISHES = 200
MAX_CARDS = 5

_HEADER = (
    "DISHES (real dishes on FoodFen you may recommend)\n"
    "Use this list only when suggesting a dish to order or eat at a FoodFen restaurant: never invent one, "
    "and write [[dish:<id>]] with the exact id right after each dish you recommend. For anything else "
    "(recipes, home cooking, nutrition questions, food outside the app) answer normally, without markers. "
    "If the user asks for a dish or restaurant that is not listed, say FoodFen doesn't have it yet, then "
    "still help. The user's request (e.g. high protein, cheap, a restaurant, a cuisine) comes first; "
    "\"suggested\" only breaks ties when they ask for nothing specific. If a dish has an exceeds_* reason, "
    "say in words that it goes over the user's kcal / carbs / fat left today. Reply in the user's language."
)
# "x" = one hex digit. A marker is exactly this shape.
_SHAPE = "[[dish:" + "-".join("x" * n for n in (8, 4, 4, 4, 12)) + "]]"


def pick_candidates(ranked: Iterable[RankedDish], diet: DietType | None) -> list[RankedDish]:
    return [r for r in ranked if diet_ok(r.dish, diet)][:MAX_CHAT_DISHES]


def render_dishes(candidates: list[RankedDish], public: dict[UUID, tuple[Dish, Restaurant]]) -> str:
    """The DISHES section, or "" when there is nothing to recommend."""
    if not candidates:
        return ""
    lines = []
    for r in candidates:
        d = r.dish
        flag = "suggested" if r.fits else "not suggested"
        warn = [c for c in r.reasons if c.startswith("exceeds_")]
        lines.append(
            f"- {d.id} | {d.name} | {public[d.id][1].name} | {d.kcal} kcal, P {d.protein_g:g}g, "
            f"C {d.carbs_g:g}g, F {d.fat_g:g}g | {d.price:f} VND | {flag}" + (f" ({', '.join(warn)})" if warn else "")
        )
    return "\n".join([_HEADER, *lines])


def _fits(s: str) -> bool:
    return all(c == t or (t == "x" and c in hexdigits) for c, t in zip(s, _SHAPE, strict=False))


class MarkerStripper:
    """Removes ``[[dish:<uuid>]]`` from a stream of deltas, collecting the ids in ``ids``.

    Text from a ``[`` is held back only while it can still become a marker, so a marker split across
    deltas never leaks and other ``[[`` text flows through unchanged."""

    def __init__(self) -> None:
        self.ids: list[UUID] = []
        self._held = ""

    def feed(self, delta: str) -> str:
        buf, self._held, out, i = self._held + delta, "", [], 0
        while i < len(buf):
            if buf[i] != "[":
                out.append(buf[i])
                i += 1
                continue
            rest = buf[i : i + len(_SHAPE)]
            if len(rest) == len(_SHAPE) and _fits(rest):
                self.ids.append(UUID(rest[7:-2]))
                i += len(_SHAPE)
            elif len(rest) < len(_SHAPE) and _fits(rest):  # may still become a marker
                self._held = rest
                break
            else:
                out.append("[")
                i += 1
        return "".join(out)

    def finish(self) -> str:
        held, self._held = self._held, ""
        return held


def valid_ids(found: Iterable[UUID], candidates: set[UUID]) -> list[UUID]:
    """Ids Fen wrote that were really offered this turn, de-duplicated in order, at most ``MAX_CARDS``."""
    return list(dict.fromkeys(i for i in found if i in candidates))[:MAX_CARDS]


def to_cards(ids: Iterable[UUID], public: dict[UUID, tuple[Dish, Restaurant]]) -> list[ChatDishDTO]:
    """Hydrate ids into cards; an id that is no longer public is dropped."""
    return [
        ChatDishDTO(PublicDishDTO.from_entity(d), PublicRestaurantSummaryDTO.from_entity(r))
        for i in ids
        if i in public
        for d, r in [public[i]]
    ]

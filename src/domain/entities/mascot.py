"""Mascot entity — a collectible companion; free when ``coin_cost`` is 0, otherwise bought with coins."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from src.domain.enums import MascotState
from src.domain.exceptions import (
    InvalidMascotException,
    MascotDefaultLockedException,
    MascotMissingIdleImageException,
)
from src.domain.validation import require_non_empty

FREE_MASCOT_ID = "default"
# ponytail: the app draws these four itself, so they may be active with no server image.
# Drop an id from the set once it has server art.
HAND_DRAWN_IDS = frozenset({"default", "sprout", "berry", "chili"})

_SLUG = re.compile(r"[a-z0-9_-]{1,32}")
_MAX_NAME = 40
_MAX_COST = 1_000_000


@dataclass
class Mascot:
    id: str  # slug, e.g. "sprout" — immutable; the app keys its artwork on it
    name: str
    coin_cost: int
    active: bool = True
    images: dict[MascotState, str] = field(default_factory=dict)  # at most one URL per state

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.id):
            raise InvalidMascotException(f"id must be 1-32 chars of a-z, 0-9, _ or -, got {self.id!r}")
        self.name = require_non_empty(self.name, "name", InvalidMascotException)
        if len(self.name) > _MAX_NAME:
            raise InvalidMascotException(f"name must be at most {_MAX_NAME} characters")
        if not 0 <= self.coin_cost <= _MAX_COST:
            raise InvalidMascotException(f"coin_cost must be between 0 and {_MAX_COST}, got {self.coin_cost!r}")

    @classmethod
    def create(
        cls, id: str, name: str, coin_cost: int, active: bool = False, images: dict[MascotState, str] | None = None
    ) -> Mascot:
        """New mascots are drafts (inactive) unless asked otherwise."""
        mascot = cls(id=id, name=name, coin_cost=coin_cost, active=active, images=dict(images or {}))
        mascot._check_rules()
        return mascot

    def update(
        self,
        name: str | None = None,
        coin_cost: int | None = None,
        active: bool | None = None,
        images: dict[MascotState, str | None] | None = None,
    ) -> None:
        """Only the given fields change. ``images`` merges per state: a URL sets it, ``None`` removes it,
        an absent state is untouched. Invalid input raises before anything changes."""
        merged = dict(self.images)
        for state, url in (images or {}).items():
            if url is None:
                merged.pop(state, None)
            else:
                merged[state] = url
        changed = replace(
            self,
            name=self.name if name is None else name,
            coin_cost=self.coin_cost if coin_cost is None else coin_cost,
            active=self.active if active is None else active,
            images=merged,
        )  # replace() re-runs __post_init__
        changed._check_rules()
        self.name, self.coin_cost, self.active, self.images = changed.name, changed.coin_cost, changed.active, merged

    def ensure_deletable(self) -> None:
        if self.id == FREE_MASCOT_ID:
            raise MascotDefaultLockedException("the default mascot cannot be deleted")

    def _check_rules(self) -> None:
        """Rules over the whole state. Not in ``__post_init__``: a row edited by hand in the DB must still load."""
        if self.id == FREE_MASCOT_ID and (not self.active or self.coin_cost > 0):
            raise MascotDefaultLockedException("the default mascot must stay active and free")
        if self.active and self.id not in HAND_DRAWN_IDS and MascotState.IDLE not in self.images:
            raise MascotMissingIdleImageException("an active mascot needs an idle image")

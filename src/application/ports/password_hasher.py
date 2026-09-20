"""Password hashing port. Standard library only — the algorithm lives in infrastructure."""

from __future__ import annotations

from typing import Protocol


class PasswordHasherProtocol(Protocol):
    def hash(self, plain: str) -> str: ...

    def verify(self, plain: str, hashed: str) -> bool: ...

"""bcrypt implementation of ``PasswordHasherProtocol``."""

from __future__ import annotations

import asyncio

import bcrypt


class BcryptPasswordHasher:
    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    async def hash(self, plain: str) -> str:
        # bcrypt at cost 12 burns ~250ms of CPU: keep it off the event loop.
        hashed = await asyncio.to_thread(
            bcrypt.hashpw, plain.encode("utf-8"), bcrypt.gensalt(self._rounds)
        )
        return hashed.decode("utf-8")

    async def verify(self, plain: str, hashed: str) -> bool:
        try:
            return await asyncio.to_thread(
                bcrypt.checkpw, plain.encode("utf-8"), hashed.encode("utf-8")
            )
        except ValueError:
            # Malformed stored hash — treat as a non-match rather than a 500.
            return False

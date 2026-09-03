"""User entity. Standard library only — invariants enforced on construction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidUserAttributeException

# Deliberately permissive: "something@something.something", no whitespace.
# ponytail: naive regex, swap for a real RFC 5322 validator only if bad addresses reach production.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class User:
    id: UUID
    email: str
    name: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        email = (self.email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise InvalidUserAttributeException(f"invalid email address: {self.email!r}")
        self.email = email

        name = (self.name or "").strip()
        if not name:
            raise InvalidUserAttributeException("user name must not be empty")
        self.name = name

    @classmethod
    def create(cls, email: str, name: str) -> User:
        """Factory for a brand-new user: fresh id, active, created now."""
        return cls(
            id=uuid4(),
            email=email,
            name=name,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

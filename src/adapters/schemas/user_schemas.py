"""HTTP wire models. Pydantic v2 lives here and nowhere deeper.

Email *syntax* is validated by the domain entity (translated to HTTP 400), so the
schema only needs a non-empty string — no `email-validator` dependency required.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime

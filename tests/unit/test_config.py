import pytest
from pydantic import ValidationError

from src.infrastructure.config import Settings


def test_unknown_email_backend_fails_at_startup():
    with pytest.raises(ValidationError):
        Settings(email_backend="smtp")

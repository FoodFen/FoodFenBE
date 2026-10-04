"""Domain-exception -> HTTP-status translation, registered once on the app.

Failure body shape is the front-end contract's: ``{message?, error?, errors?}``
(see docs/authentication.md) — not FastAPI's default ``{"detail": ...}``. Also
applied to Pydantic's own request-validation errors, so every non-2xx response
from this API uses one shape.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    AiTrialExhaustedException,
    AuthenticationException,
    DomainException,
    EntityNotFoundException,
    InsufficientCoinsException,
    InvalidAttributeException,
    InvalidWebhookSignatureException,
    PremiumRequiredException,
    QuizAlreadySubmittedException,
    RateLimitedException,
    UserAlreadyExistsException,
)

# Domain exception type -> HTTP status. Registration order is irrelevant: Starlette
# resolves a raised exception against the most specific registered base via its MRO.
# UserAlreadyExistsException is handled separately below (it needs a field-keyed
# `errors` body, not just a message) so it is deliberately not listed here.
EXCEPTION_STATUS: list[tuple[type[DomainException], int]] = [
    (InvalidWebhookSignatureException, 401),  # a more specific AuthenticationException
    (InvalidAttributeException, 400),  # + InvalidUserAttributeException, WeakPasswordException, InvalidPaymentStateException
    (AuthenticationException, 401),  # + InvalidCredentialsException, InvalidTokenException
    (PremiumRequiredException, 402),
    (RateLimitedException, 429),
    (InsufficientCoinsException, 409),
    (EntityNotFoundException, 404),  # + UserNotFoundException, PaymentNotFoundException
    (DomainException, 400),  # catch-all
]


def _domain_exception_handler(status_code: int):
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None

    async def handler(_: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=status_code, content={"message": str(exc)}, headers=headers
        )

    return handler


async def _duplicate_email_handler(_: Request, exc: UserAlreadyExistsException) -> JSONResponse:
    message = str(exc)
    return JSONResponse(
        status_code=400, content={"message": message, "errors": {"email": message}}
    )


async def _ai_trial_exhausted_handler(_: Request, exc: AiTrialExhaustedException) -> JSONResponse:
    """403 with a stable machine code, so the client can tell it from any other 403."""
    return JSONResponse(
        status_code=403,
        content={
            "message": str(exc),
            "code": "ai_trial_exhausted",
            "inputMethod": exc.input_method.value,
            "resetsAt": exc.resets_at.isoformat(),
        },
    )


async def _quiz_already_submitted_handler(
    _: Request, exc: QuizAlreadySubmittedException
) -> JSONResponse:
    """409 with a stable machine code, so the client can tell it from any other 409."""
    return JSONResponse(
        status_code=409, content={"message": str(exc), "error": "quiz_already_submitted"}
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Reshape Pydantic's ``{"detail": [...]}`` into ``{message, errors}``."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"] if part != "body") or "_"
        errors.setdefault(field, err["msg"])
    return JSONResponse(
        status_code=422, content={"message": "validation failed", "errors": errors}
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(UserAlreadyExistsException, _duplicate_email_handler)
    app.add_exception_handler(AiTrialExhaustedException, _ai_trial_exhausted_handler)
    app.add_exception_handler(QuizAlreadySubmittedException, _quiz_already_submitted_handler)
    for exc_type, status_code in EXCEPTION_STATUS:
        app.add_exception_handler(exc_type, _domain_exception_handler(status_code))

"""Payment endpoints (PayOS checkout). HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.adapters.schemas.payment_schemas import (
    CancelPaymentRequest,
    CheckoutResponse,
    CreateCheckoutRequest,
    PaymentResponse,
)
from src.application.dtos.payment import CreateCheckoutInputDTO
from src.infrastructure.di import (
    CancelPaymentUseCaseDep,
    CreateCheckoutUseCaseDep,
    CurrentUserDep,
    GetPaymentStatusUseCaseDep,
    HandlePaymentWebhookUseCaseDep,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CreateCheckoutRequest, user: CurrentUserDep, use_case: CreateCheckoutUseCaseDep
) -> CheckoutResponse:
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=user.id, plan_type=body.plan_type))
    return CheckoutResponse.from_dto(result)


@router.get("/{order_code}", response_model=PaymentResponse)
async def get_payment(
    order_code: int, user: CurrentUserDep, use_case: GetPaymentStatusUseCaseDep
) -> PaymentResponse:
    result = await use_case.execute(user_id=user.id, order_code=order_code)
    return PaymentResponse.from_dto(result)


@router.post("/{order_code}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    order_code: int,
    body: CancelPaymentRequest,
    user: CurrentUserDep,
    use_case: CancelPaymentUseCaseDep,
) -> PaymentResponse:
    result = await use_case.execute(
        user_id=user.id, order_code=order_code, reason=body.cancellation_reason
    )
    return PaymentResponse.from_dto(result)


@router.post("/webhook", status_code=200)
async def payment_webhook(
    request: Request, use_case: HandlePaymentWebhookUseCaseDep
) -> dict[str, str]:
    raw_body = await request.body()
    await use_case.execute(raw_body)
    return {"code": "00"}

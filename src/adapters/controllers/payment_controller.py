"""Payment endpoints (PayOS, MoMo). HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from src.adapters.schemas.payment_schemas import (
    CancelPaymentRequest,
    CheckoutResponse,
    CreateCheckoutRequest,
    PaymentResponse,
    PlansResponse,
)
from src.application.dtos.payment import CreateCheckoutInputDTO
from src.domain.enums import PaymentProvider
from src.infrastructure.di import (
    CancelPaymentUseCaseDep,
    CreateCheckoutUseCaseDep,
    CurrentUserDep,
    GetPaymentStatusUseCaseDep,
    HandlePaymentWebhookUseCaseDep,
    ListPlansUseCaseDep,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CreateCheckoutRequest, user: CurrentUserDep, use_case: CreateCheckoutUseCaseDep
) -> CheckoutResponse:
    result = await use_case.execute(
        CreateCheckoutInputDTO(user_id=user.id, plan_type=body.plan_type, provider=body.provider)
    )
    return CheckoutResponse.from_dto(result)


# Public: a guest looking at the paywall needs the prices. Declared before "/{order_code}" so
# "plans" is not parsed as an order code.
@router.get("/plans", response_model=PlansResponse)
async def list_plans(use_case: ListPlansUseCaseDep) -> PlansResponse:
    return PlansResponse.from_dto(use_case.execute())


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
    await use_case.execute(PaymentProvider.PAYOS, await request.body())
    return {"code": "00"}


# MoMo's IPN contract expects an empty 204 acknowledgement.
@router.post("/webhook/momo", status_code=204)
async def momo_webhook(request: Request, use_case: HandlePaymentWebhookUseCaseDep) -> Response:
    await use_case.execute(PaymentProvider.MOMO, await request.body())
    return Response(status_code=204)

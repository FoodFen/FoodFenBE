"""MoMo adapter (v2 gateway, captureWallet): implements PaymentProviderProtocol over httpx.

Raw signature strings are MoMo's documented field order, which is alphabetical —
so ``_sign`` sorts the keys rather than hard-coding each order.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from src.application.ports.payment_provider import (
    CheckoutLinkResult,
    ProviderPaymentStatus,
    WebhookPayload,
)
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException

_ORDER_ID_PREFIX = "FF"
# Final payment failures: insufficient funds, rejected, cancelled, limit, expired, user denied,
# account inactive, cancelled by partner, promo restriction, account restricted, auth failed.
# Any other non-zero code (1000 awaiting user, 7000/7002 processing, 9000 authorized, 10 maintenance,
# 11/13 auth, 99 unknown) stays PENDING so a payment that may still succeed is never failed.
# ponytail: list from MoMo's result-code table; add a code here only once it is confirmed final.
_FAILED_RESULT_CODES = frozenset({1001, 1002, 1003, 1004, 1005, 1006, 1007, 1017, 1026, 4001, 4100})
_IPN_SIGNED_FIELDS = (
    "amount",
    "extraData",
    "message",
    "orderId",
    "orderInfo",
    "orderType",
    "partnerCode",
    "payType",
    "requestId",
    "responseTime",
    "resultCode",
    "transId",
)


def _status_for(result_code: int) -> PaymentStatus:
    if result_code == 0:
        return PaymentStatus.PAID
    if result_code in _FAILED_RESULT_CODES:
        return PaymentStatus.FAILED
    return PaymentStatus.PENDING


@dataclass
class MomoPaymentProvider:
    http: httpx.AsyncClient
    partner_code: str
    access_key: str
    secret_key: str
    redirect_url: str
    ipn_url: str

    def _sign(self, fields: dict[str, Any]) -> str:
        raw = "&".join(f"{key}={fields[key]}" for key in sorted(fields))
        return hmac.new(self.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await self.http.post(path, json=body, timeout=30)
        response.raise_for_status()
        return response.json()

    async def create_checkout_link(
        self, order_code: int, amount: Decimal, description: str, cancel_url: str, return_url: str
    ) -> CheckoutLinkResult:
        # MoMo sends the user back to self.redirect_url; PayOS's return/cancel URLs don't apply.
        order_id = f"{_ORDER_ID_PREFIX}{order_code}"
        fields: dict[str, Any] = {
            "accessKey": self.access_key,
            "amount": int(amount),
            "extraData": "",
            "ipnUrl": self.ipn_url,
            "orderId": order_id,
            "orderInfo": description,
            "partnerCode": self.partner_code,
            "redirectUrl": self.redirect_url,
            "requestId": order_id,
            "requestType": "captureWallet",
        }
        body = {k: v for k, v in fields.items() if k != "accessKey"}
        data = await self._post(
            "/v2/gateway/api/create", {**body, "lang": "vi", "signature": self._sign(fields)}
        )
        if data.get("resultCode") != 0:
            raise RuntimeError(f"MoMo create failed: {data.get('resultCode')} {data.get('message')}")
        return CheckoutLinkResult(
            payment_link_id=order_id,
            checkout_url=data["payUrl"],
            qr_code=None,
            deeplink=data.get("deeplink"),
        )

    async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus:
        order_id = f"{_ORDER_ID_PREFIX}{order_code}"
        request_id = uuid.uuid4().hex
        signature = self._sign(
            {
                "accessKey": self.access_key,
                "orderId": order_id,
                "partnerCode": self.partner_code,
                "requestId": request_id,
            }
        )
        data = await self._post(
            "/v2/gateway/api/query",
            {
                "partnerCode": self.partner_code,
                "requestId": request_id,
                "orderId": order_id,
                "lang": "vi",
                "signature": signature,
            },
        )
        status = _status_for(data["resultCode"])
        return ProviderPaymentStatus(
            order_code=order_code, status=status, succeeded=status is PaymentStatus.PAID
        )

    async def cancel(self, order_code: int, reason: str | None) -> None:
        # MoMo has no cancel for an unpaid order; it expires on MoMo's side.
        return None

    def verify_webhook(self, raw_body: bytes) -> WebhookPayload:
        try:
            data = json.loads(raw_body)
            fields = {key: data[key] for key in _IPN_SIGNED_FIELDS}
            signature = str(data["signature"])
            order_code = int(str(data["orderId"]).removeprefix(_ORDER_ID_PREFIX))
            status = _status_for(int(data["resultCode"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidWebhookSignatureException("malformed MoMo IPN") from exc
        expected = self._sign({**fields, "accessKey": self.access_key})
        if not hmac.compare_digest(expected, signature):
            raise InvalidWebhookSignatureException("MoMo IPN signature mismatch")
        return WebhookPayload(
            order_code=order_code, status=status, succeeded=status is PaymentStatus.PAID
        )

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest

from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException
from src.infrastructure.payments.momo_provider import MomoPaymentProvider

SECRET = "secret"


def _provider(handler) -> MomoPaymentProvider:
    return MomoPaymentProvider(
        http=httpx.AsyncClient(base_url="https://momo.test", transport=httpx.MockTransport(handler)),
        partner_code="PARTNER",
        access_key="ACCESS",
        secret_key=SECRET,
        redirect_url="foodfen://premium/return",
        ipn_url="https://api.test/payments/webhook/momo",
    )


def _sign(raw: str) -> str:
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


async def test_create_signs_the_documented_raw_string_and_returns_the_deeplink():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"resultCode": 0, "payUrl": "https://pay.momo/x", "deeplink": "momo://x"}
        )

    link = await _provider(handler).create_checkout_link(
        42, Decimal("49000"), "FoodFen monthly premium", "unused", "unused"
    )

    body = seen["body"]
    assert seen["path"] == "/v2/gateway/api/create"
    assert body["partnerCode"] == "PARTNER"
    assert body["orderId"] == "FF42"
    assert body["amount"] == 49000
    assert body["requestType"] == "captureWallet"
    assert body["redirectUrl"] == "foodfen://premium/return"
    assert body["ipnUrl"] == "https://api.test/payments/webhook/momo"
    assert "accessKey" not in body
    assert body["signature"] == _sign(
        "accessKey=ACCESS&amount=49000&extraData=&ipnUrl=https://api.test/payments/webhook/momo"
        "&orderId=FF42&orderInfo=FoodFen monthly premium&partnerCode=PARTNER"
        "&redirectUrl=foodfen://premium/return&requestId=FF42&requestType=captureWallet"
    )
    assert link.checkout_url == "https://pay.momo/x"
    assert link.deeplink == "momo://x"
    assert link.qr_code is None


async def test_create_raises_when_momo_rejects_the_order():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"resultCode": 22, "message": "bad amount"})

    with pytest.raises(RuntimeError):
        await _provider(handler).create_checkout_link(42, Decimal("49000"), "x", "u", "u")


@pytest.mark.parametrize(
    ("result_code", "expected"),
    [
        (0, PaymentStatus.PAID),
        (1000, PaymentStatus.PENDING),
        (7000, PaymentStatus.PENDING),
        (7002, PaymentStatus.PENDING),
        (9000, PaymentStatus.PENDING),
        (99, PaymentStatus.PENDING),
        (13, PaymentStatus.PENDING),
        (10, PaymentStatus.PENDING),
        (1006, PaymentStatus.FAILED),
        (1005, PaymentStatus.FAILED),
    ],
)
async def test_query_maps_result_codes(result_code, expected):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"resultCode": result_code})

    status = await _provider(handler).get_payment_status(42)

    body = seen["body"]
    assert seen["path"] == "/v2/gateway/api/query"
    assert body["orderId"] == "FF42"
    assert body["signature"] == _sign(
        f"accessKey=ACCESS&orderId=FF42&partnerCode=PARTNER&requestId={body['requestId']}"
    )
    assert status.order_code == 42
    assert status.status is expected
    assert status.succeeded is (expected is PaymentStatus.PAID)


async def test_cancel_makes_no_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("cancel must not call MoMo")

    await _provider(handler).cancel(42, "changed my mind")


IPN_RAW = (
    "accessKey=ACCESS&amount=49000&extraData=&message=ok&orderId=FF42"
    "&orderInfo=FoodFen monthly premium&orderType=momo_wallet&partnerCode=PARTNER&payType=qr"
    "&requestId=FF42&responseTime=1700000000000&resultCode={code}&transId=123"
)


def _ipn(code: int = 0, **overrides) -> bytes:
    data = {
        "partnerCode": "PARTNER",
        "orderId": "FF42",
        "requestId": "FF42",
        "amount": 49000,
        "orderInfo": "FoodFen monthly premium",
        "orderType": "momo_wallet",
        "transId": 123,
        "resultCode": code,
        "message": "ok",
        "payType": "qr",
        "responseTime": 1700000000000,
        "extraData": "",
        "signature": _sign(IPN_RAW.format(code=code)),
    }
    return json.dumps({**data, **overrides}).encode()


def _unused(request: httpx.Request) -> httpx.Response:
    raise AssertionError("verify_webhook must not call MoMo")


def test_verify_webhook_accepts_a_signed_successful_ipn():
    payload = _provider(_unused).verify_webhook(_ipn(0))

    assert payload.order_code == 42
    assert payload.succeeded is True


def test_verify_webhook_reports_a_signed_failed_ipn():
    payload = _provider(_unused).verify_webhook(_ipn(1006))

    assert payload.order_code == 42
    assert payload.status is PaymentStatus.FAILED
    assert payload.succeeded is False


def test_verify_webhook_keeps_a_non_final_ipn_code_pending():
    payload = _provider(_unused).verify_webhook(_ipn(9000))

    assert payload.status is PaymentStatus.PENDING
    assert payload.succeeded is False


def test_verify_webhook_accepts_a_string_result_code():
    payload = _provider(_unused).verify_webhook(_ipn(0, resultCode="0"))

    assert payload.status is PaymentStatus.PAID
    assert payload.succeeded is True


def test_verify_webhook_rejects_a_non_numeric_result_code():
    with pytest.raises(InvalidWebhookSignatureException):
        _provider(_unused).verify_webhook(_ipn(0, resultCode="abc"))


def test_verify_webhook_rejects_a_tampered_amount():
    with pytest.raises(InvalidWebhookSignatureException):
        _provider(_unused).verify_webhook(_ipn(0, amount=1000))


def test_verify_webhook_rejects_a_missing_field():
    body = json.loads(_ipn(0))
    del body["transId"]

    with pytest.raises(InvalidWebhookSignatureException):
        _provider(_unused).verify_webhook(json.dumps(body).encode())


def test_verify_webhook_rejects_malformed_json():
    with pytest.raises(InvalidWebhookSignatureException):
        _provider(_unused).verify_webhook(b"not json")

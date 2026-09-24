# PayOS payment feature — design

Date: 2026-09-24
Status: approved for implementation

## Goal

Let a user buy a Premium plan (monthly or annual) via PayOS (VietQR / bank-transfer
checkout links), and have that purchase flip `User.subscription_tier` to `PREMIUM` for
the agreed period. A later slice will put `CurrentPremiumUserDep` (added here) in front
of actual premium-only endpoints — none exist yet.

## Scope decisions (confirmed with user)

- Payment plumbing **and** the premium gate dependency are both in scope now; no premium
  endpoint consumes the gate yet.
- Renewal is **manual**: PayOS payment links are one-time bank-transfer/QR payments, not
  a tokenized card. A subscription simply lapses at `end_date` if not renewed. No cron,
  no auto-charge.
- Both `PlanType.MONTHLY` and `PlanType.ANNUAL` ship at once.
- Real PayOS sandbox credentials will be supplied via `.env`; config keys added with no
  defaults (fail closed, matching `google_oauth_client_ids` convention).

## Existing state this design builds on

- `src/domain/entities/subscription.py` + `subscriptions` table (migration `0002`) exist
  but have **no** repository / use case / controller — this design completes that slice.
- `User.subscription_tier` (`SubscriptionTier.FREE|PREMIUM`) and `User.is_premium` already
  exist and are already the field the front-end contract reads (`GET /auth/me`, via
  `UserOutputDTO`/`UserResponse`). **This is the actual premium gate** — `Subscription` is
  the detailed billing record (dates, price, status) that this flag is derived from, kept
  in sync by this feature. The gate does not need a new user-facing concept.
- PayOS SDK: official `payos` PyPI package, `AsyncPayOS` client (async, fits this async
  FastAPI app) — same "wrap the vendor SDK" pattern already used for `google-genai` and
  `cloudinary`. Exact method/exception names on the installed version must be checked
  against its actual type stubs at implementation time (docs summaries are not gospel);
  if a method used below doesn't exist as named, adapt `PayOsPaymentProvider` to whatever
  the installed SDK actually exposes — the port (`PaymentProviderProtocol`) is what the
  rest of the app depends on, not the SDK's exact surface.

## PayOS API contract (verified against payos.vn/docs, 2026-09-24)

- Base URL: `https://api-merchant.payos.vn`. Headers: `x-client-id`, `x-api-key`.
- `POST /v2/payment-requests` — create link. Required: `orderCode` (int), `amount` (int,
  VND, no decimals), `description`, `cancelUrl`, `returnUrl`, `signature`. Response
  `data`: `checkoutUrl`, `qrCode`, `paymentLinkId`, `status` (`PENDING`/...), `accountNumber`, `bin`.
  Request signature: HMAC-SHA256(checksum key, `"amount=$amount&cancelUrl=$cancelUrl&description=$description&orderCode=$orderCode&returnUrl=$returnUrl"`).
- `GET /v2/payment-requests/{id}` — status: `data.status`, `amountPaid`, `amountRemaining`.
- `POST /v2/payment-requests/{id}/cancel` — body `{cancellationReason?}`.
- `POST /confirm-webhook` — one-time **ops** step (call once via SDK or the
  `my.payos.vn` dashboard) to register our webhook URL with PayOS. Not part of the
  application code path — documented in `.env.example`, not automated.
- Webhook (IPN) POST body: `{code, desc, success, data: {orderCode, amount, description,
  accountNumber, reference, transactionDateTime, currency, paymentLinkId, code, desc,
  counterAccountBankId/Name, counterAccountName, counterAccountNumber,
  virtualAccountName, virtualAccountNumber}, signature}`. Verify: sort `data`'s keys
  alphabetically, `"k=v&k=v..."` (nested values JSON-encoded, null → `""`), HMAC-SHA256
  with the checksum key, compare hex digest to `signature`. The SDK's `webhooks.verify()`
  (name to confirm at implementation time) should do this instead of hand-rolling it.
  **The webhook route must read the raw request body** (`await request.body()`), not a
  Pydantic model — parsing would not preserve the exact bytes the signature was computed
  over.

## Domain layer

- `src/domain/enums.py`: add `PaymentStatus(StrEnum)`: `PENDING/PAID/CANCELLED/EXPIRED/FAILED`.
- `src/domain/exceptions.py`: add
  - `PaymentNotFoundException(EntityNotFoundException)` → 404
  - `InvalidPaymentStateException(InvalidAttributeException)` → 400
  - `InvalidWebhookSignatureException(AuthenticationException)` → 401
  - `PremiumRequiredException(DomainException)` → **402** (new, dedicated mapping)
- `src/domain/entities/payment.py` — new `Payment` entity, one row per checkout attempt:
  `id: UUID`, `user_id: int`, `order_code: int | None` (DB-assigned on insert — same
  "doesn't exist before the DB assigns it" precedent as `User.id`, since PayOS needs a
  numeric id we cannot safely self-mint without a collision risk), `plan_type: PlanType`,
  `amount: Decimal` (never float, per repo rule), `status: PaymentStatus`,
  `payment_link_id/checkout_url/qr_code: str | None`, `created_at`, `paid_at: datetime | None`.
  - `Payment.create(user_id, plan_type, amount) -> Payment` factory (status=PENDING, order_code=None).
  - `attach_checkout(payment_link_id, checkout_url, qr_code)` — raises `InvalidPaymentStateException` unless PENDING.
  - `mark_paid()` — idempotent no-op if not PENDING (webhook retries).
  - `mark_failed()` — idempotent no-op if not PENDING.
  - `mark_cancelled()` — raises `InvalidPaymentStateException` unless PENDING.
- `src/domain/entities/subscription.py` — add `Subscription.renew(existing, user_id,
  plan_type, price, today) -> Subscription` factory:
  - `start_date` = `today` normally, or `existing.end_date + 1 day` if renewing before
    the current period expires (so early renewal stacks instead of wasting paid time).
  - `end_date` = start + 1 month (calendar-correct via `calendar.monthrange`, clamping
    day-of-month, e.g. Jan 31 + 1 month → Feb 28/29) or + 1 year (clamping Feb 29 → Feb 28
    in a non-leap target year). Pure stdlib (`calendar`, `datetime`) — no new dependency.
  - Reuses `existing.id` if renewing, else mints a new UUID.

## Application layer

- `application/ports/payment_provider.py`:
  ```python
  class PaymentProviderProtocol(Protocol):
      async def create_checkout_link(self, order_code: int, amount: Decimal, description: str,
                                      cancel_url: str, return_url: str) -> CheckoutLinkResult: ...
      async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus: ...
      async def cancel(self, order_code: int, reason: str | None) -> None: ...
      def verify_webhook(self, raw_body: bytes) -> WebhookPayload: ...  # raises InvalidWebhookSignatureException
  ```
  `CheckoutLinkResult`, `ProviderPaymentStatus`, `WebhookPayload` are frozen dataclasses
  next to the port — they translate PayOS's vocabulary (its own `status` strings, its
  `success`/`code` webhook fields) into our `PaymentStatus`, the same isolation the
  chat slice uses for `ChatRole` inside `GeminiChatProvider`.
- `application/ports/payment_repository.py` — `PaymentRepositoryProtocol`:
  `create(payment) -> Payment`, `get_by_order_code(order_code) -> Payment | None`, `update(payment) -> Payment`.
- `application/ports/subscription_repository.py` — `SubscriptionRepositoryProtocol`:
  `get_by_user_id(user_id) -> Subscription | None`, `save(subscription) -> Subscription`
  (upsert keyed on `user_id`, matching the table's `uq_subscriptions_user` constraint).
- `application/dtos/payment.py` — `CheckoutOutputDTO`, `PaymentOutputDTO` (frozen dataclasses, `from_entity`).
- `application/dtos/subscription.py` — `SubscriptionOutputDTO` (frozen dataclass, `from_entity`).
- `application/use_cases/apply_payment_result.py` — **shared helper** (same role as
  `token_pair.py::issue_session`), not a use case class: `async def apply_payment_result(payment, succeeded, payments, subscriptions, users) -> Payment`.
  - No-ops if `payment.status is not PENDING` (idempotent against webhook retries / double reconciliation).
  - On success: `payment.mark_paid()`; `subscriptions.save(Subscription.renew(existing, payment.user_id, payment.plan_type, payment.amount, date.today()))`;
    load the user via `users.get_by_id(payment.user_id)`, set `subscription_tier = PREMIUM`, `users.update(user)`.
  - On failure: `payment.mark_failed()`.
  - Always: `payments.update(payment)`; return it.
- `application/use_cases/create_checkout.py` — `CreateCheckoutUseCase(payments, provider)`:
  price looked up from settings by `plan_type` → `Payment.create(...)` → `payments.create(...)`
  (assigns `order_code`) → `provider.create_checkout_link(...)` → `payment.attach_checkout(...)` → `payments.update(...)`.
- `application/use_cases/handle_payment_webhook.py` — `HandlePaymentWebhookUseCase(payments, provider, subscriptions, users)`:
  `provider.verify_webhook(raw_body)` → look up `Payment` by `order_code` (404 if missing)
  → `apply_payment_result(payment, webhook.success, ...)`.
- `application/use_cases/get_payment_status.py` — `GetPaymentStatusUseCase(payments, provider, subscriptions, users)`:
  look up by `order_code` + ownership check (`payment.user_id == user_id`, else treat as
  not-found — don't leak existence of another user's payment) → if still `PENDING`, ask
  `provider.get_payment_status` and `apply_payment_result` if it's no longer pending
  (this is the fallback for a lost/delayed webhook) → return DTO.
- `application/use_cases/cancel_payment.py` — `CancelPaymentUseCase(payments, provider)`:
  ownership check → must be `PENDING` (else `InvalidPaymentStateException`) → `provider.cancel(...)` → `payment.mark_cancelled()` → `payments.update(...)`.
- `application/use_cases/get_my_subscription.py` — `GetMySubscriptionUseCase(subscriptions)`:
  `execute(user_id) -> SubscriptionOutputDTO | None`.

## Infrastructure layer

- `infrastructure/db/models/payment_model.py` — `PaymentORM(UUIDPrimaryKey, UserOwned, Base)`,
  table `payments`. `order_code: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True, nullable=False)`
  — a DB-native identity column (`Identity()`, the SQLAlchemy/Postgres equivalent of
  autoincrement for a non-PK column), so order codes are assigned atomically with no
  collision risk and no new dependency. `amount: Numeric(12, 0)` (VND has no minor unit).
  `plan_type`/`status` via `enum_column`. `payment_link_id String(64)`, `checkout_url
  String(512)`, `qr_code Text`, `created_at DateTime(timezone=True) server_default=func.now()`,
  `paid_at DateTime(timezone=True) nullable`. `to_domain`/`from_domain` — `from_domain`
  omits `order_code` when `None`, mirroring `UserORM.from_domain`'s `id` handling exactly.
- `infrastructure/db/repositories/payment_repository.py` — `SQLAlchemyPaymentRepository`:
  `create` does add+flush+refresh (to read back the DB-assigned `order_code`, same as
  `SQLAlchemyUserRepository.create`), `get_by_order_code` (select where), `update`.
- `infrastructure/db/repositories/subscription_repository.py` — `SQLAlchemySubscriptionRepository`:
  `get_by_user_id` (select where), `save` (select by `user_id`; update columns in place if
  found, else insert — upsert keyed on the unique constraint, not the PK).
- `infrastructure/payments/payos_provider.py` — `PayOsPaymentProvider(PaymentProviderProtocol)`
  wrapping `payos.AsyncPayOS(client_id, api_key, checksum_key)`. Translates SDK request/response
  objects to/from `CheckoutLinkResult`/`ProviderPaymentStatus`/`WebhookPayload`; catches
  the SDK's own "bad signature" exception (name TBD at implementation) and re-raises
  `InvalidWebhookSignatureException`.
- `infrastructure/config.py` — add, all required (no default → fails closed like the
  OAuth client-id settings):
  `payos_client_id`, `payos_api_key`, `payos_checksum_key`, `payos_return_url`, `payos_cancel_url`
  (frontend/deep-link URLs the user is redirected to after paying — not backend routes),
  and priced-in-VND ints with sane defaults: `payos_monthly_price_vnd = 49_000`,
  `payos_annual_price_vnd = 499_000`.
- `.env.example` — add the six keys above (commented, blank for the required ones).
- `infrastructure/di/repositories.py` — `get_payment_repository`/`PaymentRepositoryDep`,
  `get_subscription_repository`/`SubscriptionRepositoryDep`.
- `infrastructure/di/security.py` — add (same file already hosts `AiChatProviderDep`,
  `FoodVisionProviderDep`, `ImageStorageDep` despite its docstring, so this follows
  existing precedent rather than adding a new module):
  - `_payos_provider()` (`@lru_cache`) + `get_payment_provider()`/`PaymentProviderDep`.
  - `get_current_premium_user(user: CurrentUserDep, subscriptions: SubscriptionRepositoryDep, users: UserRepositoryDep) -> User`:
    loads the user's `Subscription`; if `user.is_premium` but the subscription no longer
    `.covers(date.today())` (lapsed since last check — there is no cron, so this is the
    only place expiry is enforced), lazily reconciles: `subscription.status = EXPIRED`,
    save it, flip `user.subscription_tier = FREE`, `users.update(user)`. Then, if
    `not user.is_premium`, raise `PremiumRequiredException`. Returns the user.
    `CurrentPremiumUserDep = Annotated[User, Depends(get_current_premium_user)]` — nothing
    consumes this yet; a future slice depends on it instead of `CurrentUserDep`.
- `infrastructure/di/use_cases.py` (+ re-export from `di/__init__.py`): providers + `Annotated`
  aliases for `CreateCheckoutUseCase`, `HandlePaymentWebhookUseCase`, `GetPaymentStatusUseCase`,
  `CancelPaymentUseCase`, `GetMySubscriptionUseCase`.
- `pyproject.toml` — add `"payos>=1.1.0"` to `dependencies`.
- Migration `alembic/versions/0009_payments_table.py` — create `payments` table only
  (`subscriptions` already exists from `0002`, no schema change needed there). Follow the
  repo's bare-CHECK-constraint-name convention for the two new enums.

## Adapters layer

- `adapters/schemas/payment_schemas.py` (all `CamelModel`): `CreateCheckoutRequest{planType}`,
  `CheckoutResponse{orderCode, checkoutUrl, qrCode, amount, planType, status}`,
  `PaymentResponse{orderCode, status, amount, planType, paidAt, createdAt}`,
  `CancelPaymentRequest{cancellationReason: str | None}`.
- `adapters/schemas/subscription_schemas.py`: `SubscriptionResponse{planType, status, startDate, endDate}`,
  `MySubscriptionResponse{hasActiveSubscription: bool, subscription: SubscriptionResponse | None}`
  (no subscription is normal free-tier state, not a 404).
- `adapters/controllers/payment_controller.py`, `APIRouter(prefix="/payments")`, DI only
  from `src.infrastructure.di`:
  - `POST /payments/checkout` (`CurrentUserDep`)
  - `GET /payments/{order_code}` (`CurrentUserDep`)
  - `POST /payments/{order_code}/cancel` (`CurrentUserDep`)
  - `POST /payments/webhook` — **no** auth dependency (PayOS has no bearer token); reads
    `await request.body()` raw, passes to the use case. Protected purely by signature
    verification inside the use case.
- `adapters/controllers/subscription_controller.py`, `APIRouter(prefix="/subscriptions")`:
  `GET /subscriptions/me` (`CurrentUserDep`).
- `src/main.py` — register both routers.
- `adapters/exception_handlers.py` — add to `EXCEPTION_STATUS`:
  `(InvalidWebhookSignatureException, 401)` (or falls under `AuthenticationException`'s
  existing 401 entry via MRO — either is fine, prefer being explicit), `(PremiumRequiredException, 402)`.
  `PaymentNotFoundException`/`InvalidPaymentStateException` fall under existing
  `EntityNotFoundException`(404)/`InvalidAttributeException`(400) base entries — no new tuples needed.

## Testing

- `tests/unit/test_payment_use_cases.py` — in-memory `FakePaymentRepository`,
  `FakeSubscriptionRepository`, `FakePaymentProvider` (scripted, same shape as
  `FakeAiChatProvider` in `tests/api/conftest.py`). Cover: checkout happy path; webhook
  success → `Subscription` created + `User.subscription_tier` flips to PREMIUM; webhook
  replay is a no-op (idempotency); invalid signature raises; early-renewal stacks
  `start_date` off the existing `end_date`; monthly/annual date math including a Jan
  31 → Feb clamp and a Feb 29 leap-year case; reconciliation path in
  `GetPaymentStatusUseCase`; cancel rejects a non-PENDING payment.
- `tests/api/test_payment_endpoints.py` — mirrors `test_food_analysis_endpoints.py`:
  override DI with fakes; checkout returns a checkout URL; webhook with a
  provider-verified vs. rejected signature; `GET /subscriptions/me` before/after a
  simulated payment; a smoke test that `CurrentPremiumUserDep` (used on a throwaway test
  route registered only in the test, since nothing production uses it yet) 402s a
  free-tier user and passes a premium one.
- `tests/integration/test_payment_repository.py` — real DB: confirms `order_code`
  actually gets a unique, DB-assigned value on insert (the one piece of behavior that
  can't be exercised by a fake).

## Open items to verify at implementation time (not blocking, but call out explicitly)

- Exact method/exception names on the installed `payos` SDK version — the design above
  names them by their most likely shape from public docs; adapt `PayOsPaymentProvider`
  to whatever `import payos; help(...)` / its type stubs actually show once added via `uv add payos`.
- Whether PayOS expects any particular JSON body in the webhook's 200 response — default
  to a minimal `{"code": "00"}` ack unless the SDK/docs say otherwise.

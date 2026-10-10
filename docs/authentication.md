# Authentication in FoodFenBE

A walk-through of how login works in this project, written for someone who has
not built auth with FastAPI before. It covers **what was installed**, **the
concepts**, **how our code is wired**, and **the exact request/response flow**
for every endpoint.

Endpoint names, field names (camelCase), and response shapes follow a
front-end API contract — a real, already-implemented mobile client, not a
design we chose ourselves. Where this doc and that contract would disagree,
the contract wins; a few endpoints here (`verify-email`,
`resend-verification`, `reset-password`) are extras it doesn't require.

---

## 1. The libraries we added

| Package | Version | What it does | Why this one |
|---|---|---|---|
| **PyJWT** (`pyjwt`) | `>=2.9` | Encode / decode / verify JSON Web Tokens | The plain, well-maintained JWT library. No framework baggage. |
| **bcrypt** | `>=4.2` | Hash and verify passwords | The password-hashing standard. We call it directly — no `passlib` wrapper, which is heavy and semi-abandoned. |
| **python-multipart** | `>=0.0.12` | Parses form-encoded request bodies | Required by `OAuth2PasswordRequestForm` (§4.8) — Swagger's login form posts form data, not JSON. |

All three are in `pyproject.toml` under `[project].dependencies`. Install with `uv sync`.

Nothing else was needed. FastAPI ships `OAuth2PasswordBearer` and
`BackgroundTasks`; email goes out through the standard-library `smtplib` +
`email.message`; camelCase JSON comes from Pydantic's own
`alias_generators.to_camel`.

---

## 2. Concepts you need first

### 2.1 Password hashing (not encryption)

We never store the user's password. We store a **bcrypt hash** of it:

```
"s3cret-pass"  --bcrypt-->  "$2b$12$Q7...long...string"
```

- Hashing is **one-way**: you cannot get the password back from the hash.
- bcrypt is **slow on purpose** (cost factor 12, roughly 250 ms per hash). That
  makes brute-forcing a stolen hash database expensive.
- Every hash embeds a random **salt**, so two users with the same password still
  get different hashes.

To check a login we hash the *submitted* password with the *stored* salt and
compare. bcrypt's `checkpw` does that in one call.

### 2.2 What a JWT is

A JWT (JSON Web Token) is a string with three dot-separated parts:

```
eyJhbGciOiJIUzI1NiJ9  .  eyJzdWIiOiI0MTZi...  .  7dAjP4ouEK0PaVITSstPr...
   header (base64)          payload (base64)        signature
```

- The **payload** is just base64 — **anyone can read it**. Never put secrets there.
- The **signature** is `HMAC-SHA256(header + "." + payload, JWT_SECRET)`. Only
  someone who knows `JWT_SECRET` can produce a valid one.

So a JWT is **tamper-proof, not secret**. If a client edits the payload (say,
swaps in another user's id), the signature stops matching and the server rejects
the token.

Our payload (`src/infrastructure/security/jwt_service.py`):

```json
{
  "sub":  "1",
  "type": "access",
  "iat":  1788446042,
  "exp":  1788447842,
  "jti":  "8bf075d8-..."
}
```

| claim | meaning |
|---|---|
| `sub` | the user's id (a plain integer, as a string — JWT requires `sub` to be a string) |
| `type` | `"access"`, `"refresh"`, `"email_verification"`, or `"password_reset"` — stops one being used in place of another |
| `iat` | issued-at, unix seconds |
| `exp` | expires-at — PyJWT refuses the token automatically once this passes |
| `jti` | *refresh tokens only* — a unique id for this token, used for revocation |

### 2.3 Why *two* tokens: access + refresh

| | Access token | Refresh token |
|---|---|---|
| Lifetime | **30 minutes** | **30 days** |
| Sent on | every API request | only to `POST /auth/refresh` |
| Stored server-side? | **no** — pure JWT | **yes** — one row in `refresh_tokens` |
| If stolen | attacker has ~30 min | we can **revoke** it instantly |

The access token is short-lived, so a leak is limited in time. But you don't want
users re-entering a password every 30 minutes, so the long-lived refresh token
can mint fresh access tokens silently.

The catch with a plain JWT: it stays valid until `exp` no matter what — there is
no "log out" for a stateless token. We solve that for the refresh token by
**tracking it in the database** (next section).

---

## 3. The `refresh_tokens` table

Created by migration `0003_refresh_tokens.py`. One row per issued refresh token:

| column | meaning |
|---|---|
| `id` | row primary key (UUID — see §4.0 on why `users` is the one table that differs) |
| `user_id` | FK to `users`, `ON DELETE CASCADE` (an integer — see §4.0) |
| `jti` | the `jti` claim from the JWT (unique) |
| `expires_at` | a real timestamp copy of the JWT's `exp` |
| `revoked_at` | `NULL` = still usable; a timestamp = killed |
| `created_at` | when it was issued |

**A refresh token is accepted only if all of these hold:**

1. its JWT signature verifies and it is not past `exp` (PyJWT checks this), and
2. a row with that `jti` exists, and
3. that row's `revoked_at` is `NULL`, and
4. `now < expires_at`.

This is an **allowlist**: the row must be present and alive. Consequences:

- **Sign-out** = set `revoked_at = now` on the row. The JWT is now dead even though
  its `exp` is weeks away.
- **Rotation** (see §4.3) = on every refresh, revoke the row you just used and
  insert a new one. A refresh token is **single-use**.

The access token is deliberately *not* in this table — it is stateless and simply
expires.

---

## 4. The endpoints and their exact flow

Everything is under `/auth`, except the extra `GET /users/{id}`. There is one
more session-establishing endpoint not detailed here —
`POST /auth/social` (Google/Apple sign-in) — because it's involved enough to
get its own page: see [`social-sign-in.md`](./social-sign-in.md). It returns
the identical `AuthSession` shape as sign-up/sign-in/refresh below.

### 4.0 Two contract quirks worth knowing up front

- **`User.id` is a plain integer**, not a UUID — the front-end contract types it
  as a number. `users` is the *only* table built that way (`IntPrimaryKey`
  mixin, Postgres `SERIAL`/identity); every other table in the app keeps a UUID
  PK. That means `User.id` doesn't exist until the row is actually inserted
  (`User.create()` leaves it `None`) — unlike every other entity, which mints
  its own UUID up front and never needs the database to tell it its id.
- **The wire format is camelCase**: `accessToken`, `refreshToken`, `expiresAt`,
  `displayName`, `weeklyRateKg`, etc. Python stays snake_case internally;
  `src/adapters/schemas/base.py::CamelModel` (a Pydantic `alias_generator`)
  translates both directions. `docs/authentication.md` below always shows the
  wire (camelCase) shape.
- **Failure bodies** are `{"message"?: str, "error"?: str, "errors"?: {field:
  str}}` — never FastAPI's default `{"detail": ...}`. Every domain exception
  and even Pydantic's own request-validation errors are reshaped to this by
  `src/adapters/exception_handlers.py`.

### 4.1 `POST /auth/sign-up` — no auth required

Unlike a design where signup blocks until email verification, **this returns a
live, usable session immediately** — the contract's client has no "please
verify your email" screen, so there is nothing to block on.

```
Request:
  { "email": "u@example.com", "password": "s3cret-pass", "displayName": "U" }
  (displayName is optional)

Response 200:
  { "accessToken": "eyJ...", "refreshToken": "eyJ...", "expiresAt": 1788447842000,
    "user": { "id": 1, "email": "u@example.com", "displayName": "U", "gender": null,
              "birthYear": null, "unitSystem": "metric", "height": null,
              "weightCurrent": null, "weightGoal": null, "activityLevel": null,
              "dietType": null, "calorieCalcMode": "auto", "calorieLeftMode": null,
              "subscriptionTier": "free", "role": "user", "weeklyRateKg": null,
              "createdAt": "2026-09-19T11:49:13Z" } }
```

`expiresAt` is **epoch milliseconds** (not seconds, not ISO) — the contract's
type, and what `Date.now()` compares against directly.

`role` is `user` | `admin`; `GET /auth/me` additionally returns `restaurantId` (null when the user owns no restaurant) — see `docs/marketplace.md`.

```
client                 RegisterUserUseCase                bcrypt / PyJWT       DB
  | email,pw,name -->     |
  |                       | User.validate_password_strength(pw)  (>= 8 chars, <= 72 bytes)
  |                       | hash = bcrypt.hashpw(pw) --------> "$2b$12$..."
  |                       | User.create(...) -> id=None, email_verified_at=None
  |                       | users.get_by_email() ---------------------------> SELECT
  |                       |   (raise -> HTTP 400, errors.email, if it exists)
  |                       | users.create(user) ----------------------------> INSERT, id assigned
  |                       | issue_session(user) — mints access+refresh, stores refresh row
  |                       | ALSO: token = JWT(sub=id, type=email_verification, 24h)
  |                       | return RegisterResultDTO(session, verification_token)
  | <-- 200 + session ----|
        |
   controller schedules  background_tasks.add_task(notifier.send_verification, ...)
        |                 (runs AFTER the response is sent — a slow/down mail
        |                  server can never block or fail sign-up)
   notifier -> SMTP: "click https://APP_BASE_URL/auth/verify-email?token=<jwt>"
```

A duplicate email is a **`400`** with a field-keyed body, not a generic error:

```json
{ "message": "user with email 'u@example.com' already exists",
  "errors": { "email": "user with email 'u@example.com' already exists" } }
```

### 4.2 `POST /auth/sign-in` — no auth required

```
Request:  { "email": "u@example.com", "password": "s3cret-pass" }
Response 200: the same session shape as sign-up
```

```
LoginUseCase:
  user = users.get_by_email(email.lower())
  if user is None
     or user.password_hash is None
     or not bcrypt.checkpw(password, user.password_hash):
         raise InvalidCredentialsException        -> HTTP 401
  if not user.is_active:
         raise InvalidCredentialsException        -> HTTP 401
  return issue_session(user)   # same helper sign-up and refresh use
```

**"no such user" and "wrong password" return the same 401 message** —
deliberate, so a client can't use this endpoint to probe which emails have
accounts. There is no email-verified check here at all: verification never
gates anything.

### 4.3 `POST /auth/refresh` — no auth required — the rotation dance

```
Request:      { "refreshToken": "eyJ...(the refresh JWT)" }
Response 200: a BRAND NEW session — tokens *and* the user, same as sign-in
```

```
RefreshTokenUseCase:
  claims = tokens.read_refresh_token(refreshToken)
      # PyJWT verifies signature + exp; we also check type == "refresh"
      # -> InvalidTokenException (401) if any of that fails
  row = refresh_tokens.get_by_jti(claims.jti)
  if row is None or not row.is_active(now):       # revoked or expired row
      raise InvalidTokenException                 -> HTTP 401
  row.revoke(now)                                 # the presented token is now spent
  refresh_tokens.revoke(row) ---------------------> UPDATE refresh_tokens SET revoked_at = now
  user = users.get_by_id(claims.user_id)          # -> 404 if the account is gone
  return issue_session(user)                      # inserts a NEW jti row
```

Because the old row is revoked, **replaying the same refresh token a second
time returns 401**. The client must always use the newest refresh token it
received. The contract requires the response to include the `user` even
though a refresh is not a login — this is the same reason `issue_session` is
shared by all three endpoints.

### 4.4 `POST /auth/sign-out` — **requires** a valid access token

Unlike sign-up/sign-in/refresh, sign-out is *not* in the contract's
`skipAuth` list — a bearer token is required in addition to the refresh token
in the body (route-level `dependencies=[Depends(get_current_user)]`, the
resulting user isn't otherwise used).

```
Request:      Authorization: Bearer <access token>
              { "refreshToken": "eyJ..." }
Response 204  (no body — the contract says the client ignores it anyway)
```

```
LogoutUseCase:
  try:  claims = tokens.read_refresh_token(refreshToken)
  except InvalidTokenException:  return           # already unusable -> nothing to do
  row = refresh_tokens.get_by_jti(claims.jti)
  if row and row.revoked_at is None:
      row.revoke(now)
      refresh_tokens.revoke(row) -----------------> UPDATE ... SET revoked_at = now
```

Idempotent: calling it twice, or with a garbage refresh token (as long as the
access token is valid), still returns 204.

> The **access token** used to call this still works until its own 30-minute
> `exp` — sign-out only kills the refresh token. Instantly killing the access
> token too would need a denylist cache (e.g. Redis); not built here, see §8.

### 4.5 `POST /auth/password-reset` — no auth required

```
Request:  { "email": "u@example.com" }
Response 202 (any 2xx; the contract says the client ignores the body)
  { "message": "If that address has an account, a reset link is on its way." }
```

```
RequestPasswordResetUseCase:
  user = users.get_by_email(email.lower())
  if user is None:
      return None                                 # nothing to send
  token = JWT(sub=user.id, type=password_reset, 1h)
  return VerificationDispatchDTO(email, name, token)
```

**Always answers the same way regardless of whether the email is
registered** — same enumeration-safe pattern as sign-up's duplicate-email
check would otherwise leak, and as `resend-verification` below. The email (if
sent) is scheduled as a `BackgroundTask`, same mechanism as sign-up's
verification email.

The contract only documents *requesting* a reset — there is no "confirm"
endpoint in it (a reset is presumably meant to complete on a web page, not in
the app). We still built one, since a request with no way to complete it does
nothing:

**`POST /auth/reset-password`** (extra, not in the contract) —
`{ "token": "...", "newPassword": "..." }` → verifies the `password_reset`
JWT, applies `User.validate_password_strength`, updates the hash. `200` on
success, `401` on a bad/expired token.

### 4.6 `GET /auth/me` — requires a valid access token

```
Response 200: the User object shown in §4.1, unwrapped (no session envelope)
```

Used to refresh the client's copy of the account's server-side profile
without re-authenticating.

### 4.7 Calling a protected endpoint

```
GET /auth/me
Authorization: Bearer eyJ...(the access JWT)
```

```
get_current_user   (src/infrastructure/di/security.py):
  token = OAuth2PasswordBearer(tokenUrl="auth/token")   # reads "Authorization: Bearer X"
  if token is None:            raise InvalidTokenException          -> 401
  user_id = tokens.read_access_token(token)
      # PyJWT verifies signature + exp; we check type == "access"
      # -> InvalidTokenException (401) if bad / expired / wrong type
  user = users.get_by_id(user_id)
  if user is None or not user.is_active:  raise InvalidTokenException  -> 401
  return user                                     # the domain User entity
```

Any route can require login in one of two ways:

```python
# the handler needs the user object:
@router.get("/me")
async def me(current_user: CurrentUserDep) -> UserResponse: ...

# the handler only needs "must be logged in" (e.g. sign-out):
@router.post("/sign-out", dependencies=[Depends(get_current_user)])
async def sign_out(...): ...
```

A failed auth always returns **`401` plus the header `WWW-Authenticate: Bearer`**
(the HTTP-standard way to say "this endpoint needs a bearer token").

### 4.8 Logging in from Swagger UI (`/docs`)

`get_current_user` depends on `OAuth2PasswordBearer`, not the plainer `HTTPBearer` —
functionally identical (it still just reads `Authorization: Bearer <token>`), but
it makes FastAPI declare an OAuth2 "password flow" security scheme in the OpenAPI
document, and Swagger UI renders that as a real login form behind the
**Authorize** button, instead of a bare "paste your token" field:

```
1. Click Authorize -> enter your email as "username" and your password
2. Swagger POSTs (form-encoded) to tokenUrl = "auth/token"
3. It stores the returned accessToken and attaches
   "Authorization: Bearer <token>" to every "Try it out" call from then on
```

`POST /auth/token` exists only to be that form's target — it takes the
`OAuth2PasswordRequestForm` shape the OAuth2 spec requires (`username`,
`password`, form-encoded) rather than the JSON `{email, password}` of the real
`POST /auth/sign-in`, and calls the identical `LoginUseCase`. It is marked
`include_in_schema=False` so it doesn't appear as a second, confusing login
endpoint in the docs. Needs the `python-multipart` package (anything parsing a
form body does).

---

## 5. Where each piece lives (Clean Architecture)

The project keeps framework code out of the core. Auth is spread across the four
layers on purpose:

```
src/domain/                        (pure Python, no libraries)
  entities/user.py                 id: int | None, email_verified_at, verify_email(now),
                                   validate_password_strength()
  entities/refresh_token.py        RefreshToken: is_active(now), revoke(now)
  entities/social_identity.py      SocialIdentity — links (provider, subject) -> user_id
  exceptions.py                    AuthenticationException
                                     |- InvalidCredentialsException  -> 401
                                     |- InvalidTokenException        -> 401
                                   WeakPasswordException              -> 400

src/application/                   (orchestration, still no libraries)
  dtos/auth.py                     AuthSessionDTO, RegisterResultDTO, RefreshClaims, ...
  dtos/user.py                     UserOutputDTO — mirrors the contract's User shape
  ports/password_hasher.py         PasswordHasherProtocol   (interface only)
  ports/token_service.py           TokenServiceProtocol     (interface only)
  ports/refresh_token_repository.py
  ports/social_identity_repository.py    ports/social_identity_verifier.py
  ports/email_verification_notifier.py   EmailVerificationNotifierProtocol
                                   (also carries send_password_reset)
  use_cases/register_user.py       creates the user, returns RegisterResultDTO
  use_cases/login.py               returns AuthSessionDTO directly — no gate
  use_cases/refresh_token.py       also fetches the user (contract needs it in the response)
  use_cases/logout.py
  use_cases/verify_email.py        resend_verification.py     (extras)
  use_cases/request_password_reset.py   reset_password.py     (extras)
  use_cases/social_sign_in.py      resolve/create/link an account — see social-sign-in.md
  use_cases/token_pair.py          issue_session() — shared by every session-issuing use case

src/infrastructure/                (the real libraries live here)
  security/password_hasher.py      BcryptPasswordHasher   -> implements the port
  security/jwt_service.py          JwtTokenService (PyJWT) -> implements the port
                                   4 token types: access, refresh, email_verification, password_reset
  security/social_identity_verifier.py   JwtSocialIdentityVerifier — PyJWKClient, no new
                                   heavyweight dependency (no google-auth)
  db/mixins.py                     IntPrimaryKey (users only) vs UUIDPrimaryKey (everything else)
  db/models/user_model.py          UserORM(IntPrimaryKey, Base)
  db/models/refresh_token_model.py RefreshTokenORM (SQLAlchemy) + to_/from_domain
  db/models/social_identity_model.py     SocialIdentityORM
  db/repositories/refresh_token_repository.py
  db/repositories/social_identity_repository.py
  notifications/email_verification_notifier.py   Logging + Smtp notifiers (both emails)
  di/database.py  di/repositories.py  di/security.py  di/notifications.py
  di/use_cases.py                  every get_*_use_case provider, one file, all slices
  config.py                        JWT + email settings

src/adapters/                      (HTTP surface)
  schemas/base.py                  CamelModel — the camelCase <-> snake_case translation
  schemas/auth_schemas.py          SignUpRequest, SignInRequest, AuthSessionResponse, ...
  schemas/user_schemas.py          UserResponse.from_dto() — maps UserOutputDTO.name -> displayName
  controllers/auth_controller.py   the contract's 7 routes + 3 extras + hidden /auth/token
  exception_handlers.py            DomainException / RequestValidationError -> {message, errors}

src/main.py                        app factory only: routers + lifespan + calls
                                   register_exception_handlers(app)
```

**Why the `Protocol` ports?** The use cases say "I need something that can
`hash()` and `verify()`" without knowing it is bcrypt. Tests pass in a fake hasher
and a fake token service — no bcrypt, no PyJWT, no DB — see
`tests/unit/test_auth_use_cases.py`. The real classes are assembled only in
`di/use_cases.py`; controllers only ever import the resulting `Annotated` aliases
from `src.infrastructure.di`.

---

## 6. Configuration

`src/infrastructure/config.py` reads these from the environment / `.env`:

| setting | env var | default | notes |
|---|---|---|---|
| `jwt_secret` | `JWT_SECRET` | `dev-insecure-secret-change-me-in-production-only` | **Change in production.** `main.lifespan` logs a warning if the default is still in use. |
| `jwt_algorithm` | `JWT_ALGORITHM` | `HS256` | HMAC with a shared secret. |
| `access_token_expire_minutes` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `refresh_token_expire_days` | `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | |
| `verification_token_expire_hours` | `VERIFICATION_TOKEN_EXPIRE_HOURS` | `24` | |
| `password_reset_token_expire_minutes` | `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `60` | shorter than verification — a leaked reset link is more damaging |
| `app_base_url` | `APP_BASE_URL` | `http://localhost:8000` (set it to the web client, e.g. `http://localhost:5173`) | origin of the web client (FoodFenWeb); email links land on its `/auth/verify-email` and `/auth/reset-password` pages |
| `email_backend` | `EMAIL_BACKEND` | `console` | `console` logs the link; `smtp` sends it |
| `email_from` | `EMAIL_FROM` | `no-reply@foodfen.local` | |
| `smtp_host` / `smtp_port` | `SMTP_HOST` / `SMTP_PORT` | `localhost` / `1025` | |
| `smtp_username` / `smtp_password` | `SMTP_USERNAME` / `SMTP_PASSWORD` | empty | omit to skip AUTH |
| `smtp_starttls` | `SMTP_STARTTLS` | `true` | |

Generate a real secret:

```
openssl rand -hex 32
```

`HS256` uses one secret for both signing and verifying. If you later need a
separate service to verify tokens without being able to mint them, switch to
`RS256` (a private key signs, a public key verifies) — only `jwt_service.py`
changes.

---

## 7. Try it yourself

With the database up (`docker compose up -d`) and migrations applied
(`uv run alembic upgrade head`), start the API:

```
uv run uvicorn src.main:app --reload
```

Keep `EMAIL_BACKEND=console` (the default) so links print to the uvicorn log
instead of being emailed. Then, in another shell:

```bash
BASE=http://127.0.0.1:8000
CREDS='{"email":"me@example.com","password":"s3cret-pass"}'

# 1. sign-up -> 200, a full session already (no verification needed to use it)
SESSION=$(curl -s -X POST $BASE/auth/sign-up -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"s3cret-pass","displayName":"Me"}')
echo "$SESSION" | python -m json.tool
ACCESS=$(echo "$SESSION"  | python -c "import sys,json;print(json.load(sys.stdin)['accessToken'])")
REFRESH=$(echo "$SESSION" | python -c "import sys,json;print(json.load(sys.stdin)['refreshToken'])")

# 2. protected endpoint, then no token -> 401
curl -s $BASE/auth/me -H "Authorization: Bearer $ACCESS" | python -m json.tool
curl -s -o /dev/null -w 'no token: %{http_code}\n' $BASE/auth/me

# 3. sign-in works right away too (verification never gates it)
curl -s -X POST $BASE/auth/sign-in -H 'Content-Type: application/json' -d "$CREDS" \
  | python -m json.tool

# 4. refresh returns a new session (tokens + user); replaying the old token -> 401
curl -s -X POST $BASE/auth/refresh -H 'Content-Type: application/json' \
  -d "{\"refreshToken\":\"$REFRESH\"}" | python -m json.tool
curl -s -o /dev/null -w 'replay: %{http_code}\n' -X POST $BASE/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refreshToken\":\"$REFRESH\"}"

# 5. sign-out needs the access token too, not just the refresh token
curl -s -o /dev/null -w 'no auth: %{http_code}\n' -X POST $BASE/auth/sign-out \
  -H 'Content-Type: application/json' -d "{\"refreshToken\":\"$REFRESH\"}"

# 6. password-reset always 2xx, whether or not the email exists
curl -s -o /dev/null -w 'reset: %{http_code}\n' -X POST $BASE/auth/password-reset \
  -H 'Content-Type: application/json' -d '{"email":"ghost@example.com"}'
```

Interactive docs with a green **Authorize** button: `http://127.0.0.1:8000/docs`.

---

## 8. Deliberate limitations

| Corner cut | Why it is acceptable now | When to revisit |
|---|---|---|
| Login does not equalise response time when the email is unknown | Network jitter dwarfs the bcrypt timing delta | If login timing becomes a measured concern — add a constant-time dummy verify |
| Replaying a revoked refresh token just fails; it does not revoke the whole token family | MVP; theft detection is a larger feature | Add "on reuse of a revoked `jti`, revoke all of that user's tokens" |
| Sign-out kills only the refresh token, not the paired access token | The access token lives at most 30 minutes | Add a short-lived denylist cache (Redis) keyed by the access token's id |
| A verification/reset email lost after the response (app crash before the background task ran) is never retried | The user can resend / re-request | Move sending to a real task queue (arq / Celery) with retries |
| Old verification tokens stay valid until they naturally expire, even after a resend | Short window (24h), low stakes | Track a `jti` per token if single-use matters |
| A reset token is single-use only via the `stamp` claim (a hash of the current password hash), so re-requesting a reset does not invalidate earlier unused links | Each link still dies on first use and after 1h | Track a `jti` per reset token |
| No account lockout after repeated failed logins | Out of scope for this slice | Its own slice, same pattern as everything else here |
| Migration `0005` (UUID -> int user ids) truncates all user data | No production data existed yet | N/A — a one-time pre-launch migration, not a pattern to repeat |

These are marked with `ponytail:` comments at the relevant spots in the code.

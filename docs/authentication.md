# Authentication in FoodFenBE

A walk-through of how login works in this project, written for someone who has
not built auth with FastAPI before. It covers **what was installed**, **the
concepts**, **how our code is wired**, and **the exact request/response flow**
for every endpoint.

---

## 1. The two libraries we added

| Package | Version | What it does | Why this one |
|---|---|---|---|
| **PyJWT** (`pyjwt`) | `>=2.9` | Encode / decode / verify JSON Web Tokens | The plain, well-maintained JWT library. No framework baggage. |
| **bcrypt** | `>=4.2` | Hash and verify passwords | The password-hashing standard. We call it directly — no `passlib` wrapper, which is heavy and semi-abandoned. |

Both are in `pyproject.toml` under `[project].dependencies`. Install with `uv sync`.

Nothing else was needed. FastAPI ships the `HTTPBearer` helper and
`BackgroundTasks`; email goes out through the standard-library `smtplib` +
`email.message`.

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
  "sub":  "416bbbb9-dbd7-49a4-a7cc-78e3ae22a589",
  "type": "access",
  "iat":  1788446042,
  "exp":  1788447842,
  "jti":  "8bf075d8-..."
}
```

| claim | meaning |
|---|---|
| `sub` | the user's UUID ("subject") |
| `type` | `"access"` or `"refresh"` — stops one being used in place of the other |
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
| `id` | row primary key |
| `user_id` | FK to `users`, `ON DELETE CASCADE` |
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

- **Logout** = set `revoked_at = now` on the row. The JWT is now dead even though
  its `exp` is weeks away.
- **Rotation** (see 4.4) = on every refresh, revoke the row you just used and
  insert a new one. A refresh token is **single-use**.

The access token is deliberately *not* in this table — it is stateless and simply
expires.

---

## 4. The endpoints and their exact flow

Everything is under `/auth`, except the protected example `GET /users/{id}`.

### 4.1 `POST /auth/register`

The account is created **inactive**: no tokens come back, and login is blocked
until the email is confirmed.

```
Request:
  { "email": "u@example.com", "password": "s3cret-pass", "name": "U" }

Response 201:
  { "detail": "Account created. Check your email to confirm your address." }
```

```
client            RegisterUserUseCase             bcrypt / PyJWT       DB
  | email,pw,name -> |
  |                  | User.validate_password_strength(pw)   (>= 8 chars, <= 72 bytes)
  |                  | hash = bcrypt.hashpw(pw) --------> "$2b$12$..."
  |                  | User.create(...)  -> email_verified_at = None
  |                  | users.get_by_email()  --------------------------> SELECT
  |                  |   (raise -> HTTP 409 if it already exists)
  |                  | users.create(user)  ---------------------------> INSERT users
  |                  | token = JWT(sub=id, type=email_verification, 24h)
  |                  | return VerificationDispatchDTO(email, name, token)
  | <-- 201 + msg ---|
        |
   controller schedules  background_tasks.add_task(notifier.send_verification, ...)
        |                 (runs AFTER the response is sent)
   notifier -> SMTP: "click https://APP_BASE_URL/auth/verify-email?token=<jwt>"
```

No refresh-token row is created here — that only happens at login, once the
account is verified.

### 4.2 `POST /auth/login`

```
Request:      { "email": "u@example.com", "password": "s3cret-pass" }
Response 200: { "access_token": "eyJ...", "refresh_token": "eyJ...",
                "token_type": "bearer", "expires_in": 1799 }
```

```
LoginUseCase:
  user = users.get_by_email(email.lower())
  if user is None
     or user.password_hash is None
     or not bcrypt.checkpw(password, user.password_hash):
         raise InvalidCredentialsException        -> HTTP 401
  if user.email_verified_at is None:
         raise EmailNotVerifiedException          -> HTTP 403
  if not user.is_active:
         raise InvalidCredentialsException        -> HTTP 401
  return issue_token_pair(user.id)  # mints the access + refresh pair, stores the refresh row
```

`expires_in` is the seconds until the **access** token expires (~1800), so a
mobile app knows when to call `/auth/refresh`.

Two deliberate points:
- **"no such user" and "wrong password" return the same 401 message** — stops an
  attacker probing which emails have accounts.
- **Unverified is a distinct `403`**, not a `401` — the password was right, so the
  client can show a "resend confirmation email" screen instead of "check your
  password".

### 4.3 Email verification

**`GET /auth/verify-email?token=<jwt>`** — the link from the email.

```
VerifyEmailUseCase:
  user_id = read_verification_token(token)     # PyJWT sig + exp; type must be
                                               # "email_verification"
                                               # -> InvalidTokenException (401) otherwise
  user = users.get_by_id(user_id)              # -> 404 if the account is gone
  if user.is_email_verified:  return           # idempotent: clicking twice is fine
  user.verify_email(now)                        # sets email_verified_at
  users.update(user)  ------------------------> UPDATE users SET email_verified_at = now
  -> 200 { "detail": "Email confirmed. You can now log in." }
```

It is a `GET` so the link works straight from a mail client. A link-scanning
proxy that pre-fetches it would verify the address early — harmless here, since
confirming the real owner's email is the whole goal.

**`POST /auth/resend-verification`** — body `{ "email": "..." }`.

```
ResendVerificationUseCase:
  user = users.get_by_email(email.lower())
  if user is None or user.is_email_verified:
      return None                               # nothing to do
  return VerificationDispatchDTO(email, name, new_token)
```

The controller schedules a background send when the use case returns a dispatch,
and **always answers `202` with the same message** — so the response never
reveals whether an address is registered or already confirmed.

### 4.4 `POST /auth/refresh` — the rotation dance

```
Request:      { "refresh_token": "eyJ...(the refresh JWT)" }
Response 200: a BRAND NEW token pair
```

```
RefreshTokenUseCase:
  claims = tokens.read_refresh_token(refresh_token)
      # PyJWT verifies signature + exp; we also check type == "refresh"
      # -> InvalidTokenException (401) if any of that fails
  row = refresh_tokens.get_by_jti(claims.jti)
  if row is None or not row.is_active(now):       # revoked or expired row
      raise InvalidTokenException                 -> HTTP 401
  row.revoke(now)                                 # the presented token is now spent
  refresh_tokens.revoke(row) ---------------------> UPDATE refresh_tokens SET revoked_at = now
  return issue_token_pair(claims.user_id)         # inserts a NEW jti row
```

Because the old row is revoked, **replaying the same refresh token a second time
returns 401**. The client must always use the newest refresh token it received.

### 4.5 `POST /auth/logout`

```
Request:      { "refresh_token": "eyJ..." }
Response 204  (no body)
```

```
LogoutUseCase:
  try:  claims = tokens.read_refresh_token(refresh_token)
  except InvalidTokenException:  return           # already unusable -> nothing to do
  row = refresh_tokens.get_by_jti(claims.jti)
  if row and row.revoked_at is None:
      row.revoke(now)
      refresh_tokens.revoke(row) -----------------> UPDATE ... SET revoked_at = now
```

Idempotent: calling it twice, or with a garbage token, still returns 204. After
logout, `/auth/refresh` with that token returns 401.

> The **access token** issued alongside it still works until its 30-minute `exp`.
> Killing the access token instantly too would need a denylist cache (e.g. Redis)
> — not built here, listed under limitations.

### 4.6 Calling a protected endpoint

Every request to a protected route carries the access token in a header:

```
GET /auth/me
Authorization: Bearer eyJ...(the access JWT)
```

```
get_current_user   (src/infrastructure/di/security.py):
  creds = HTTPBearer(auto_error=False)            # reads "Authorization: Bearer X"
  if creds is None:            raise InvalidTokenException          -> 401
  user_id = tokens.read_access_token(creds.credentials)
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

# the handler only needs "must be logged in":
router = APIRouter(prefix="/users", dependencies=[Depends(get_current_user)])
```

A failed auth always returns **`401` plus the header `WWW-Authenticate: Bearer`**
(the HTTP-standard way to say "this endpoint needs a bearer token").

---

## 5. Where each piece lives (Clean Architecture)

The project keeps framework code out of the core. Auth is spread across the four
layers on purpose:

```
src/domain/                        (pure Python, no libraries)
  entities/user.py                 User.validate_password_strength()
  entities/refresh_token.py        RefreshToken: is_active(now), revoke(now)
  exceptions.py                    AuthenticationException
                                     |- InvalidCredentialsException  -> 401
                                     |- InvalidTokenException        -> 401
                                   EmailNotVerifiedException          -> 403
                                   WeakPasswordException              -> 400
  entities/user.py                 email_verified_at, verify_email(now)

src/application/                   (orchestration, still no libraries)
  dtos/auth.py                     RegisterInputDTO, LoginInputDTO, TokenPairDTO, ...
  ports/password_hasher.py         PasswordHasherProtocol   (interface only)
  ports/token_service.py           TokenServiceProtocol     (interface only)
  ports/refresh_token_repository.py
  ports/email_verification_notifier.py   EmailVerificationNotifierProtocol
  use_cases/register_user.py       creates the user, returns a VerificationDispatchDTO
  use_cases/verify_email.py        confirms the address from the token
  use_cases/resend_verification.py
  use_cases/login.py   logout.py   refresh_token.py   token_pair.py

src/infrastructure/                (the real libraries live here)
  security/password_hasher.py      BcryptPasswordHasher   -> implements the port
  security/jwt_service.py          JwtTokenService (PyJWT) -> implements the port
  db/models/refresh_token_model.py RefreshTokenORM (SQLAlchemy) + to_/from_domain
  db/repositories/refresh_token_repository.py
  notifications/email_verification_notifier.py   Logging + Smtp notifiers
  di/database.py  di/repositories.py  di/security.py  di/notifications.py
  config.py                        JWT + email settings

src/adapters/                      (HTTP surface)
  schemas/auth_schemas.py          Pydantic request / response models
  controllers/auth_controller.py   the 7 routes; register/resend also schedule
                                   the verification email as a BackgroundTask

src/main.py                        DomainException type -> HTTP status (400/401/403/404/409)
```

**Why the `Protocol` ports?** The use cases say "I need something that can
`hash()` and `verify()`" without knowing it is bcrypt. Tests pass in a fake hasher
and a fake token service — no bcrypt, no PyJWT, no DB — see
`tests/unit/test_auth_use_cases.py`. The real classes are assembled only in the
`di/` package and the slice `*_deps.py` modules.

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
| `app_base_url` | `APP_BASE_URL` | `http://localhost:8000` | origin used to build the verification link |
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

Keep `EMAIL_BACKEND=console` (the default) so the verification link is printed to
the uvicorn log instead of emailed. Then, in another shell:

```bash
BASE=http://127.0.0.1:8000
CREDS='{"email":"me@example.com","password":"s3cret-pass"}'

# 1. register -> 201, no tokens; the link is now in the uvicorn log
curl -s -X POST $BASE/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"s3cret-pass","name":"Me"}'

# 2. login before verifying -> 403
curl -s -o /dev/null -w 'login pre-verify: %{http_code}\n' \
  -X POST $BASE/auth/login -H 'Content-Type: application/json' -d "$CREDS"

# 3. copy the full verify-email URL from the log line, then:
LINK='paste http://.../auth/verify-email?token=... here'
curl -s "$LINK"                          # -> 200 "Email confirmed."

# 4. login now works -> 200 + token pair
TOKENS=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d "$CREDS")
echo "$TOKENS" | python -m json.tool
ACCESS=$(echo "$TOKENS"  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
REFRESH=$(echo "$TOKENS" | python -c "import sys,json;print(json.load(sys.stdin)['refresh_token'])")

# 5. protected endpoint, then no token -> 401
curl -s $BASE/auth/me -H "Authorization: Bearer $ACCESS" | python -m json.tool
curl -s -o /dev/null -w 'no token: %{http_code}\n' $BASE/auth/me

# 6. refresh, then replay the old one -> 401
curl -s -o /dev/null -w 'replay: %{http_code}\n' -X POST $BASE/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$REFRESH\"}"

# 7. resend (always 202) drops a fresh link in the log
curl -s -o /dev/null -w 'resend: %{http_code}\n' -X POST $BASE/auth/resend-verification \
  -H 'Content-Type: application/json' -d '{"email":"me@example.com"}'
```

Interactive docs with a green **Authorize** button: `http://127.0.0.1:8000/docs`.

---

## 8. Deliberate limitations

| Corner cut | Why it is acceptable now | When to revisit |
|---|---|---|
| Login does not equalise response time when the email is unknown | Network jitter dwarfs the bcrypt timing delta | If login timing becomes a measured concern — add a constant-time dummy verify |
| Replaying a revoked refresh token just fails; it does not revoke the whole token family | MVP; theft detection is a larger feature | Add "on reuse of a revoked `jti`, revoke all of that user's tokens" |
| Logout kills only the refresh token, not the paired access token | The access token lives at most 30 minutes | Add a short-lived denylist cache (Redis) keyed by the access token's id |
| A verification email lost after the response (app crash before the background task ran) is never retried | The user can `POST /auth/resend-verification` | Move sending to a real task queue (arq / Celery) with retries |
| Old verification tokens stay valid until they expire after a resend | 24 h window, low stakes — the link only confirms an address | Track a `jti` per verification token if single-use matters |
| No password reset or account lockout | Out of scope for this slice | Each is its own slice, following the same pattern |

These are marked with `ponytail:` comments at the relevant spots in the code.

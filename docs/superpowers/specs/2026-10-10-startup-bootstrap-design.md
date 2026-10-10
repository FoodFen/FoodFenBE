# Startup bootstrap: admin from env, demo seed behind a flag

Replaces `scripts/make_admin.py` and `scripts/seed_demo.py` (CLI) with work done in `main.lifespan`,
so a fresh local DB is usable after `make migrate && make dev`.

## Decisions

- **Settings** (`src/infrastructure/config.py`, next to the other plain settings):
  `admin_email: str = ""`, `admin_password: str = ""`, `seed_demo: bool = False`.
- **Admin bootstrap** runs on every startup when **both** `admin_email` and `admin_password` are set
  (either empty → skip silently):
  - no user with that email (case-insensitive, same lookup as `get_by_email`) → create via
    `User.create(email, password_hash=BcryptPasswordHasher().hash(pw))`, role `ADMIN`.
    Run `User.validate_password_strength(pw)` first: a weak password fails startup loudly, never a
    weak admin.
  - user exists, not admin → set role `ADMIN`. **Never touch the password** of an existing account.
  - user exists, already admin → nothing.
- **Demo seed** runs on startup only when `seed_demo` is true. Same data and logic as today's
  `scripts/seed_demo.py::run` (non-remove branch): per-owner idempotent by
  `demo-owner-{i}@foodfen.invalid`, so restarts never duplicate. Default off: prod's restaurants
  table is empty, and an "if empty then seed" rule would put fake restaurants on prod.
- Both run in one session from `SessionLocal`, committed, after the existing `SELECT 1` in
  `lifespan`. Log one line per action via the module logger (`configure_logging()` logger) — never
  log the password.
- **Deleted**: `scripts/` entirely (`__init__.py`, `_cli.py`, `make_admin.py`, `seed_demo.py`) and
  `tests/integration/test_ops_scripts.py`. Lost on purpose: `--revoke`, `--remove`, `--env-file`
  (local: reset the docker DB).

## Files

- new `src/infrastructure/db/bootstrap.py`: `async def ensure_admin(session, email, password)`,
  `async def seed_demo(session)` (the `DEMO` table moves here), and
  `async def bootstrap(session_factory=SessionLocal)` that reads `settings` and calls them.
  Use existing repositories (`SQLAlchemyUserRepository`, `SQLAlchemyRestaurantRepository`) and
  entity methods; touch the ORM directly only where the repo has no method (e.g. setting role).
- `src/main.py`: `await bootstrap()` in `lifespan`.
- `src/infrastructure/config.py`: three settings.
- `.env.example`: the three keys, commented, with `SEED_DEMO=false`.
- new `tests/integration/test_bootstrap.py` replaces `test_ops_scripts.py` (reuse its session
  fixture pattern).

## Tests (one file)

1. `ensure_admin` on empty DB creates an admin whose password verifies with `BcryptPasswordHasher`.
2. Existing non-admin user (different password) → promoted, password hash unchanged.
3. Second call is a no-op (still one user).
4. Weak password → raises the domain exception, no user created.
5. `seed_demo` twice → 3 approved restaurants, 15 approved dishes (no duplicates).

`api` tests use `ASGITransport`, which does not run `lifespan`, so no test setup changes.
Must stay green: `uv run pytest`, `uv run lint-imports`.

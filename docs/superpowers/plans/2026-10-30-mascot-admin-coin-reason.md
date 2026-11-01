# Plan — mascot artwork from the server, admin mascot CRUD, mascot purchases in coin history

Spec: `docs/superpowers/specs/2026-10-30-mascot-admin-coin-reason-design.md`. Task list only; each implementer
writes its own tests first (TDD) from the spec. Opus (this session) reviews every diff before the next step.

| # | Task | Who | Main files | Depends on |
|---|------|-----|------------|------------|
| 1 | Part A: `mascot_purchase` reason + migration 0029 (CHECK, backfill, downgrade) | Sonnet subagent (BE) | `domain/enums.py`, `use_cases/purchase_mascot.py`, `alembic/versions/0029_*.py`, mascot api tests | — |
| 2 | Parts B + C: `MascotState`, `mascot_images` + migration 0030, entity invariants, repo, `POST /admin/images`, admin mascot use cases/routes/schemas/DI, `images` on `GET /mascots` | Sonnet subagent (BE) | `domain/`, `ports/mascot_repository.py`, `db/models/mascot_model.py`, `db/repositories/mascot_repository.py`, `use_cases/admin_mascots.py`, `schemas/mascot_schemas.py`, `controllers/admin_controller.py`, `controllers/restaurant_controller.py` (shared upload check), `di/`, `tests/` | 1 (sequential, same files) |
| 3 | Review, `make test`, `lint-imports`, DDL check for 0029/0030, docs (`docs/feature-notes.md`, old mascots spec), commit after user OK | Opus | docs | 1, 2 |
| 4 | Mobile: schemas, render order, offline persistence of equipped art, contract note | FoodFenMobile session | `src/api/schemas.ts`, `src/db/schema.ts`, `src/components/mascot/*`, `src/features/mascot/*`, `docs/backend-contracts/premium-entitlements.md` | 3 |
| 5 | Web: `api:gen`, admin Mascots page (table, dialog, state grid, bulk drop, preview, confirmations), route + nav | FoodFenWeb session | `src/features/admin/mascots-*`, `src/routes/_authed/admin/mascots.tsx`, generated client | 3 |

4 and 5 run in parallel; each session gets its spec section plus the wire contract as its message, and reports
back to this session for review.

# 1. Clean Architecture with Protocol ports and FastAPI `Depends` composition

Date: 2026-09-03

## Status

Accepted.

## Context

FoodFenBE is a new backend that will grow several entities (users, foods, meals, logs) and is
expected to outlive its current framework choices. We want business logic that is testable without a
database or an HTTP server, an explicit seam for swapping persistence, and a structure that a new
contributor — human or AI — can extend without re-reading the whole codebase.

Constraints and preferences going in: Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL,
Pydantic v2, `uv` for packaging.

## Decision

### Clean Architecture, four layers, inward-only dependencies

`domain <- application <- {adapters, infrastructure}`. The domain has no third-party imports at all;
the application imports only the domain and the standard library. `import-linter` contracts
(`.importlinter`) fail CI if any layer imports outward or if `domain` / `application` touch a
framework. The rule is machine-checked, not just documented.

### Ports as `typing.Protocol`, not `abc.ABC`

Use cases depend on structural interfaces they define themselves (`UserRepositoryProtocol`).
`Protocol` means implementations don't inherit anything — the infrastructure repository and the
in-memory test double both satisfy the port by shape alone. This keeps the dependency pointing
inward without a base class shipped from an outer layer, and removes any need for a mocking library
in unit tests.

### Plain dataclass DTOs across the application boundary

Use cases accept and return frozen dataclasses, never Pydantic or ORM types. Pydantic stays in
`adapters` (HTTP wire format); SQLAlchemy stays in `infrastructure` (storage format). The domain
entity is a third, separate representation. Mapping between entity and ORM row is explicit
(`to_domain` / `from_domain`) so persistence concerns never leak into the model of the business.

### Composition via FastAPI `Depends`

`src/infrastructure/di.py` is the single composition root: small factory functions that build a
repository from a request-scoped `AsyncSession` and inject it into a use case. Controllers declare
`use_case: CreateUserUseCase = Depends(get_create_user_use_case)` and know nothing about wiring. No
DI container library — FastAPI's own dependency system is sufficient and already present.

### Domain exceptions mapped to HTTP centrally

Application and domain raise `DomainException` subclasses. `src/main.py` holds one table mapping
exception type → status code (400 / 404 / 409). Controllers never catch or translate. Adding an
error class and its status is a one-line change in one place.

## Consequences

**Positive**

- Business rules unit-test in milliseconds with no DB or ASGI server.
- Swapping or adding a persistence backend touches `infrastructure` + `di.py` only.
- The architecture is enforced automatically; violations are caught in CI, not review.
- New slices follow a fixed, documented recipe (`ARCHITECTURE.md`).

**Negative / costs**

- Three representations of "a user" (entity, DTO, ORM model, plus the HTTP schema — four) and
  explicit mapping code between them. Deliberate: the boundaries are the point.
- More files per feature than a framework-native CRUD app.
- Contributors must learn the layering before adding code. Mitigated by `CLAUDE.md` and this ADR.

**Deferred**

- Email syntax is checked with a naive regex in the domain; no `email-validator` dependency. Revisit
  if malformed addresses reach production.
- Transactions are request-scoped (commit-on-success in the session dependency). A use case needing
  finer control will get an explicit unit-of-work object.
- No auth, pagination, or soft-delete yet — out of scope for the reference slice.

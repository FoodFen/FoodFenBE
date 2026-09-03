# FoodFenBE — rules for AI sessions

Clean Architecture. Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, Pydantic v2, `uv`.
Dependency direction: `domain <- application <- adapters | infrastructure`. Never sideways, never inward-out.

## Never

- **Never** import third-party packages in `src/domain/`. Standard library only (`dataclasses`, `typing`, `abc`, `re`, `uuid`, `datetime`).
- **Never** import `fastapi`, `sqlalchemy`, `pydantic`, `src.adapters`, or `src.infrastructure` from `src/application/`.
- **Never** define ports as `abc.ABC`. Ports are `typing.Protocol`.
- **Never** pass a Pydantic schema (or an ORM object) into a use case. Use cases take/return dataclass DTOs only.
- **Never** put business rules in controllers. They translate HTTP <-> DTO and nothing else.
- **Never** reuse a domain entity as an ORM model, or vice versa. They are separate classes with explicit `to_domain` / `from_domain`.
- **Never** raise `HTTPException` from application or domain. Raise a `DomainException` subclass; `src/main.py` maps it to a status code.
- **Never** catch domain exceptions in the controller. Let them propagate to the handlers.
- **Never** add a dependency for something a few lines of stdlib do.

## Always

- **Always** enforce entity invariants in the entity's `__post_init__` (or a factory), not in the use case or schema.
- **Always** construct new entities via the domain factory (`User.create(...)`), which sets id / timestamps / defaults.
- **Always** access the DB session through the `get_db_session` dependency (commit-on-success, rollback-on-error per request).
- **Always** run `uv run lint-imports` after touching imports. It is the architecture's guardrail and CI must stay green.
- **Always** add an Alembic migration when you change an ORM model. Never edit the DB by hand.
- **Always** register new use cases in `src/infrastructure/di.py` and inject them with `Depends`.
- **Always** use `Annotated` for router functions and other injected parameters that Python IDEs
  complain about (valid in FastAPI either way, but only `Annotated` type-checks cleanly). For example:

```python
async def create_user(
    body: CreateUserRequest,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
    # Not: use_case: CreateUserUseCase = Depends(get_create_user_use_case)
) -> UserResponse:
```

  This applies to `src/infrastructure/di.py` too — see the `SessionDep` / `UserRepositoryDep`
  aliases there, and reuse that pattern rather than repeating `Annotated[...]` at each call site.

## Commands

    make dev            # uvicorn --reload
    make test           # pytest (unit + integration + api)
    make lint-imports   # import-linter contracts
    make migrate        # alembic upgrade head
    make docker-up      # local postgres:16

## Adding a slice

See `ARCHITECTURE.md` → "Scaffolding a new slice". Mirror the User slice, layer by layer, inner to outer.

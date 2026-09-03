.PHONY: dev test lint-imports migrate docker-up

TEST_DB := postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test

dev:
	uv run uvicorn src.main:app --reload

# Tests drop and recreate their schema, so they use a separate database.
test:
	DATABASE_URL=$(TEST_DB) TEST_DATABASE_URL=$(TEST_DB) uv run pytest

lint-imports:
	uv run lint-imports

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up -d

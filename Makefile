.PHONY: dev test lint-imports migrate docker-up

dev:
	uv run uvicorn src.main:app --reload

test:
	uv run pytest

lint-imports:
	uv run lint-imports

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up -d

.PHONY: dev test lint-imports migrate docker-up

dev:
	@# watchfiles, not uvicorn --reload: on Windows uvicorn's reloader stops the worker with CTRL_C_EVENT, which never arrives without a real console (background shells), so it hangs on the old code. watchfiles hard-kills and restarts.
	uv run watchfiles "uvicorn src.main:app" src

# tests/conftest.py points the tests at in-memory SQLite, never at .env's DATABASE_URL.
test:
	uv run pytest

lint-imports:
	uv run lint-imports

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up -d

.DEFAULT_GOAL := help
.PHONY: help doctor install hooks local-up local-down api web migrate migrate-down makemigration makemigration-auto test test-api test-web test-unit lint format

help: ## list targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## verify host tools (uv, pnpm, docker) are installed
	@printf "uv     : "; command -v uv     >/dev/null && uv     --version       || { echo "MISSING — install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
	@printf "node   : "; command -v node   >/dev/null && node   --version       || { echo "MISSING — install: brew install node"; exit 1; }
	@printf "pnpm   : "; command -v pnpm   >/dev/null && pnpm   --version       || { echo "MISSING — install: brew install pnpm   (or: npm i -g pnpm@9)"; exit 1; }
	@printf "docker : "; command -v docker >/dev/null && docker --version | head -1 || { echo "MISSING — install Docker Desktop or 'brew install --cask docker'"; exit 1; }
	@echo "OK."

install: ## uv sync + pnpm install (run `make doctor` first if anything is missing)
	@command -v pnpm >/dev/null 2>&1 || { \
		echo "ERROR: pnpm not found on PATH. Run 'make doctor' for install instructions."; \
		exit 1; \
	}
	cd apps/api && uv sync
	cd apps/web && pnpm install

hooks: ## install pre-commit git hooks (run once after `make install`)
	cd apps/api && uv run pre-commit install

local-up: ## docker compose up postgres + localstack + mailpit
	cd docker && docker compose up -d

local-down: ## docker compose down
	cd docker && docker compose down

api: ## run uvicorn :8000 with reload
	cd apps/api && GIT_SHA=$$(git rev-parse --short HEAD 2>/dev/null || echo unknown) uv run uvicorn bootstrap.api:app --reload

web: ## run Vite :5173
	cd apps/web && pnpm dev

migrate: ## alembic upgrade head
	cd apps/api && uv run alembic upgrade head

migrate-down: ## alembic downgrade -1
	cd apps/api && uv run alembic downgrade -1

makemigration: ## alembic revision -m "$M"
	cd apps/api && uv run alembic revision -m "$(M)"

makemigration-auto: ## alembic revision --autogenerate -m "$M"
	cd apps/api && uv run alembic revision --autogenerate -m "$(M)"

test: test-api test-web ## run backend + frontend (all suites)

test-api: ## pytest backend (unit + integration + e2e)
	cd apps/api && uv run pytest

test-web: ## vitest run (no watch)
	cd apps/web && pnpm test:run

test-unit: ## backend unit only + frontend unit only
	cd apps/api && uv run pytest tests/unit
	cd apps/web && pnpm test:run tests/unit

lint: ## ruff + mypy + import-linter + pnpm lint
	cd apps/api && uv run ruff check . && uv run mypy && uv run lint-imports
	cd apps/web && pnpm typecheck && pnpm lint

format: ## ruff format + prettier
	cd apps/api && uv run ruff format .
	cd apps/web && pnpm format

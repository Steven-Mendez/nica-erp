.PHONY: doctor doctor-deploy install hooks local-up local-down api web migrate migrate-down makemigration-auto lint format

##@ Setup
doctor: ## verify dev tools (uv, node, pnpm, docker) needed for local dev + tests
	@printf "uv     : "; command -v uv     >/dev/null && uv     --version       || { echo "MISSING — install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
	@printf "node   : "; command -v node   >/dev/null && node   --version       || { echo "MISSING — install: brew install node"; exit 1; }
	@printf "pnpm   : "; command -v pnpm   >/dev/null && pnpm   --version       || { echo "MISSING — install: brew install pnpm   (or: npm i -g pnpm@9)"; exit 1; }
	@printf "docker : "; command -v docker >/dev/null && docker --version | head -1 || { echo "MISSING — install Docker Desktop or 'brew install --cask docker'"; exit 1; }
	@echo "OK."

doctor-deploy: ## verify deploy tools (terraform, aws, gh) needed for bootstrap + workflow dispatch
	@printf "terraform : "; command -v terraform >/dev/null && terraform version | head -1 || { echo "MISSING — install: brew install terraform   (need >= 1.6)"; exit 1; }
	@printf "aws       : "; command -v aws       >/dev/null && aws       --version       || { echo "MISSING — install: brew install awscli      (need v2)"; exit 1; }
	@printf "gh        : "; command -v gh        >/dev/null && gh        --version | head -1 || { echo "MISSING — install: brew install gh"; exit 1; }
	@printf "aws sts   : "; AWS_PROFILE=$${AWS_PROFILE:-nica-erp} aws sts get-caller-identity --query Account --output text 2>/dev/null || { echo "FAIL — profile '$${AWS_PROFILE:-nica-erp}' not configured. Run: aws configure --profile nica-erp"; exit 1; }
	@printf "gh auth   : "; gh auth status >/dev/null 2>&1 && echo "OK" || { echo "FAIL — not logged in. Run: gh auth login"; exit 1; }
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

##@ Local dev
local-up: ## docker compose up postgres + localstack + mailpit
	cd docker && docker compose up -d

local-down: ## docker compose down
	cd docker && docker compose down

api: ## run uvicorn :8000 with reload
	cd apps/api && GIT_SHA=$$(git rev-parse --short HEAD 2>/dev/null || echo unknown) uv run uvicorn bootstrap.api:app --reload

web: ## run Vite :5173
	cd apps/web && pnpm dev

##@ Migrations
migrate: ## alembic upgrade head
	cd apps/api && uv run alembic upgrade head

migrate-down: ## alembic downgrade -1
	cd apps/api && uv run alembic downgrade -1

makemigration-auto: ## alembic revision --autogenerate -m "$M"
	cd apps/api && uv run alembic revision --autogenerate -m "$(M)"

##@ Code quality
lint: ## ruff + mypy + import-linter + pnpm lint
	cd apps/api && uv run ruff check . && uv run mypy && uv run lint-imports
	cd apps/web && pnpm typecheck && pnpm lint

format: ## ruff format + prettier
	cd apps/api && uv run ruff format .
	cd apps/web && pnpm format

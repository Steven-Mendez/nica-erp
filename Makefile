.DEFAULT_GOAL := help
.PHONY: help doctor doctor-deploy install hooks local-up local-down api web migrate migrate-down makemigration makemigration-auto test test-api test-web test-unit test-be-unit test-be-integration test-be-e2e test-be-coverage test-fe-unit test-fe-integration test-fe-e2e test-fe-matrix test-fe-coverage test-fe-all test-all lint format bootstrap destroy-bootstrap build-image deploy deploy-local destroy destroy-local plan logs urls verify wipe

help: ## list targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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

test-be-unit: ## backend pytest tests/unit only (no testcontainer, < 5s)
	cd apps/api && uv run pytest tests/unit

test-be-integration: ## backend pytest tests/integration only (one testcontainer for the session)
	cd apps/api && uv run pytest tests/integration

test-be-e2e: ## backend pytest tests/e2e only (full wired-app + testcontainer)
	cd apps/api && uv run pytest tests/e2e

test-be-coverage: ## backend pytest + coverage gate (currently 89.50%, target 90%)
	cd apps/api && uv run pytest \
		--cov=src/contexts/tenants \
		--cov=src/contexts/identity \
		--cov=src/shared_kernel \
		--cov-report=term-missing \
		--cov-fail-under=89

test-fe-unit: ## frontend vitest unit lane only (pure logic, no MSW)
	cd apps/web && pnpm test:unit

test-fe-integration: ## frontend vitest integration lane (MSW + react-query + router)
	cd apps/web && pnpm test:integration

test-fe-e2e: ## frontend Playwright @smoke (Chromium)
	cd apps/web && pnpm test:e2e:smoke

test-fe-matrix: ## verification matrix: every inventory entry has a covering test
	cd apps/web && pnpm test:layout && pnpm test:matrix

test-fe-coverage: ## frontend vitest run + v8 coverage gate
	cd apps/web && pnpm exec vitest run --coverage

test-fe-all: test-fe-unit test-fe-integration test-fe-matrix test-fe-coverage ## full FE triad + matrix + coverage

test-all: test-be-coverage test-fe-all ## full triad: backend + FE lanes + gates

lint: ## ruff + mypy + import-linter + pnpm lint
	cd apps/api && uv run ruff check . && uv run mypy && uv run lint-imports
	cd apps/web && pnpm typecheck && pnpm lint

format: ## ruff format + prettier
	cd apps/api && uv run ruff format .
	cd apps/web && pnpm format

bootstrap: ## provision persistent AWS resources (state bucket, ECR, SPA CloudFront)
	./scripts/bootstrap.sh

destroy-bootstrap: ## tear down persistent AWS resources (refuses if ephemeral stack alive)
	./scripts/destroy-bootstrap.sh

build-image: ## build the API image (linux/amd64) and push to ECR (ALLOW_DIRTY=1 to opt in to a dirty tag). Note: --platform linux/amd64 emulates under QEMU on Apple Silicon and may segfault; use the deploy workflow's build step instead.
	./scripts/build-and-push-image.sh

deploy: ## dispatch the deploy GHA workflow (build image + apply ephemeral infra + migrate + SPA upload + healthcheck)
	@command -v gh >/dev/null || { echo "ERROR: gh CLI not found. Install: brew install gh"; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "ERROR: not logged in to gh. Run: gh auth login"; exit 1; }
	gh workflow run deploy.yml --ref main
	@echo
	@echo "==> Dispatched deploy.yml. Tail logs with:"
	@echo "    gh run watch \$$(gh run list --workflow=deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')"

deploy-local: ## run scripts/deploy.sh directly on this host (escape hatch — requires linux/amd64 for the image build step)
	./scripts/deploy.sh

destroy: ## dispatch the destroy GHA workflow (tears down the ephemeral demo stack; bootstrap survives)
	@command -v gh >/dev/null || { echo "ERROR: gh CLI not found. Install: brew install gh"; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "ERROR: not logged in to gh. Run: gh auth login"; exit 1; }
	gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral
	@echo
	@echo "==> Dispatched destroy.yml. Tail logs with:"
	@echo "    gh run watch \$$(gh run list --workflow=destroy.yml --limit 1 --json databaseId --jq '.[0].databaseId')"

destroy-local: ## run scripts/destroy.sh directly on this host (escape hatch)
	./scripts/destroy.sh

plan: ## terraform plan against the demo env (operator-host read-only)
	@account_id=$$(AWS_PROFILE=$${AWS_PROFILE:-nica-erp} aws sts get-caller-identity --query Account --output text); \
	  terraform -chdir=infra/terraform/envs/demo init -input=false -reconfigure -backend-config="bucket=nica-erp-tf-state-$${account_id}" && \
	  terraform -chdir=infra/terraform/envs/demo plan

logs: ## tail the API CloudWatch Logs group
	./scripts/tail-logs.sh

urls: ## print the public CloudFront URLs
	./scripts/print-urls.sh

verify: ## smoke-test the live deploy (curl /api/healthz + SPA root, assert db:ok + non-null alembic_revision)
	./scripts/verify-deploy.sh

wipe: destroy destroy-bootstrap ## project-close: destroy ephemeral via workflow, then destroy bootstrap locally

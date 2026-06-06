.PHONY: bootstrap destroy-bootstrap build-image deploy destroy wipe plan logs urls verify deploy-local destroy-local

##@ Deploy lifecycle
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

destroy: ## dispatch the destroy GHA workflow (tears down the ephemeral demo stack; bootstrap survives)
	@command -v gh >/dev/null || { echo "ERROR: gh CLI not found. Install: brew install gh"; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "ERROR: not logged in to gh. Run: gh auth login"; exit 1; }
	gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral
	@echo
	@echo "==> Dispatched destroy.yml. Tail logs with:"
	@echo "    gh run watch \$$(gh run list --workflow=destroy.yml --limit 1 --json databaseId --jq '.[0].databaseId')"

wipe: destroy destroy-bootstrap ## project-close: destroy ephemeral via workflow, then destroy bootstrap locally

##@ Deploy observability
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

##@ Escape hatches (use when GHA is down)
deploy-local: ## run scripts/deploy.sh directly on this host (requires linux/amd64 for the image build step)
	./scripts/deploy.sh

destroy-local: ## run scripts/destroy.sh directly on this host
	./scripts/destroy.sh

# 11 — Terraform and Deployment

Two commands: `make deploy` / `make destroy`. Persistent state, ephemeral infra. No CI/CD ([ADR-0023](adr/0023-no-ci-cd-mvp.md)). One environment: `demo`. Assumes [ADR-0020](adr/0020-no-custom-domain-mvp.md) (no custom domain) and [ADR-0021](adr/0021-ssm-parameter-store.md) (SSM instead of Secrets Manager).

Infrastructure description (service inventory, network topology, sizing) in [`10-infrastructure.md`](10-infrastructure.md). Backup/restore operations in [`13-operations.md`](13-operations.md).

---

## Layout

```
infra/terraform/
├── bootstrap/                  # once in the lifetime of the project
│   ├── main.tf                 # S3 state, DynamoDB lock, ECR, S3 web, CloudFront, OAC
│   ├── outputs.tf              # web_bucket_name, web_distribution_id, web_distribution_domain_name
│   └── backend.tf              # backend "local" in .tfstate-local/ (gitignored)
├── modules/
│   ├── network/                # VPC, subnets, NAT, SGs
│   ├── data/                   # RDS + subnet/parameter group + credentials in SSM
│   ├── compute/                # ECS cluster, task defs, service, ALB HTTP-only + SG CloudFront prefix list
│   ├── workers/                # Lambdas + event source mappings + scheduled rules + vpc_config
│   ├── messaging/              # EventBridge bus + rules + queues + DLQs
│   ├── auth/                   # Cognito User Pool + App Client + default domain prefix
│   ├── storage/                # S3 files
│   ├── secrets/                # SSM SecureString (db/master, jwt/signing-key, integrations/*)
│   ├── email/                  # SES email identities (no domain)
│   └── observability/          # CloudWatch + alarms + SNS topic
└── envs/demo/
    ├── main.tf                 # composes modules; adds /api/* behavior to bootstrap CloudFront
    ├── backend.tf              # points to bootstrap S3+DynamoDB
    └── outputs.tf
```

---

## Bootstrap (once)

`make bootstrap` → `cd infra/terraform/bootstrap && terraform init && terraform apply -auto-approve`. Creates:

| Resource | Reason |
|---|---|
| S3 bucket `nica-erp-tf-state` (versioned) | Terraform state. |
| DynamoDB `nica-erp-tf-lock` | Concurrent lock. |
| ECR `nica-erp` | API + worker images. |
| S3 bucket `nica-erp-web` private + CloudFront + OAC | SPA. CloudFront `<dist-id>.cloudfront.net` with `/*` behavior → S3; `/api/*` is added in `envs/demo`. |

Bootstrap state is **local** (`.tfstate-local/`, in `.gitignore`). Back up manually — without it you can't destroy the bootstrap.

---

## Deployment

`make deploy` runs: `check-credentials.sh` → `build-and-push-image.sh` → `terraform apply` → `run-migrations.sh` → `print-urls.sh`. ~12 min total (RDS takes 6–8, build/push ~2, migration ~1).

**Single ECR image, different entrypoints**. One image serves five roles:

| Resource | Entrypoint |
|---|---|
| API task | `uvicorn bootstrap.api:app --host 0.0.0.0 --port 8000` |
| Migration task | `alembic upgrade head` |
| Lambda outbox/audit/notif/fx/housekeeping | `bootstrap.entrypoints.<worker>.handler` |

`build-and-push-image.sh` writes the tag to `$REPO_ROOT/.deploy-image-tag` (gitignored). **Single source of truth**: Makefile, `plan`, `apply`, `destroy` read it from there.

`terraform apply` creates VPC, RDS, ECS service, ALB HTTP-only + SG restricted to CloudFront prefix list, Cognito, SES email identity sandbox, SQS, EventBridge, Lambdas, S3 `files`; **adds the `/api/*` behavior to the bootstrap CloudFront** (`OriginProtocolPolicy=http-only`, cache TTL 0, forward `Authorization` + `Cookie`).

CloudFront **does not** rewrite the path: the API receives `/api/v1/...`. FastAPI runs with `root_path="/api"` when `APP_ENV=aws` (set in `bootstrap/settings.py`); that way routers are declared under `/v1/...` just like local, and OpenAPI lists the servers with `/api` so the generated client works against both origins. In local `root_path=""` and the API is served at `http://localhost:8000/v1/...`.

Migrations run as a **one-off ECS task** with override `command = ["alembic", "upgrade", "head"]`, `aws ecs wait tasks-stopped` validates exit code.

`print-urls.sh` reads outputs and prints: `App: https://<dist-id>.cloudfront.net/`, `API: /api`, `OpenAPI: /api/docs`, `Health: /api/healthz`, `Cognito: https://nica-erp.auth.us-east-1.amazoncognito.com`. The `<dist-id>` is preserved between destroy and deploy (the distribution lives in bootstrap); it only changes after `make wipe` + re-bootstrap.

---

## Destruction

`make destroy`: `confirm-destroy.sh` (type `destroy` — external script to avoid `read -p` traps in make), then `terraform destroy -auto-approve -var "image_tag=$(cat .deploy-image-tag || echo latest)" -var "final_snapshot_suffix=$(date +%Y%m%d%H%M%S)"`. ~10 min (RDS slow, the rest parallel). Ends with `scripts/verify-destroyed.sh` (exit≠0 if NAT/ALB/RDS/ECS/Fargate/Lambda are still alive).

**Preserves** (bootstrap): state bucket, DynamoDB lock, ECR, `web` bucket, CloudFront.

**Destroys** (don't persist):

- RDS final snapshot — pre-launch `skip_final_snapshot=true` ([ADR-0017](adr/0017-backups-pitr.md)); each deploy re-creates with Alembic + seed.
- SSM SecureString parameters — immediate deletion, no recovery window ([ADR-0021](adr/0021-ssm-parameter-store.md)); the next bootstrap regenerates them with `random_password`.

### Re-deployment

Default: empty DB + all migrations. Restore procedure in [`13-operations.md`](13-operations.md).

---

## Total destruction (`make wipe`)

`make wipe = make destroy && make destroy-bootstrap`. To close the project or change account. No external gotchas under [ADR-0020](adr/0020-no-custom-domain-mvp.md) + [ADR-0021](adr/0021-ssm-parameter-store.md) (no DNS registrar, no recovery windows, no orphan snapshots).

`scripts/destroy-bootstrap.sh` requires typing `DESTROY BOOTSTRAP`. Aborts if `envs/demo` still has state with resources. Empties versioned buckets (state + web) and ECR before the bootstrap `terraform destroy`.

### Risks

| Risk | Mitigation |
|---|---|
| `.tfstate-local/` lost | Back up to external S3 after each `make bootstrap`. Without it: `terraform import` or manual cleanup via console. |
| CloudFront destroyed → URL changes | All references via Terraform output (Cognito callbacks, SPA `/api` relative). A URL stable across wipes requires a custom domain. |
| Cognito prefix `nica-erp` reserved after destroy | AWS retains it for a few minutes; wait ~5 min and retry. |

### Re-bootstrap

`make bootstrap && make deploy`. New CloudFront URL; Cognito callbacks and Terraform outputs are updated in the same apply.

---

## Rolling deploys

Per [ADR-0018](adr/0018-rolling-deploys.md): each sprint from 01 onwards exercises `make deploy` + `make destroy`, swapping the sprint's port to its AWS adapter and verifying against the deployed stack. The canonical post-deploy checklist lives in [`sprints/README.md` § Post-deploy verification](sprints/README.md#post-deploy-verification) — don't duplicate it here.

---

## No CI/CD

Per [ADR-0023](adr/0023-no-ci-cd-mvp.md): GitHub Actions runs static verification only (lint, type-check, unit tests). Deploy is manual — `make deploy` from a developer workstation with AWS credentials. Rationale: a single operator, ephemeral environments, no productive tenants pre-launch. CD will be introduced when the first productive tenant arrives.

---

## Activate custom domain

Runbook to revert [ADR-0020](adr/0020-no-custom-domain-mvp.md). When: a serious prospect that needs the URL in a presentation, a URL stable across `make wipe`, exit from SES sandbox, first productive tenant. **Not** for personal demos or screen share (`<dist-id>.cloudfront.net` is enough).

Prerequisites: working stack, decided domain (preferably Route 53 Registrar, ~$15/year for `.com` — avoids the NS records vs external registrar gotcha), 24–48 h margin for DNS propagation.

### Steps

1. Register the domain (`aws route53domains register-domain ...`).
2. Add `domain_name = "miempresa.dev"` to `terraform.tfvars`.
3. `make deploy`.
4. If the domain is NOT on Route 53 Registrar: copy the NS records of the hosted zone (`terraform output -raw hosted_zone_id`) to the external registrar, wait for propagation.
5. Verify: `dig +short app.miempresa.dev`, `curl https://api.miempresa.dev/healthz`.

### Terraform changes

| Resource | Module | Notes |
|---|---|---|
| `aws_route53_zone` | `bootstrap/` | If you registered via R53 Registrar it already exists — `terraform import`. |
| `aws_acm_certificate` `*.miempresa.dev` (`us-east-1`) | `bootstrap/` or `envs/demo/` | Mandatory us-east-1 for CloudFront. Automatic DNS validation. |
| `aws_cloudfront_distribution.aliases` + `viewer_certificate` | `bootstrap/` update | |
| `aws_route53_record` ALIAS A `app.miempresa.dev` → CloudFront | `bootstrap/` | |
| `aws_cognito_user_pool_domain` custom `auth.miempresa.dev` + cert | `envs/demo/` | Replaces default prefix. |
| `aws_ses_domain_identity` + DKIM in R53 + out-of-sandbox ticket | `envs/demo/` + manual console | DKIM/SPF/DMARC. Approval ~24–48 h. |

**Recommendation**: Option A — CloudFront with `aliases = ["app.miempresa.dev"]` and `/api/*` behavior (SPA + API same domain, no CORS). Option B (split between CloudFront SPA and ALB HTTPS for API) adds a regional cert, CORS, and complexity.

### Application updates

| Component | Change |
|---|---|
| SPA `VITE_API_BASE_URL` | stays `/api` (relative) in Option A |
| Cognito callback URLs | add `https://app.miempresa.dev/auth/callback`, keep CloudFront default during transition |
| SES from address | `noreply@miempresa.dev` |
| SES Configuration Set | publishing bounces/complaints to SNS |

### Recurring cost

`.com` registration ~$1.08/month + hosted zone $0.50/month = **+$1.58/month** vs ADR-0020. ACM free.

### Reversal

Remove `domain_name`, remove `aliases` + `viewer_certificate` from CloudFront, remove Cognito custom domain, remove SES domain identity, `make deploy`. Optionally `aws route53domains disable-domain-auto-renew`.

---

## Makefile

```makefile
REPO_ROOT       := $(shell git rev-parse --show-toplevel)
IMAGE_TAG_FILE  := $(REPO_ROOT)/.deploy-image-tag

.PHONY: help install bootstrap deploy deploy-web destroy destroy-bootstrap wipe plan \
        local-up local-down migrate seed \
        api web test lint format logs \
        worker-outbox worker-audit worker-notif \
        _check-credentials _build-and-push-image

help:
	@echo "Local:"
	@echo "  make install            # uv sync + pnpm install + pre-commit install"
	@echo "  make local-up           # docker compose: postgres + localstack + mailpit"
	@echo "  make local-down"
	@echo "  make migrate            # alembic upgrade head"
	@echo "  make seed"
	@echo "  make api / make web"
	@echo "  make worker-outbox / worker-audit / worker-notif"
	@echo "  make test"
	@echo ""
	@echo "AWS:"
	@echo "  make bootstrap          # once: state + ECR + S3 web + CloudFront"
	@echo "  make deploy             # build + push + apply + migrate"
	@echo "  make deploy-web         # pnpm build + s3 sync + invalidation"
	@echo "  make destroy            # tear down ephemeral"
	@echo "  make destroy-bootstrap  # irreversible, hard confirm"
	@echo "  make wipe               # destroy + destroy-bootstrap"
	@echo "  make logs / make plan"

install:
	cd apps/api && uv sync
	cd apps/web && pnpm install --frozen-lockfile
	uv run pre-commit install

bootstrap:
	cd infra/terraform/bootstrap && terraform init && terraform apply -auto-approve

deploy: _check-credentials _build-and-push-image
	cd infra/terraform/envs/demo && terraform init && \
	  terraform apply -auto-approve -var "image_tag=$$(cat $(IMAGE_TAG_FILE))"
	@./scripts/run-migrations.sh
	@./scripts/print-urls.sh

deploy-web: _check-credentials
	cd apps/web && pnpm install --frozen-lockfile && pnpm build
	@WEB_BUCKET=$$(cd infra/terraform/bootstrap && terraform output -raw web_bucket_name); \
	  DIST_ID=$$(cd infra/terraform/bootstrap && terraform output -raw web_distribution_id); \
	  DIST_DOMAIN=$$(cd infra/terraform/bootstrap && terraform output -raw web_distribution_domain_name); \
	  aws s3 sync apps/web/dist/ "s3://$$WEB_BUCKET/" --delete --cache-control "public,max-age=31536000,immutable" --exclude "index.html"; \
	  aws s3 cp apps/web/dist/index.html "s3://$$WEB_BUCKET/index.html" --cache-control "no-cache,no-store,must-revalidate"; \
	  aws cloudfront create-invalidation --distribution-id "$$DIST_ID" --paths '/index.html' >/dev/null; \
	  echo "Frontend deployed: https://$$DIST_DOMAIN/"

destroy:
	@./scripts/confirm-destroy.sh
	cd infra/terraform/envs/demo && terraform destroy -auto-approve \
	  -var "image_tag=$$(cat $(IMAGE_TAG_FILE) 2>/dev/null || echo latest)" \
	  -var "final_snapshot_suffix=$$(date +%Y%m%d%H%M%S)"
	@./scripts/verify-destroyed.sh

destroy-bootstrap:
	@./scripts/destroy-bootstrap.sh

wipe: destroy destroy-bootstrap
	@echo "Infrastructure fully removed. AWS cost: 0 USD/month."

plan:
	cd infra/terraform/envs/demo && terraform init && \
	  terraform plan -var "image_tag=$$(cat $(IMAGE_TAG_FILE) 2>/dev/null || echo latest)"

local-up:
	cd docker && docker compose up -d
	@echo "Postgres :5432, LocalStack :4566, Mailpit :8025"

local-down:
	cd docker && docker compose down

migrate:
	cd apps/api && uv run alembic upgrade head

seed:
	cd apps/api && uv run python scripts/seed-dev.py

api:
	cd apps/api && uv run uvicorn bootstrap.api:app --reload

web:
	cd apps/web && pnpm dev

worker-outbox:
	cd apps/api && uv run python -m bootstrap.entrypoints.outbox_publisher
worker-audit:
	cd apps/api && uv run python -m bootstrap.entrypoints.audit_consumer
worker-notif:
	cd apps/api && uv run python -m bootstrap.entrypoints.notifications_worker

test:
	cd apps/api && uv run pytest

logs:
	@./scripts/tail-logs.sh

_check-credentials:
	@./scripts/check-credentials.sh
_build-and-push-image:
	@./scripts/build-and-push-image.sh
```

**Literal TAB indentation** (spaces → `*** missing separator`). `IMAGE_TAG_FILE` is the single source of truth for the tag — Makefile, `plan`, `apply`, `destroy` read it from there.

`deploy-web` syncs assets with `cache-control "public,max-age=31536000,immutable"` except `index.html` (`no-cache`); invalidates only `/index.html`.

---

## Critical scripts

### `scripts/verify-destroyed.sh`

Exit code 0 from `terraform destroy` **does not guarantee** infra is down. Known scenarios: hung Lambda ENI blocking the NAT, ALB with `deletion_protection` enabled outside Terraform, ECS task `RUNNING` restarted between `update-service --desired-count 0` and the destroy, final snapshot with an existing identifier (Terraform silently fails).

```bash
#!/usr/bin/env bash
set -euo pipefail

FAIL=0
check() {
  local label="$1" count="$2"
  if [[ "$count" -gt 0 ]]; then
    echo "  [FAIL] $label still alive: $count"; FAIL=1
  else
    echo "  [OK]   $label clean"
  fi
}

echo "Post-destroy verification in account $(aws sts get-caller-identity --query Account --output text):"
check "NAT Gateways"     "$(aws ec2 describe-nat-gateways --filter 'Name=state,Values=available' --query 'length(NatGateways)' --output text)"
check "ALBs"             "$(aws elbv2 describe-load-balancers --query 'length(LoadBalancers[?starts_with(LoadBalancerName, \`nica-erp\`)])' --output text)"
check "RDS instances"    "$(aws rds describe-db-instances --query 'length(DBInstances[?starts_with(DBInstanceIdentifier, \`nica-erp\`)])' --output text)"
check "ECS services"     "$(aws ecs list-services --cluster nica-erp --query 'length(serviceArns)' --output text 2>/dev/null || echo 0)"
check "Fargate tasks"    "$(aws ecs list-tasks --cluster nica-erp --query 'length(taskArns)' --output text 2>/dev/null || echo 0)"
check "Lambda functions" "$(aws lambda list-functions --query 'length(Functions[?starts_with(FunctionName, \`nica-erp\`)])' --output text)"
check "VPCs nica-erp"    "$(aws ec2 describe-vpcs --filter 'Name=tag:Project,Values=nica-erp' --query 'length(Vpcs)' --output text)"

[[ "$FAIL" -ne 0 ]] && { echo "Some resources survived. Review and clean up."; exit 1; }
echo "Destroyed correctly."
```

### `scripts/destroy-bootstrap.sh`

Handling S3 versioning (delete markers) and ECR emptying is non-trivial — `terraform destroy` fails if buckets/repos are not empty. Hard confirmation: `DESTROY BOOTSTRAP`. Guard: aborts if `envs/demo` state still has resources.

```bash
#!/usr/bin/env bash
set -euo pipefail

STATE_BUCKET=nica-erp-tf-state
WEB_BUCKET=nica-erp-web
ECR_REPO=nica-erp
ENV_STATE_KEY=envs/demo/terraform.tfstate

echo "WARNING: TOTAL destruction of bootstrap (irreversible)."
echo "Pre-requisites: 'make destroy' executed; backup of .tfstate-local/."
read -rp "Confirm with 'DESTROY BOOTSTRAP': " confirm
[[ "$confirm" != "DESTROY BOOTSTRAP" ]] && { echo "Cancelled." >&2; exit 1; }

# Guard: main env state must be empty
if aws s3api head-object --bucket "$STATE_BUCKET" --key "$ENV_STATE_KEY" >/dev/null 2>&1; then
  STATE_SIZE=$(aws s3api head-object --bucket "$STATE_BUCKET" --key "$ENV_STATE_KEY" --query 'ContentLength' --output text)
  [[ "$STATE_SIZE" -gt 500 ]] && { echo "Error: envs/demo state not empty ($STATE_SIZE bytes). Run 'make destroy' first." >&2; exit 1; }
fi

empty_versioned_bucket() {
  local bucket="$1" versions markers
  versions=$(aws s3api list-object-versions --bucket "$bucket" --query 'Versions[*].{Key:Key,VersionId:VersionId}' --output json 2>/dev/null || echo '[]')
  [[ "$versions" != "[]" && "$versions" != "null" ]] && \
    aws s3api delete-objects --bucket "$bucket" --delete "{\"Objects\": $versions}" >/dev/null
  markers=$(aws s3api list-object-versions --bucket "$bucket" --query 'DeleteMarkers[*].{Key:Key,VersionId:VersionId}' --output json 2>/dev/null || echo '[]')
  [[ "$markers" != "[]" && "$markers" != "null" ]] && \
    aws s3api delete-objects --bucket "$bucket" --delete "{\"Objects\": $markers}" >/dev/null
}

echo "[1/4] Emptying state S3 bucket..."; empty_versioned_bucket "$STATE_BUCKET"
echo "[2/4] Emptying web S3 bucket...";   empty_versioned_bucket "$WEB_BUCKET"
echo "[3/4] Emptying ECR..."
IMAGES=$(aws ecr list-images --repository-name "$ECR_REPO" --query 'imageIds[*]' --output json 2>/dev/null || echo '[]')
[[ "$IMAGES" != "[]" ]] && aws ecr batch-delete-image --repository-name "$ECR_REPO" --image-ids "$IMAGES" >/dev/null
echo "[4/4] terraform destroy of bootstrap..."
cd infra/terraform/bootstrap && terraform destroy -auto-approve
echo; echo "Bootstrap destroyed. AWS cost: 0 USD/month."
```

### `scripts/confirm-destroy.sh`

Confirmation outside the Makefile (avoids `@read -p` traps with `make -j`, non-interactive shells, capture by `script`/CI):

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "This destroys all ephemeral infrastructure."
echo "Preserves: S3 state, DynamoDB lock, ECR, S3 web, CloudFront."
read -rp "Confirm with 'destroy': " confirm
[[ "$confirm" != "destroy" ]] && { echo "Cancelled." >&2; exit 1; }
```

---

## State and locking

S3 `nica-erp-tf-state` key `envs/demo/terraform.tfstate`, DynamoDB `nica-erp-tf-lock` (LockID), bucket versioned + encrypted.

---

## Sensitive variables

`terraform.tfvars` not versioned (there's a `.example`):

```hcl
alert_email      = "ops@example.com"
aws_region       = "us-east-1"
ses_from_address = "noreply@example.com"
ses_from_name    = "nica-erp"
```

No `domain_name` under [ADR-0020](adr/0020-no-custom-domain-mvp.md). **Override `alert_email` to a real address before applying** or alarms go to a nonexistent inbox. The address must be verified in the SES console before the first send.

App secrets (JWT, integrations) are created by `modules/secrets/` with `random_password` and stored as SSM SecureString. The app reads them with `SecretsProviderAwsSsm`.

---

## Cycle cost

| Stage | Time | Cost |
|---|---|---|
| `make bootstrap` (once) | ~5 min | ~$0.05 + ~$0.04/month idle |
| `make deploy` | ~12 min | starts a session |
| Session 1–3 days | — | ~$2.70/day |
| `make destroy` | ~10 min | ends a session |
| Total 3-day session | — | **~$8** |
| `make wipe` | ~15 min | idle at $0/month |

---

## Providers and versions

```hcl
terraform { required_version = "~> 1.7.0" }
required_providers {
  aws    = { source = "hashicorp/aws", version = "~> 5.70" }
  random = { source = "hashicorp/random", version = "~> 3.6" }
  null   = { source = "hashicorp/null", version = "~> 3.2" }
}
```

`.terraform.lock.hcl` versioned. Provider upgrade: short ADR or note in [`adr/README.md`](adr/README.md) + `terraform plan` with no drift.

---

## Tagging

Provider `default_tags`: `Project=nica-erp`, `Environment=$var.environment` (`demo` → `prod-tenant-X`), `ManagedBy=terraform`, `Owner=$var.owner_email`, `CostCenter=pre-launch` (→ `tenant:<slug>`), `Component=infrastructure` (override per resource). Enables Cost Explorer grouping from day 1.

---

## Common incidents

- **`ECR repository does not exist`** → missing `make bootstrap`.
- **`alembic upgrade head` fails** → fix the migration and rerun `scripts/run-migrations.sh` (infra is already applied).
- **`DependencyViolation` on VPC** → hung Lambda ENI (5–20 min for Lambda to release it). `aws ec2 describe-network-interfaces --filters 'Name=vpc-id,Values=<ID>' 'Name=status,Values=available'`. Wait; if > 20 min, `aws ec2 delete-network-interface --network-interface-id <ID>` (only if `available`). Retry destroy.
- **RDS `final snapshot already exists`** → only applies if you enabled the final snapshot (post-MVP). Suffix collision; delete (`aws rds delete-db-snapshot`) or pass another `final_snapshot_suffix`.
- **Cognito `Domain already exists`** after re-bootstrap → AWS retains the prefix for a few minutes; wait ~5 min.
- **SES `Email address is not verified`** → sandbox + email-only; verify the recipient from the SES console or `aws ses verify-email-identity --email-address user@example.com`.
- **Unexpected high cost** → run `verify-destroyed.sh`. If NAT alive: `aws ec2 describe-nat-gateways --filter "Name=state,Values=available"`.

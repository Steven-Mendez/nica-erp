# 11 — Terraform and Deployment

Four operations, two surfaces:

- **Operator host, operator-only:** `make bootstrap`, `make destroy-bootstrap`. Direct `terraform apply/destroy` against the `nica-erp` AWS CLI profile. These create / remove the persistent infrastructure that the workflows depend on (state bucket, ECR, CloudFront, GitHub OIDC provider, CI IAM roles).
- **GitHub Actions, `workflow_dispatch` only:** `make deploy`, `make destroy`. Thin `gh workflow run` wrappers; the actual work runs on `ubuntu-latest` and assumes a short-lived OIDC role. Push to `main` does NOT auto-deploy.

[ADR-0030](adr/0030-ci-image-publish.md) explains the surface split (supersedes [ADR-0023](adr/0023-no-ci-cd-mvp.md)). One environment: `demo`. Assumes [ADR-0020](adr/0020-no-custom-domain-mvp.md) (no custom domain) and [ADR-0021](adr/0021-ssm-parameter-store.md) (SSM instead of Secrets Manager).

Infrastructure description (service inventory, network topology, sizing) in [`10-infrastructure.md`](10-infrastructure.md). Backup/restore operations in [`13-operations.md`](13-operations.md).

---

## First-time setup

Read this once when you start the project. After step 6 you can run `make deploy` from any machine that has `gh` installed; you only come back to `make bootstrap` if the persistent stack itself changes.

### 1. Host tools (operator's host, one-time)

Two `make` targets verify everything is in place, each fails fast at the first missing tool with the exact install command:

```sh
make doctor              # uv, node, pnpm, docker  (dev tools, needed for local dev + tests)
make doctor-deploy       # terraform, aws, gh      (deploy tools, needed for bootstrap + workflow dispatch)
```

`make doctor-deploy` also checks that the `nica-erp` AWS CLI profile resolves and that `gh` is authenticated — so it doubles as the precondition gate for the rest of this section.

Versions required: Terraform `>= 1.6`, AWS CLI v2, `gh >= 2.0`. macOS install one-liner if anything is missing:

```sh
brew install terraform awscli gh
```

### 2. AWS CLI profile `nica-erp` (operator's host, one-time)

```sh
aws configure --profile nica-erp
# AWS Access Key ID:     <your IAM access key>
# AWS Secret Access Key: <your IAM secret>
# Default region:        us-east-1
# Default output:        json
```

The profile MUST be named exactly `nica-erp` — scripts pin `AWS_PROFILE=nica-erp` and refuse to use the default profile.

The IAM user / role behind that profile needs the following permissions for the bootstrap to succeed:

- **S3**: `CreateBucket`, `Put*`, `Get*`, `Delete*`, `ListBucket`, `ListAllMyBuckets`, `PutBucketVersioning`, `PutBucketPolicy`, `PutBucketPublicAccessBlock`, `PutBucketEncryption`.
- **DynamoDB**: `CreateTable`, `DescribeTable`, `ListTables`, `DeleteTable`, `TagResource`, `UntagResource`, `ListTagsOfResource`.
- **ECR**: `CreateRepository`, `DescribeRepositories`, `DeleteRepository`, `PutLifecyclePolicy`, `GetLifecyclePolicy`, `BatchDeleteImage`, `ListImages`, `TagResource`.
- **CloudFront**: `CreateDistribution`, `GetDistribution`, `UpdateDistribution`, `DeleteDistribution`, `CreateOriginAccessControl`, `GetOriginAccessControl`, `DeleteOriginAccessControl`, `ListDistributions`, `TagResource`.
- **IAM**: `CreateOpenIDConnectProvider`, `GetOpenIDConnectProvider`, `DeleteOpenIDConnectProvider`, `TagOpenIDConnectProvider`, `CreateRole`, `GetRole`, `DeleteRole`, `PutRolePolicy`, `GetRolePolicy`, `DeleteRolePolicy`, `AttachRolePolicy`, `DetachRolePolicy`, `TagRole`, `UntagRole`, `CreateServiceLinkedRole` (first CloudFront use per account).
- **tag**: `tag:GetResources` (for the destroy-bootstrap allow-list check).

`scripts/bootstrap.sh` runs a permissions canary against S3 / DynamoDB / ECR / CloudFront before any `terraform apply`, so a missing permission fails fast with a clear message instead of mid-apply.

Verify the profile works:

```sh
AWS_PROFILE=nica-erp aws sts get-caller-identity
```

### 3. `gh` CLI authenticated (operator's host, one-time)

```sh
gh auth login
# GitHub.com → HTTPS → Login with a web browser
# pick the repository `Steven-Mendez/nica-erp` scope
gh auth status
```

The operator's GitHub account needs write access to the repository, because `gh variable set` (step 5) and `gh workflow run` (step 6) both require it.

### 4. `make bootstrap` (operator's host, one-time per project)

```sh
make bootstrap
```

Provisions, in order, against the `nica-erp` profile:

1. S3 state bucket `nica-erp-tf-state-<account-id>` (versioned, KMS-encrypted).
2. DynamoDB lock table `nica-erp-tf-lock`.
3. ECR repository `nica-erp` (immutable tags, 5-image lifecycle).
4. S3 bucket `nica-erp-web-<account-id>` (private, OAC-bound) and the CloudFront distribution that serves it. CloudFront declares an `/api/*` behavior with `placeholder.invalid` as origin — the deploy script swaps it later.
5. GitHub OIDC provider for `token.actions.githubusercontent.com`.
6. IAM roles `nica-erp-ci-deploy` and `nica-erp-ci-destroy`, each with a trust policy bound to `repo:Steven-Mendez/nica-erp:ref:refs/heads/main` and an inline policy scoped to its workflow's surface (Deny explicit on bootstrap-surface destructive actions — only `destroy-bootstrap` can touch those).

Idempotent: re-running on an already-bootstrapped account is a no-op (`terraform plan` reports "No changes"). The last lines of stdout look like:

```
==> Bootstrap outputs
cloudfront_distribution_domain = d1234abcd.cloudfront.net
tf_state_bucket                = nica-erp-tf-state-469351852594
ecr_repository_url             = 469351852594.dkr.ecr.us-east-1.amazonaws.com/nica-erp
web_bucket                     = nica-erp-web-469351852594
github_oidc_provider_arn       = arn:aws:iam::469351852594:oidc-provider/token.actions.githubusercontent.com
ci_deploy_role_arn             = arn:aws:iam::469351852594:role/nica-erp-ci-deploy
ci_destroy_role_arn            = arn:aws:iam::469351852594:role/nica-erp-ci-destroy

==> Register the CI role ARNs with GitHub
    Run these two commands once (requires `gh auth login` first):

    gh variable set AWS_DEPLOY_ROLE_ARN  --body "arn:aws:iam::469351852594:role/nica-erp-ci-deploy"
    gh variable set AWS_DESTROY_ROLE_ARN --body "arn:aws:iam::469351852594:role/nica-erp-ci-destroy"
```

### 5. Register GitHub repository variables (operator's host, one-time per project)

Copy/paste the two `gh variable set` lines `make bootstrap` printed. Or, equivalently, in the GitHub UI: **Settings → Secrets and variables → Actions → Variables tab → New repository variable** with names `AWS_DEPLOY_ROLE_ARN` and `AWS_DESTROY_ROLE_ARN`.

Verify both are registered:

```sh
gh variable list | grep AWS_
```

These are **variables**, not secrets — the ARN by itself is not a credential. STS only mints a token for a workflow whose `sub` claim matches the trust policy (`refs/heads/main` of this repo).

### 6. First `make deploy` (operator's host triggers a remote workflow)

```sh
make deploy
```

`make deploy` is a thin wrapper around `gh workflow run deploy.yml --ref main`. The command exits in seconds; the actual deploy runs on a GitHub-hosted `ubuntu-latest` runner. Watch the run:

```sh
gh run watch $(gh run list --workflow=deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

What the workflow does, in order:

1. `actions/checkout@v6` with full history (`fetch-depth: 0`) so `git rev-parse HEAD` resolves correctly.
2. AWS auth via OIDC (assumes `nica-erp-ci-deploy`).
3. `docker buildx setup` → `scripts/build-and-push-image.sh` builds the API image (native `linux/amd64`, no QEMU) and pushes it to ECR.
4. Terraform setup + `init -backend-config="bucket=nica-erp-tf-state-<account-id>"` + `apply -var image_tag=<short-sha>` on `infra/terraform/envs/demo`.
5. `scripts/run-migrations.sh` invokes the `nica-erp-migrate` task definition via ECS RunTask and waits for `alembic upgrade head` to finish.
6. `aws ecs update-service --force-new-deployment` rolls the API service to the new task definition.
7. `scripts/deploy-web.sh` runs `pnpm build`, uploads `apps/web/dist/` to the SPA bucket, and creates a CloudFront invalidation on `/*`.
8. Polls `https://<dist>.cloudfront.net/api/healthz` with exponential backoff until the JSON body contains `"db":"ok"` (timeout `DEPLOY_HEALTH_TIMEOUT=300` seconds).
9. Writes a step summary to the run page with: image tag, commit SHA, CloudFront URL, Alembic revision, ECS task definition ARN.

First deploy takes ~20–25 minutes (RDS provisioning dominates). Subsequent deploys on top of a live stack take ~10 minutes.

### 7. Verification

After the workflow turns green:

```sh
make verify                     # curls /api/healthz + SPA root, asserts db:ok + non-null alembic_revision
```

A passing run prints the parsed healthz JSON and the two URLs. A failing run names the failed assertion and exits non-zero, so `make verify` is also safe to chain (`make deploy && make verify`).

Open the SPA URL printed by `make verify` in a browser — the healthz card should show the same values returned by the curl. Then optionally:

```sh
make logs                       # tails CloudWatch /nica-erp/api
make plan                       # terraform plan against demo; expect "No changes"
```

---

### Daily cycle (after first-time setup)

| Action | Command | Surface | Duration |
|---|---|---|---|
| Deploy current `main` | `make deploy` | GHA workflow | ~10 min (warm) |
| Destroy ephemeral stack (keep bootstrap) | `make destroy` | GHA workflow | ~10 min |
| Read API logs | `make logs` | operator's host, read-only | live tail |
| Show public URLs | `make urls` | operator's host, read-only | < 1 s |
| Dry-run Terraform | `make plan` | operator's host, read-only | ~15 s |

### Project close (rare)

`make destroy-bootstrap` runs on the operator's host and removes the persistent stack. It prompts for `nica-erp-bootstrap` at the terminal, refuses if the ephemeral stack is still alive, then empties buckets + ECR before `terraform destroy`. `make wipe` is the convenience that chains `make destroy && make destroy-bootstrap`.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make deploy` says `gh: command not found` | `gh` CLI not installed | `brew install gh` |
| `make deploy` says `not logged in to gh` | Token expired or never ran `gh auth login` | `gh auth login` |
| Workflow fails at AWS auth step with `Could not load credentials` | The two GitHub variables are missing or misnamed | `gh variable list` — should show `AWS_DEPLOY_ROLE_ARN` and `AWS_DESTROY_ROLE_ARN` |
| Workflow fails at AWS auth with `Not authorized to perform sts:AssumeRoleWithWebIdentity` | The trust policy on the IAM role does not match the workflow's `sub` claim | Workflow must run on `refs/heads/main`. Feature branches cannot assume the role by design. |
| `make bootstrap` fails at the permissions canary | The `nica-erp` profile lacks one of the IAM actions listed in step 2 | Inspect the canary output — it names the failing call. Attach the missing permission to the user/role. |
| Workflow fails at health check (timeout 300 s) | Image started but `/api/healthz` returns 5xx; usually RDS not reachable or migrations failed | Inspect the previous step's logs (`run-migrations.sh`) and the ECS task logs via `make logs`. |
| `make destroy-bootstrap` says "ephemeral stack still alive" | The demo env was not destroyed first | Run `make destroy` (the workflow), wait for green, then re-run `make destroy-bootstrap`. |

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

## CI surface

Per [ADR-0030](adr/0030-ci-image-publish.md) (supersedes [ADR-0023](adr/0023-no-ci-cd-mvp.md)):

- `api-checks.yml` and `web-checks.yml` run automatically on push/PR (lint, type-check, unit tests). No AWS access.
- `deploy.yml` and `destroy.yml` run on `workflow_dispatch` only. They assume narrowly-scoped IAM roles via OIDC (no static keys in GitHub). Push to `main` does NOT auto-deploy.
- `make bootstrap` and `make destroy-bootstrap` stay on the operator's host, operator-only. The chicken-and-egg (the bootstrap creates the OIDC provider + the IAM roles the workflows need) makes this unavoidable.

Auto-trigger on push to `main` is a one-line YAML diff in `deploy.yml` (the `nica-erp-ci-deploy` role already trusts that ref). Switch it on when the team grows past one developer.

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

The root `Makefile` is the single operator surface. Targets fall into three groups by execution location, per ADR-0030:

**Operator host (direct on `nica-erp` AWS profile):**

| Target | Effect |
|---|---|
| `make bootstrap` | `scripts/bootstrap.sh` — creates the persistent stack (state bucket, DynamoDB lock, ECR, S3 SPA + CloudFront, GitHub OIDC provider, CI IAM roles). Idempotent. |
| `make destroy-bootstrap` | `scripts/destroy-bootstrap.sh` — refuses while the ephemeral stack is alive; demands a typed `nica-erp-bootstrap` confirmation; empties S3/ECR; runs `terraform destroy` against the bootstrap module. |
| `make build-image` | `scripts/build-and-push-image.sh` — builds the API image on the operator host and pushes to ECR. Hits the Apple-Silicon QEMU segfault; prefer the GHA workflow's build step instead. |
| `make plan` | `terraform plan` against `envs/demo` (read-only). |
| `make logs` | `scripts/tail-logs.sh` — `aws logs tail /nica-erp/api --follow --since 5m --format short`. |
| `make urls` | `scripts/print-urls.sh` — prints the SPA and `/api/healthz` URLs from bootstrap outputs. |
| `make verify` | `scripts/verify-deploy.sh` — smoke-tests the live stack (curl `/api/healthz` + SPA root, asserts `db: ok` + non-null `alembic_revision`). |
| `make wipe` | `destroy` + `destroy-bootstrap` chained. Project-close convenience. |

**GHA dispatch (thin `gh workflow run` wrappers):**

| Target | Effect |
|---|---|
| `make deploy` | `gh workflow run deploy.yml --ref main` — dispatches the deploy workflow which (on `ubuntu-latest`, via OIDC) runs `scripts/deploy.sh`: build-and-push image → terraform apply → run-migrations → ECS force-new-deployment → `scripts/deploy-web.sh` (SPA build + S3 sync + CloudFront invalidation) → healthcheck poll. Ships backend AND frontend in a single run. |
| `make destroy` | `gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral` — dispatches the destroy workflow; fails before any AWS call if `confirm` is not the literal `nica-erp-ephemeral`. |

**Escape hatches (operator host, same scripts the workflows call):**

| Target | Effect |
|---|---|
| `make deploy-local` | `scripts/deploy.sh` — runs the same chain locally. Requires a linux/amd64 host (or a working QEMU) for the image build step. |
| `make destroy-local` | `scripts/destroy.sh` — runs the destroy chain locally. |

There is no `make deploy-web` standalone target. The SPA deploy is owned by `scripts/deploy-web.sh`, which `scripts/deploy.sh` invokes after the backend rollout. Operators who only want to refresh the SPA still go through `make deploy` (or `make deploy-local`) — the backend steps are idempotent when nothing changed.

The Makefile pins `AWS_PROFILE=nica-erp` indirectly via the scripts it delegates to (the scripts skip the pin when `AWS_ACCESS_KEY_ID` is in env, so the same scripts work under GHA OIDC). Targets use literal TAB indentation; help text is generated from `## ` doc comments by `make help`.

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

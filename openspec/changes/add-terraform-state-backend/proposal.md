## Why

[Sprint 01](../../../docs/sprints/01-aws-wiring-rolling-deploys.md) puts
`make bootstrap && make deploy` behind every later sprint's DoD
([ADR-0018](../../../docs/adr/0018-rolling-deploys.md)), and `make destroy`
must return the project to ≈ $0/month. That split forces a hard line
between **persistent** AWS resources (state, image registry, static
hosting) that survive every destroy and **ephemeral** resources (VPC,
RDS, ECS) that get torn down nightly. This change ships only the
persistent half: the Terraform remote backend, the ECR repository, and
the S3 + CloudFront SPA edge — the pieces a later `terraform apply` will
read from and write into. Without them the rest of sprint 01
(`add-api-container-image`, `add-aws-runtime-stack`,
`add-deploy-destroy-automation`) has nowhere to push images and no
shared state to coordinate against.

## What Changes

- New `infra/terraform/bootstrap/` Terraform root with **local state**
  (chicken-and-egg: the state bucket cannot store its own creation)
  that provisions:
  - S3 bucket `nica-erp-tf-state` (versioning on, SSE-KMS with an AWS
    managed key, `BlockPublicAccess` all on).
  - DynamoDB table `nica-erp-tf-lock` (PAY_PER_REQUEST, hash key
    `LockID`).
  - ECR repository `nica-erp` with `IMMUTABLE` tags and a lifecycle
    policy keeping only the last 5 images.
  - S3 bucket `nica-erp-web` (private, SSE-S3, `BlockPublicAccess` all
    on) intended to hold the built SPA.
  - CloudFront distribution fronting `nica-erp-web` via an Origin
    Access Control (OAC); default cert is the CloudFront wildcard
    (`*.cloudfront.net`) — no custom domain, no ACM
    ([ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)).
  - CloudFront **two behaviors are declared from day one**:
    - default `/*` → `nica-erp-web` origin (the active behavior).
    - `/api/*` → an **HTTP origin placeholder** pointing at
      `placeholder.invalid` with `OriginProtocolPolicy=http-only`. The
      origin is intentionally non-functional; `add-aws-runtime-stack`
      replaces the origin DNS with the ALB DNS without recreating the
      distribution.
  - CloudFront custom error responses 403 → `/index.html` (200) and
    404 → `/index.html` (200) so the SPA's TanStack Router can
    handle deep links.
- New tagging convention: every resource SHALL carry
  `Project=nica-erp` so `verify-destroyed.sh` and Cost Explorer can
  filter the project blast radius.
- New `scripts/bootstrap.sh` that runs `terraform -chdir=infra/terraform/bootstrap init/apply -auto-approve` and prints the
  CloudFront distribution domain, the state bucket name, and the ECR
  repository URI to stdout.
- New `scripts/destroy-bootstrap.sh` that requires the operator to type
  the literal string `nica-erp-bootstrap` to proceed, then empties
  `nica-erp-tf-state` (all versions), `nica-erp-web`, and the ECR
  repository before running `terraform destroy -auto-approve`. It
  fails loudly if the ephemeral stack from `add-aws-runtime-stack` is
  still alive (it queries Terraform-managed tags via AWS CLI).
- New root `Makefile` targets `bootstrap` and `destroy-bootstrap` (the
  full `deploy/destroy/wipe/plan/logs/deploy-web` set lands in
  `add-deploy-destroy-automation`). `make wipe` is **not** added here
  because it composes with `destroy` from sprint 01's later change.
  Both `bootstrap` and `destroy-bootstrap` SHALL run on the
  administrator's workstation against the `nica-erp` AWS CLI profile —
  they are admin-only and intentionally do NOT have a GitHub Actions
  workflow surface (sprint 01 §Operations explains why: the bootstrap
  creates the very OIDC provider and CI IAM roles a workflow would
  need to authenticate; chicken-and-egg).
- New `infra/terraform/bootstrap/terraform.tfvars.example` documenting
  `aws_region` (default `us-east-1`) and any optional toggle; the
  actual `terraform.tfvars` is gitignored.
- **GitHub Actions OIDC federation, provisioned here so the CI roles
  the deploy/destroy workflows assume exist by the time `add-deploy-destroy-automation`
  ships its workflows.** New
  `infra/terraform/bootstrap/oidc.tf` declares:
  - One `aws_iam_openid_connect_provider` for
    `token.actions.githubusercontent.com` (AWS hard-limit: one per
    `url` per account), `client_id_list = ["sts.amazonaws.com"]`.
  - Two `aws_iam_role` resources: `nica-erp-ci-deploy` and
    `nica-erp-ci-destroy`. Trust policy on each binds the federated
    principal to `repo:Steven-Mendez/nica-erp:ref:refs/heads/main`
    only — feature-branch workflows SHALL NOT be able to assume
    them. Inline policies are scoped per role: deploy gets ECR push
    + ephemeral-stack apply + state-backend r/w + SPA-bucket put +
    CloudFront invalidation; destroy gets ephemeral-stack destroy +
    state-backend r/w and is explicitly denied the bootstrap-surface
    actions (`s3:DeleteBucket` on state/SPA buckets,
    `ecr:DeleteRepository`, `cloudfront:DeleteDistribution`,
    `iam:DeleteOpenIDConnectProvider`, `iam:DeleteRole`).
  - Two new Terraform outputs `ci_deploy_role_arn` and
    `ci_destroy_role_arn`.
- `scripts/bootstrap.sh` prints the two new role ARNs at the end and
  emits two literal `gh variable set` commands the administrator
  pastes once to register them as repo variables
  `AWS_DEPLOY_ROLE_ARN` / `AWS_DESTROY_ROLE_ARN`.

## Capabilities

### New Capabilities

- `terraform-state-backend`: the S3 bucket + DynamoDB lock table that
  every non-bootstrap Terraform root in this repo SHALL use as its
  remote backend, plus the conventions (KMS, versioning, public-access
  blocks) that protect it.
- `image-registry`: the ECR repository that hosts API container images
  produced by `add-api-container-image` and consumed by ECS task
  definitions in `add-aws-runtime-stack`, including the lifecycle
  policy that bounds storage cost.
- `web-static-hosting`: the private S3 bucket plus the CloudFront
  distribution (OAC, error responses, two-behavior layout with an
  `/api/*` placeholder origin) that serves the SPA today and will
  serve the API at `/api/*` after `add-aws-runtime-stack` wires the
  ALB origin in.
- `bootstrap-automation`: the `bootstrap.sh` / `destroy-bootstrap.sh`
  scripts and the corresponding `make bootstrap` /
  `make destroy-bootstrap` targets, including the operator-confirmation
  workflow and the rule that destroy refuses to run while ephemeral
  resources still exist.
- `aws-iam-ci-federation`: the GitHub-Actions OIDC provider and the
  two IAM roles (`nica-erp-ci-deploy`, `nica-erp-ci-destroy`) the
  workflows in `add-deploy-destroy-automation` assume. The
  bootstrap script's print-out for the two `gh variable set`
  registration commands.

### Modified Capabilities

(none — sprint 00 capabilities are local-only and unaffected)

## Impact

- Affected code: new `infra/terraform/bootstrap/` Terraform root; new
  `scripts/bootstrap.sh`, `scripts/destroy-bootstrap.sh`; new
  Makefile targets `bootstrap` and `destroy-bootstrap`; new
  `infra/terraform/.gitignore` entries for `.terraform/`,
  `terraform.tfstate*`, `terraform.tfvars`,
  `.deploy-image-tag`.
- Affected APIs: introduces public CloudFront URL of the form
  `https://<dist-id>.cloudfront.net/`. The `/api/*` path returns a
  CloudFront 502 / origin error until `add-aws-runtime-stack` lands;
  this is the intended placeholder state.
- Dependencies: requires Terraform ≥ 1.6 and AWS CLI v2 on the
  operator host. Adds a project-wide assumption that the AWS account
  has Cost Explorer enabled with `Project` as an active cost
  allocation tag.
- Systems: the only AWS resources created are the persistent set
  listed above. No VPC, no RDS, no ECS, no Cognito — those land in
  `add-aws-runtime-stack`. Idle cost: state + lock + ECR + S3 web +
  CloudFront with no traffic = effectively $0/month.
- Out of scope (intentionally): production Dockerfile and
  `build-and-push-image.sh` (`add-api-container-image`); ephemeral
  modules `network/`, `data/`, `compute/`, `auth/`, `secrets/`,
  `observability/` and `envs/demo/` (`add-aws-runtime-stack`);
  `make deploy/destroy/plan/logs/deploy-web/wipe`,
  `verify-destroyed.sh`, `print-urls.sh`, `tail-logs.sh`,
  `run-migrations.sh`, `check-credentials.sh`, `deploy-web.sh`,
  `confirm-destroy.sh` and the AWS-vs-local CORS toggle
  (`add-deploy-destroy-automation`).

## Context

[Sprint 01](../../../docs/sprints/01-aws-wiring-rolling-deploys.md)
splits AWS infrastructure into two lifecycles:

- **Persistent** (this change): state backend + image registry + SPA
  edge. Survives every `make destroy`. Cost ≈ $0/month idle.
- **Ephemeral** (`add-aws-runtime-stack`): VPC, RDS, ECS, ALB,
  Cognito, SSM, alarms. Recreated by every `make deploy`, dropped by
  every `make destroy`. Idle cost ≠ $0, which is why it has to be
  destroyable.

The persistent half has its own awkwardness: the Terraform state bucket
cannot itself live in remote state on first apply
(chicken-and-egg), and the CloudFront distribution can only declare
behaviors at create time without recreating the whole distribution on
later changes. Both constraints drive the decisions below.

The constraints come from
[`docs/11-deployment.md` §Bootstrap](../../../docs/11-deployment.md#bootstrap-once),
[ADR-0018](../../../docs/adr/0018-rolling-deploys.md) (rolling deploys
as DoD), and [ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)
(no Route 53, no ACM, no custom domain for the MVP).

## Goals / Non-Goals

**Goals:**

- After `make bootstrap`, the operator has a CloudFront distribution
  serving an empty `nica-erp-web` bucket at `https://<dist-id>.cloudfront.net/`
  and an ECR repository ready to receive its first image push.
- `make bootstrap` is idempotent: re-running it against an
  already-bootstrapped account is a no-op (Terraform plan reports
  "No changes").
- `make destroy-bootstrap` requires explicit operator confirmation,
  empties every bucket and the ECR repo so Terraform can drop them,
  and refuses to run if the ephemeral stack is still alive.
- The CloudFront distribution declares the `/api/*` behavior **on day
  one** so `add-aws-runtime-stack` can attach the ALB DNS without
  recreating the distribution.
- The state bucket protects against accidental loss
  (versioning + KMS + public access block).
- Every persistent resource carries `Project=nica-erp` so Cost Explorer
  and `verify-destroyed.sh` can filter by project.

**Non-Goals:**

- The ephemeral runtime stack (VPC, RDS, ECS, ALB, Cognito, SSM,
  alarms) — `add-aws-runtime-stack`.
- The production Dockerfile and the build/push script that fills the
  ECR repository — `add-api-container-image`.
- The full `deploy / destroy / plan / logs / deploy-web / wipe`
  Makefile surface and the AWS-vs-local CORS toggle —
  `add-deploy-destroy-automation`.
- Custom domain, ACM, Route 53, WAF, X-Ray, Interface VPC endpoints —
  excluded from the MVP tier
  ([`docs/10-infrastructure.md` §Excluded from initial tier](../../../docs/10-infrastructure.md#excluded-from-initial-tier),
  [ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)).
- Cross-account or multi-region setups; everything lands in a single
  AWS account and `us-east-1`.

## Decisions

### Local Terraform state for the bootstrap root

`infra/terraform/bootstrap/` ships **without** a `backend "s3"` block:
the state file lives at `infra/terraform/bootstrap/terraform.tfstate`
on the operator's laptop and is gitignored. Only the ephemeral root
(`envs/demo/`) configures the S3 backend with the bucket and lock
table this change creates.

Rationale: the state bucket cannot store its own creation. Alternatives
considered:

- **Manual `aws s3 mb` + import.** Rejected — every operator would
  repeat the manual step, drift is silent, and `destroy-bootstrap`
  could not symmetrically remove what it created.
- **CloudFormation stack for the backend, then Terraform for the
  rest.** Rejected — adds a second IaC tool just to break the cycle;
  not worth the surface area for ≤5 resources.

The bootstrap state is intentionally low-stakes (no app data, easy to
recreate) so local storage is acceptable.

### Both CloudFront behaviors declared on day one, `/api/*` points at a placeholder

`/api/*` is declared with an HTTP-only origin pointing at
`placeholder.invalid` (an IANA-reserved name guaranteed not to resolve)
so the distribution shape is final before the ALB exists. When
`add-aws-runtime-stack` lands, it changes the origin DNS to the ALB
DNS name and the cache-policy / origin-request-policy IDs in place; no
distribution recreation is required.

Rationale: CloudFront updates that mutate behaviors propagate in
~5 minutes; updates that recreate distributions take 30+ minutes and
hand out new domain names. Locking in the shape now keeps the public
URL stable across the rest of sprint 01.

Alternative considered: ship only the default `/*` behavior in this
change and add `/api/*` later. Rejected — the later change would have
to also re-issue the OAC or change distribution config in two places,
adding coupling for no benefit.

### `nica-erp-web` is private; CloudFront accesses it via OAC

The bucket has `BlockPublicAccess` fully on and an `aws:SecureTransport`
deny policy. CloudFront authenticates to it through an Origin Access
Control (OAC, not the deprecated OAI) signing requests with SigV4.

Rationale: this is the AWS-recommended pattern for S3-backed
distributions and the only one that survives an S3 public-access
audit.

### Two SPA-friendly custom error responses on CloudFront

`403` and `404` from S3 (deep-link to a path that doesn't exist as an
S3 key) are rewritten to `GET /index.html` with HTTP 200. TanStack
Router then resolves the route client-side.

Rationale: this is the standard SPA-on-CloudFront recipe and it costs
nothing.

### ECR with `IMMUTABLE` tags and 5-image lifecycle

Image tags are immutable so a redeploy cannot silently replace what an
older task is still running. The lifecycle policy keeps the 5 most
recent images; anything older is expired.

Rationale: matches the sprint doc; bounds storage cost without
sacrificing rollback range (5 deploys ≈ 1 week of iteration).

### `Project=nica-erp` is the load-bearing tag

Every resource created by this change SHALL be tagged
`Project=nica-erp`. `terraform.tfvars.example` documents this; the
provider-level `default_tags` block applies it transparently.

Rationale: `verify-destroyed.sh` (lands in `add-deploy-destroy-automation`)
filters the AWS account by this tag to assert "no ephemeral nica-erp
resources alive". Cost Explorer also filters on it for the "≈ $0/month
post-destroy" check.

Known caveat: Terraform's `default_tags` interacts oddly with resource
tagging on S3 buckets and ECR repos created before the provider block
materialises the default. Affected resources receive the tag
explicitly as well; `terraform plan` may report a noisy first-time
diff that re-applies cleanly.

### Operator confirmation for `destroy-bootstrap`, not for `bootstrap`

`destroy-bootstrap.sh` requires the operator to type the literal
string `nica-erp-bootstrap` on stdin before doing anything. It then
empties versioned objects in `nica-erp-tf-state`, all objects in
`nica-erp-web`, and all images in the ECR repo before
`terraform destroy`. `bootstrap.sh` runs with `-auto-approve` because
it only creates things.

Rationale: the bootstrap state is small but irrecoverable
(deleting the state bucket strands the rest of the project). The
prompt is the cheapest guardrail.

### `destroy-bootstrap` refuses to run while the ephemeral stack is alive

Before deleting anything, `destroy-bootstrap.sh` calls
`aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp` and exits non-zero if any
resource exists outside the bootstrap set (network/, data/, compute/,
auth/, secrets/, observability/, demo/). The check tolerates the
bootstrap resources by name.

Rationale: blowing away the state bucket while ECS/RDS is still alive
leaves orphan AWS resources with no IaC handle. Forcing a
`make destroy` first preserves the symmetry of the bootstrap/ephemeral
lifecycles.

## Risks / Trade-offs

- **Risk**: A `terraform plan` after `make bootstrap` shows noisy
  diffs for `default_tags` on S3/ECR. → **Mitigation**: documented in
  this design and in the sprint test list as an accepted caveat;
  re-applying converges to a clean plan.
- **Risk**: The `/api/*` placeholder origin returns CloudFront 502
  errors visible to anyone who hits the URL between bootstrap and
  the runtime stack landing. → **Mitigation**: only the operator
  knows the URL; no DNS, no advertising. The state is intentional and
  short-lived.
- **Risk**: Local bootstrap state on a single operator laptop is a
  single point of failure. → **Mitigation**: the state is trivially
  recreatable (`terraform import` the 5 resources by ARN if the
  laptop dies); the assets it protects (the state bucket, ECR repo,
  SPA bucket) carry their own data.
- **Risk**: ECR `IMMUTABLE` tags block a re-push of the same tag on a
  failed deploy. → **Trade-off**: accepted; `build-and-push-image.sh`
  in `add-api-container-image` always tags with `GIT_SHA`, which is
  unique per commit.
- **Risk**: KMS-encrypted state bucket adds a small per-request KMS
  charge and a tighter IAM surface (state operators need
  `kms:Decrypt` on the key). → **Trade-off**: accepted for the
  defence-in-depth gain over SSE-S3.
- **Risk**: CloudFront error-response rewrites mask real S3 403s
  (e.g., a misconfigured OAC) as SPA 200s. → **Mitigation**: a
  failing OAC also breaks `make deploy-web` (later change) which
  fails noisily; the mask only affects user-facing reads.

## Migration Plan

This change has no prior AWS state to migrate from
(sprint 00 is local-only).

- Deploy:
  1. Operator authenticates against AWS
     (`aws sso login` / `AWS_PROFILE`).
  2. `make bootstrap` runs `terraform init && terraform apply -auto-approve`
     against `infra/terraform/bootstrap/`.
  3. The script prints the CloudFront distribution domain, the state
     bucket name, and the ECR repository URI to stdout.
- Rollback: `make destroy-bootstrap`. The script empties the buckets
  and ECR, then `terraform destroy -auto-approve`. Local state file
  remains on disk but references nothing.

## Open Questions

- (none — design constraints are fully pinned by sprint 01 and the
  cited ADRs)

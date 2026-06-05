## Context

By the time this change lands, the persistent edge already exists
(`add-terraform-state-backend`) and there is an API image waiting in
ECR (`add-api-container-image`). What's missing is everything that
actually executes the image, talks to a database, and is reachable
from the internet through the CloudFront distribution's `/api/*`
behavior.

The sprint doc
([sprint 01](../../../docs/sprints/01-aws-wiring-rolling-deploys.md)
§Ephemeral modules) names the modules and most of the toggles. The
real design work is in the seams:

- How does the new ALB DNS name get into the CloudFront distribution
  that the bootstrap root owns, without either root re-creating the
  distribution and changing the public URL?
- How does the API task discover the database URL when SSM is the
  source of truth and the ECS task definition is created before the
  DB password exists in the same `terraform apply`?
- How does the migration task share its image with the API service
  without forcing a "deploy migration → deploy API" two-step?
- Which Cognito decisions have to be locked in on day one to avoid a
  later User Pool recreation?

This document explains those seams. Resource shapes the sprint doc
already fixes are not re-litigated here.

The relevant ADRs are
[ADR-0017](../../../docs/adr/0017-backups-pitr.md) (no PITR / no
final snapshot pre-launch),
[ADR-0018](../../../docs/adr/0018-rolling-deploys.md) (destroy/recreate
as DoD),
[ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md) (no custom
domain, no ACM, no Route 53),
[ADR-0021](../../../docs/adr/0021-ssm-parameter-store.md) (SSM
SecureString over Secrets Manager).

## Goals / Non-Goals

**Goals:**

- After `terraform -chdir=infra/terraform/envs/demo apply`, a curl
  against `https://<dist-id>.cloudfront.net/api/healthz` returns
  `db:"ok"` and the real Alembic revision.
- The same `terraform destroy` removes every resource declared by
  this change without leaving orphans tagged `Project=nica-erp`.
- The public CloudFront URL never changes across a destroy/recreate
  cycle (the distribution is bootstrap-owned and only one origin
  attribute moves).
- The migration task runs on the same image as the API task; there
  is no separate "migration image" lifecycle to maintain.
- The Cognito User Pool's `custom:active_tenant` attribute is
  reachable from sprint 02/03 without re-creating the pool, even
  though sprint 01 leaves it empty.
- API auto-scaling exists in Terraform from day one as a no-op
  (`min=max=1`) so later sprints flip variables, not files.

**Non-Goals:**

- HTTPS termination at the ALB. CloudFront terminates TLS at the
  edge; the ALB→CloudFront leg is HTTP `:80` only
  ([ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)).
- Multi-AZ RDS, RDS Proxy, read replica, performance insights.
  Modules accept these as variables but ship with them off.
- Backups, snapshots, point-in-time-recovery
  ([ADR-0017](../../../docs/adr/0017-backups-pitr.md)). Pre-launch
  posture is "data loss on destroy is acceptable".
- Cognito Hosted UI, password complexity beyond defaults, MFA. The
  user pool exists for JWT issuance; sprint 02 fleshes it out.
- The migration runner script and Makefile targets — those land in
  `add-deploy-destroy-automation`.
- WAF, X-Ray, GuardDuty, Interface VPC endpoints, NAT-per-AZ.

## Decisions

### CloudFront `/api/*` origin swap lives in `envs/demo/`, not in `bootstrap/`

The bootstrap root created the `/api/*` behavior pointing at
`placeholder.invalid`. This change's `envs/demo/` root reads the
distribution via `data "aws_cloudfront_distribution"` and updates
**only the `api-placeholder` origin's `DomainName`** to the ALB DNS
name. It does this with an `aws_cloudfront_distribution` resource
that uses `lifecycle { ignore_changes = [default_cache_behavior, custom_error_response, ordered_cache_behavior[0].cache_policy_id, ...] }`
so the demo root never fights the bootstrap root over the
distribution's other attributes.

Rationale: the alternatives are worse.

- **Move the distribution into `envs/demo/`.** Rejected — destroy
  would tear down the distribution, change the public URL on
  recreate, and orphan the bootstrap state.
- **Make `envs/demo/` import the distribution.** Rejected — both
  roots would now race on the distribution's state; whichever
  applied last would silently roll back the other's changes.
- **Use the
  [`aws_cloudfront_distribution_origin` standalone resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudfront_distribution).**
  This resource does not exist in the AWS provider; CloudFront
  origins are only configurable as nested blocks. The
  `ignore_changes` pattern is the supported workaround.

Cost: ~5 minutes of CloudFront propagation delay on every
`make deploy` while the new ALB DNS becomes effective. Verified
acceptable in the sprint doc's DoD.

### SSM SecureString is the only DB credential source

The RDS module emits the username/password to three SSM parameters
(`/nica-erp/demo/rds/url`, `/nica-erp/demo/rds/username`,
`/nica-erp/demo/rds/password`) and never to Terraform outputs. The
ECS task definition references them via the `secrets` block (not
`environment`), so the values stay in SSM and only land in the
container's environment at task launch.

Rationale: matches
[ADR-0021](../../../docs/adr/0021-ssm-parameter-store.md). Avoids
writing the password to the Terraform state file in cleartext
beyond the random_password resource itself (which is still in
state, but at least nothing else references it).

Alternative considered: AWS Secrets Manager with automatic
rotation. Rejected for the MVP — adds $0.40/secret/month and a
rotation Lambda we don't need yet.

### Migration task definition shares the API image

`nica-erp-migrate` and `nica-erp-api` are two separate task
definitions that read the same `image` argument from a shared
variable. The migration task overrides `command` to
`["alembic","upgrade","head"]`. It is never tied to an ECS service;
it runs only via `aws ecs run-task` from the migration script
(belongs to `add-deploy-destroy-automation`).

Rationale: keeping the image identical means migrations and the API
always see the same Alembic version graph. Splitting the task
definitions (rather than overriding container `command` on
RunTask) makes the migration definition addressable by ARN and lets
the IAM task role for the migration drop ALB permissions.

### Cognito `custom:active_tenant` declared on day one

The custom attribute is declared with `mutable=true` and an empty
default. Cognito User Pools cannot have new custom attributes added
after creation **only when** the schema is queried via certain APIs
— the safer assumption is "declare every attribute you will ever
need". Sprint 03 will populate it when tenants are created/switched.

Rationale: pool recreation strands every user record. Cheap to
declare now.

### Cognito user pool domain uses the default `cognito-idp.us-east-1.amazoncognito.com` prefix

The pool domain prefix is `nica-erp.auth.us-east-1.amazoncognito.com`
(`nica-erp` as the chosen prefix; the rest is AWS-provided). No
custom domain, no ACM. The Hosted UI is not used in the MVP but the
domain still exists because Cognito only exposes the
`/.well-known/jwks.json` and `/oauth2/*` endpoints when a domain is
attached.

Rationale: matches
[ADR-0020 §Cognito user pool domain](../../../docs/adr/0020-no-custom-domain-mvp.md#cognito-user-pool-domain).

### Single NAT Gateway, not one per AZ

NAT Gateways cost ~\$0.045/h each. Multi-AZ NAT is the recommended
production pattern; for MVP demo we accept that if AZ-a goes down,
private-subnet outbound traffic fails. The API service still has
public-subnet ALB ingress from AZ-b, but ECS tasks in AZ-b cannot
reach the internet — including ECR for image pulls.

Rationale: matches
[`docs/10-infrastructure.md` §NAT topology](../../../docs/10-infrastructure.md).
The trade-off is documented and accepted at the MVP tier.

### ALB ingress restricted to the CloudFront prefix list

The ALB security group accepts ingress on `:80` **only** from the
AWS-managed prefix list `com.amazonaws.global.cloudfront.origin-facing`.
There is no public CIDR allow rule.

Rationale: enforces "all traffic enters via CloudFront", which is
also where TLS terminates and where the WAF (if/when added) would
plug in. Without this, anyone who discovers the ALB DNS name could
bypass CloudFront entirely.

Caveat: the AWS-managed prefix list updates over time as CloudFront
expands its edge fleet. Terraform refreshes pick up the changes on
the next `apply` without operator action.

### Auto-scaling policy declared, capacity pinned to 1

`api_min_capacity` and `api_max_capacity` are Terraform variables
defaulting to `1`. The target-tracking policy
(`ECSServiceAverageCPUUtilization=50`) is always declared. While
`min==max`, Application Auto Scaling does nothing — but flipping
`api_max_capacity=3` later activates the same policy without
needing a new `aws_appautoscaling_policy` resource.

Rationale: avoids a code change in the sprint that first needs
scaling.

### `skip_final_snapshot=true` and `deletion_protection=false` on RDS

Pre-launch, every `make destroy` drops the RDS instance. The
next deploy recreates it and runs `alembic upgrade head` plus seed
to restore a working state.

Rationale: explicit ADR
([ADR-0017](../../../docs/adr/0017-backups-pitr.md)). Production
will flip both flags before any real user data lands.

### Pre-launch posture: empty `LOCAL_JWT_SECRET` SSM placeholder

Sprint 02 will land Cognito-issued JWT validation. Until then, the
SSM placeholder `/nica-erp/demo/jwt/secret` is declared with an
empty `value` and Terraform `lifecycle { ignore_changes = [value] }`
so an operator can drop a value in via `aws ssm put-parameter`
without Terraform reverting it.

Rationale: the parameter shape stays stable so sprint 02 just fills
the value.

## Risks / Trade-offs

- **Risk**: CloudFront origin update lag (5 minutes typical) means
  the first request after a deploy can hit a propagating
  distribution and return 5xx. → **Mitigation**: the deploy script
  in `add-deploy-destroy-automation` polls `/api/healthz` with
  exponential backoff before declaring success.
- **Risk**: Cognito Hosted UI domain prefix collisions across AWS
  accounts (the global prefix `nica-erp` may already be taken). →
  **Mitigation**: variable `cognito_domain_prefix` defaults to
  `nica-erp` but accepts an override; the operator can pick
  `nica-erp-demo` or similar if the default is taken.
- **Risk**: A failed migration leaves the RDS instance ahead of the
  API expected revision. → **Mitigation**: ECS RunTask exit code is
  checked by the migration script (in
  `add-deploy-destroy-automation`); a non-zero exit blocks the API
  service from updating.
- **Risk**: Single NAT Gateway means an AZ-a outage takes the
  whole API offline. → **Trade-off**: accepted at the MVP tier;
  the alternative (NAT per AZ) doubles the cost.
- **Risk**: ALB SG ingress rule references the CloudFront-managed
  prefix list whose underlying set of CIDRs changes asynchronously.
  → **Mitigation**: Terraform refresh picks up changes; a once-a-week
  `terraform plan` is enough to keep the SG aligned.
- **Risk**: KMS key rotation on `alias/aws/ssm` is fully managed by
  AWS and not surfaced in alarms. → **Trade-off**: acceptable
  while pre-launch; revisit at production-readiness.
- **Risk**: `terraform destroy` of the demo env races against
  CloudFront still routing to the ALB; the ALB deletion succeeds
  but in-flight requests get connection-reset errors. → **Trade-off**:
  accepted; demo-tier traffic is operator-only.

## Migration Plan

This change does not migrate prior AWS state; it adds new resources
that have no predecessor.

- Deploy:
  1. Ensure `add-terraform-state-backend` and
     `add-api-container-image` are applied; `.deploy-image-tag`
     exists.
  2. `terraform -chdir=infra/terraform/envs/demo init`.
  3. `terraform -chdir=infra/terraform/envs/demo apply` with
     `alert_email` and (optionally) `image_tag` overrides.
  4. Wait for the CloudFront distribution to converge (typically
     5 min); curl `/api/healthz`.
- Rollback: `terraform -chdir=infra/terraform/envs/demo destroy`
  removes every resource introduced here and reverts the
  CloudFront `/api/*` origin to `placeholder.invalid` via the
  `lifecycle { create_before_destroy = false }` ordering on the
  origin-swap resource.

## Open Questions

- (none — every decision is pinned by sprint 01, the cited ADRs,
  and `docs/10-infrastructure.md`)

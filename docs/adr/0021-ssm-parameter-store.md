# ADR-0021 — Secrets in SSM Parameter Store

**Status**: Accepted
**Date**: 2026-05-23

## Context
Secrets to handle: RDS credentials, JWT signing key for the local IdP ([ADR-0005](0005-cognito-with-local-idp.md)), SMTP credentials, future integrations (BCN scraper, payment gateways). Constraints from the rest of the stack:

- Deploy/destroy on demand ([ADR-0003](0003-deploy-destroy-per-env.md)) — secrets must survive `make destroy` but the store cost should not.
- Single-dev MVP — no rotation automation in flight; JWT rotation is manual, deliberate.
- Idle target ≈ $0/month ([ADR-0020](0020-no-custom-domain-mvp.md)) — every fixed monthly fee gets challenged.

AWS Secrets Manager was the first instinct (managed rotation, native versioning, default KMS, ECS injection). Two problems killed it for MVP:

1. **Cost** — $0.40/month × 3 = $1.20/month. With Route 53 removed by [ADR-0020](0020-no-custom-domain-mvp.md), this became the single most expensive idle component.
2. **Recovery window** — `terraform destroy` leaves secrets in `scheduled for deletion` (7–30 days), still billing, and re-bootstrapping with the same name fails with `InvalidRequestException` until the window elapses or `--force-delete-without-recovery` is invoked. Hard gotcha on every recreate.

SSM Parameter Store SecureString offers exactly what's actually used (KMS-encrypted, ECS `secrets[]` injection with identical ARN syntax) at zero idle cost and no recovery window. The features Secrets Manager wins on (managed rotation, version labels) aren't in use.

## Decision
**All persistent secrets in SSM Parameter Store as `SecureString`, with `.env.local` (gitignored) for dev.**

- **Persistent secrets** (`/nica-erp/db/master`, `/nica-erp/jwt/signing-key`, `/nica-erp/integrations/*`): SSM Parameter Store SecureString, KMS `alias/aws/ssm`, standard tier.
- **Non-sensitive config** (URLs, flags, endpoints): SSM Parameter Store standard String under `/nica-erp/config/*`.
- **Local dev**: `.env.local` with the same names; `SecretsProviderLocal` reads from `os.environ`. Mailpit/Postgres use fixed credentials documented in [`../15-local-development.md`](../15-local-development.md).
- **Runtime**:
  - ECS task definition references SSM ARNs in `secrets[]`.
  - Lambdas read via `boto3.client("ssm").get_parameter(WithDecryption=True)` at cold start and cache.
  - `SecretsProvider` port isolates the swap (~20 LOC adapter).
- **IAM**: task role + Lambdas get `ssm:GetParameter[s]` on `parameter/nica-erp/*` + `kms:Decrypt` on `alias/aws/ssm`. No `secretsmanager:*` permissions.

### Rotation policy
- **RDS credentials** — not rotated automatically in MVP. Reconsider at first productive tenant.
- **JWT signing key** — manual, deliberate, only after a suspected leak. Rotation invalidates all sessions (desired effect).
- **Integrations** — case by case.

### JWT compromise runbook
1. `openssl rand -hex 32` → new key.
2. `aws ssm put-parameter --name /nica-erp/jwt/signing-key --value <new> --overwrite --type SecureString`.
3. `aws ecs update-service --force-new-deployment` to pick up the new key.
4. Log the incident and date. All sessions invalidated.

Formalize as `runbooks/jwt-key-rotation.md` ([`../13-operations.md`](../13-operations.md)) if executed more than once.

## Consequences
- (+) **$1.20/month → $0** for the three persistent secrets.
- (+) No recovery window — `make wipe` + re-bootstrap works immediately.
- (+) Same ECS `secrets[]` syntax as Secrets Manager; future reversal is mechanical.
- (+) SSM free tier covers all usage (< 10k parameters, ≤ 4 KB each).
- (+) Unifies with SSM already used for non-sensitive config — one API, one base IAM permission.
- (+) `SecretsProvider` port makes dev↔prod swap trivial.
- (−) No automatic rotation. Acceptable: nothing was rotating anyway. When first productive tenant requires it, revert `db/master` to Secrets Manager (plan below).
- (−) SSM versioning is shallower (100 versions, no `AWSCURRENT`/`AWSPENDING` labels). Sufficient.
- (−) 4 KB per-parameter cap (standard tier). If exceeded, upgrade to advanced ($0.05/month each) or split.
- (−) SSM throughput is lower (~40 TPS standard vs 10k Secrets Manager). Sufficient: API reads at startup and caches.
- (−) Manual JWT rotation is fragile. Mitigations: `.env.local` in `.gitignore` from sprint 00; pre-commit hook rejecting staged `.env*` files; minimum entropy (`openssl rand -hex 32`).
- (−) Two-tier discipline (SecureString vs standard String): "if rotating it matters, SecureString; if it only changes with a re-deploy, standard".

## Alternatives
- **Keep AWS Secrets Manager** — rejected: $1.20/month + recovery-window gotcha for zero feature value in MVP.
- **SSM advanced tier** — rejected: $0.05/parameter unnecessary at current sizes.
- **Env vars in task definition** — rejected: visible in CloudTrail/console.
- **HashiCorp Vault / Doppler / Bitwarden / GitHub Secrets** — rejected: external dependency or operational overhead; GitHub Secrets is CI-only and conflicts with [ADR-0023](0023-no-ci-cd-mvp.md).

## Reversal plan (when needed)
When managed RDS rotation becomes required:
1. Create `aws_secretsmanager_secret` for `nica-erp/db/master`, copy value from SSM.
2. Update `secrets[].valueFrom` for `DB_CREDENTIALS` to the new ARN.
3. Enable `aws_secretsmanager_secret_rotation` with the AWS-managed Lambda.
4. JWT and other secrets stay in SSM.
5. Extend the adapter (`SecretsProviderHybrid`) to dispatch by ARN prefix.
6. Write a new ADR superseding this one for that secret class.

## Revisit triggers
- First productive tenant — re-evaluate RDS managed rotation.
- A single persistent secret exceeds 4 KB.
- SSM `GetParameter` throughput approaches the 40 TPS limit (only plausible if caches are removed).
- JWT rotation gets executed more than once — formalize runbook and consider automation.

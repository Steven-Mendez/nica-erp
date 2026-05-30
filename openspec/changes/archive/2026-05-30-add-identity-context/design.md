## Context

This change is the first vertical slice on top of the walking skeleton
([`add-backend-walking-skeleton`](../archive/2026-05-25-add-backend-walking-skeleton/proposal.md))
and the AWS runtime stack ([`add-aws-runtime-stack`](../add-aws-runtime-stack/proposal.md)).
The architectural envelope is fixed by:

- [`docs/sprints/02-identity-and-rbac.md`](../../../docs/sprints/02-identity-and-rbac.md)
  — the sprint contract (this change must not exceed it; RBAC is excluded
  despite the file name).
- [`docs/06-security-model.md`](../../../docs/06-security-model.md) — the
  canonical `IdentityProvider` port, JWT TTLs, lockout policy, the
  `auth_local_users` table shape, and the threat-surface checklist.
- [`docs/08-api-conventions.md`](../../../docs/08-api-conventions.md) —
  the auth endpoint allowlist, the RFC-7807 problem-details contract,
  and the public-vs-authenticated split.
- [`docs/09-frontend.md`](../../../docs/09-frontend.md) — feature layout,
  permission gating (out of scope here but the structure is fixed), and
  the OpenAPI-typed client that the auth feature consumes.
- [ADR-0005](../../../docs/adr/0005-cognito-with-local-idp.md) — Cognito +
  local IdP; the **shared claim shape** between adapters is the contract
  that makes the port swap transparent.
- [ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md) — no custom
  domain, so SES has no domain identity and Cognito uses the default
  user-pool-domain prefix.
- [ADR-0021](../../../docs/adr/0021-ssm-parameter-store.md) — all secrets
  in SSM; `LOCAL_JWT_SECRET` lives in `.env.local` and never in AWS.

The walking-skeleton 0001 migration already shipped the `users`
placeholder and the `outbox` table with `tenant_id NOT NULL` — this
change extends the row shape and writes the first event, but does **not**
backfill anything because no users exist yet.

## Goals / Non-Goals

**Goals**

- A contributor with a clean checkout can run
  `make local-up && make migrate && make api && cd apps/web && pnpm dev`,
  open `localhost:5173/signup`, complete the loop through Mailpit, and
  reach `/me` in under five minutes — without touching AWS.
- An operator with an `nica-erp` AWS profile can run `make deploy`,
  verify the SES sender address in the console, sign up against the live
  Cognito pool, and reach `/me` with a real RS256 JWT — without code
  changes between local and deployed.
- The `IdentityProvider` port is the **only** identity-related contract
  visible to `application/use_cases/`. A future migration to Keycloak /
  Okta / Auth0 changes nothing under `domain/` or `application/`.
- The `domain-purity` import-linter contract refuses any `boto3`,
  `sqlalchemy`, or `fastapi` import that creeps into
  `contexts.identity.domain`.
- The signup → verification → login → `/me` flow is exercised by an
  E2E test that hits Mailpit and pulls the code out of the captured
  message body, and by an integration suite that runs
  `IdentityProviderLocal` against a real Postgres testcontainer.

**Non-Goals**

- RBAC, the permission catalogue, `tenant_members`, the `require(...)`
  dependency, and the `Actor` materialisation — all sprint 03 ([ADR-0022](../../../docs/adr/0022-rbac-model.md)).
- Tenant creation, Postgres RLS, `current_tenant.set(...)`,
  `SET LOCAL app.tenant_id` — sprint 03 ([ADR-0002](../../../docs/adr/0002-postgres-rls.md)).
- The welcome email handler and the async notifications worker — sprint 08
  consumes `UserRegistered` from the outbox.
- The invitation creation endpoint, the `tenants` table, member roles —
  sprint 03. This change only **whitelists** `POST /v1/invitations/{token}/accept`
  so future invitation routes don't need middleware churn.
- Refresh-token rotation, `ENABLE_TOKEN_REVOCATION`, BFF + HttpOnly
  cookies — post-MVP per
  [`docs/18-roadmap.md`](../../../docs/18-roadmap.md).
- SES domain identity, DKIM, SPF, exit-from-sandbox ticket — meaningful
  only with a custom domain.
- `USER_SRP_AUTH` — re-evaluated before the first productive tenant.
- Multi-region failover, Cognito user-pool replication, cross-region SES
  identity.

## Decisions

### Identical JWT claim shape between adapters

`{sub, email, email_verified, custom:active_tenant, aud, iss, exp, iat}`
is emitted by **both** `IdentityProviderLocal` (HS256) and Cognito
(RS256). The middleware switches the signature validation strategy by
`APP_ENV` but extracts the same fields. This is the contract that makes
the port swap transparent — and the reason `update_active_tenant` on the
port can be implemented identically by both adapters (the local one
patches `attributes['custom:active_tenant']` in `auth_local_users`;
Cognito calls `AdminUpdateUserAttributes`).

Alternative considered: let each adapter define its own claim shape and
abstract over them in the middleware. Rejected — that pushes the
mapping into the middleware and makes every test fixture aware of two
shapes.

### `auth_local_users` exists only when `APP_ENV=local`

Migration 0002's `upgrade()` reads `os.environ["APP_ENV"]` and creates
the table only when the value is `local`. In AWS the table is absent
from the schema entirely. `downgrade()` drops the table only if it
exists (`IF EXISTS`).

Rationale: the table holds password hashes and verification codes that
have no purpose in AWS, where Cognito owns those secrets. Keeping the
schema clean is consistent with the security-model rule that "password
hash lives in the IdP — Cognito in prod, `auth_local_users` in dev —
never in `users`".

Alternative considered: always create the table; never write to it in
AWS. Rejected — leaves dead, sensitive schema in prod that is easy to
mistakenly populate.

Alternative considered: use a separate Alembic branch / a second
migration tree. Rejected — Alembic branches are heavy for a single
table and complicate `alembic upgrade head`.

Trade-off: `migration 0002` is no longer a pure schema migration; it
reads an env var. We accept it because the env var is already authoritative
(it picks the adapter at runtime). The migration logs the branch it took
so operators see which path applied.

### `UserRegistered` rides the outbox with the system-global tenant sentinel

`confirm_signup` writes `identity.UserRegistered v1` into `outbox` in
the same `UnitOfWork` that flips `email_verified=true`. Since
`outbox.tenant_id` is `NOT NULL` (frozen by the walking skeleton), the
row uses the sentinel `'00000000-0000-0000-0000-000000000000'`. The
sentinel is the **canonical convention** for every MVP event published
without an active tenant (signup, password reset). The outbox table has
no RLS, so the sentinel is a semantic marker, not an isolation boundary;
the publisher (sprint 07) routes these as **global** events on
EventBridge.

Alternative considered: relax the NOT NULL constraint or pick the tenant
of the first invitation the user accepts. Rejected — relaxing NOT NULL
breaks RLS later; picking a tenant retroactively couples signup to
sprint 03's tables.

### Synchronous signup verification vs. async via the outbox

The signup-verification and password-reset emails are sent **directly
from the use case** (`EmailSender.send(...)`), not via the outbox. The
user is waiting for the response and needs the mail to land before the
HTTP call returns. Sprint 08's notifications worker handles **only**
the asynchronous notifications (welcome email triggered by
`UserRegistered`, invoice issued, low stock, member invited).

Trade-off: a transient SES failure surfaces as a 500 on the signup call.
Acceptable for MVP — the operator gets an alarm on the SNS `nica-erp-alerts`
topic and the user can retry. Moving signup verification onto the outbox
post-MVP is a small change because the contract is one method.

### `EmailSender` port lives in the identity sprint but is a shared kernel concern

The port is introduced here because identity is the first context that
needs it, but it sits in `contexts.identity.application.ports.outbound`
only for sprint 02. Sprint 08 promotes it into `shared_kernel` when the
second consumer arrives — until then, putting it in `shared_kernel` would
be premature abstraction.

### Cognito JWKS cache: 24h TTL, refresh-on-miss, stale-on-error

A single dict guarded by a lock, scoped to the Fargate task process.
TTL 24h matches Cognito's signing-key rotation cadence (rare in
practice). On a cache miss the adapter fetches once under the lock so
concurrent requests do not stampede. If the JWKS endpoint errors and a
stale cache is available, the adapter SHALL use the stale cache rather
than reject traffic — the alternative is a hard outage for a transient
upstream blip.

Alternative considered: an LRU with no staleness fallback. Rejected —
strict cache invalidation prefers correctness over availability; for a
JWKS that rotates monthly, availability is the better trade.

### `USER_PASSWORD_AUTH` over `USER_SRP_AUTH` for the MVP

The SPA does not have a client secret, so SRP would require shipping a
client-side SRP implementation. `USER_PASSWORD_AUTH` lets the SPA hand
the password to the API (over HTTPS via CloudFront), which forwards to
Cognito server-side. Trade-off: the API sees the plaintext password
once per login; acceptable given the API is the trust boundary and
Cognito's `AdvancedSecurityMode` (post-MVP) provides additional defence.
Sprint-02 documents the re-evaluation at first productive tenant.

### Auth middleware order

`AuthMiddleware` is added **after** `CORSMiddleware`, so that 401
responses still carry the CORS headers the SPA needs to read the error
body in dev. The allowlist is checked first by path prefix; matching
routes skip JWT validation entirely.

### Frontend tokens in JS memory only

This is a hard rule from
[`docs/06-security-model.md`](../../../docs/06-security-model.md). The
SPA loses the session on reload; the 401 interceptor calls
`POST /v1/auth/refresh` exactly once with the in-memory refresh token,
retries the original request once, and routes to `/login` on a second
failure. No `localStorage`, no `sessionStorage`, no cookies. The BFF +
HttpOnly cookie hardening is post-MVP.

### SESv1 boto3 client, SESv2 Terraform resource

The application calls `boto3.client("ses")` (SESv1) to match the
verbatim wiring in
[`docs/sprints/02-identity-and-rbac.md` §Wiring](../../../docs/sprints/02-identity-and-rbac.md#wiring).
The Terraform module uses `aws_sesv2_email_identity` (the v2 resource)
because the v1 resource `aws_ses_email_identity` does not support the
`tags` argument, and we need `Project=nica-erp` on the identity for
cost attribution. Both resources verify the same underlying SES
identity catalogue — a v1 `send_email` call against an address
verified by the v2 resource works without translation. Trade-off
accepted; revisit if a future sprint moves to SESv2 templates
(`SendBulkEmail`, `ContactList`).

### `aws-email` is its own capability, not a sub-section of `aws-auth`

SES is unrelated to Cognito except that both ship together in sprint 02.
Future SES uses (invoice PDF mailout, customer notifications) will modify
`aws-email`, not `aws-auth`. Keeping them separate avoids accidental
coupling.

### `logout` is in MVP scope, not deferred

`docs/06-security-model.md` §Refresh and revocation declares
`POST /v1/auth/logout` as the canonical revocation surface (calls
`GlobalSignOut` on Cognito; local no-ops because refresh-token
rotation is not active in MVP). Earlier drafts of this proposal
mirrored the sprint's 10-use-case list verbatim and omitted logout —
that was a gap against the canonical security model. The corrected
shape includes `logout` (use case + route) here because:

- The `IdentityProvider` port already declares `global_signout` (11
  methods, not 10) and the IAM allow-list in `aws-auth` already grants
  `cognito-idp:GlobalSignOut`. Without an inbound use case the port
  method is unreachable.
- The SPA's "Sign out" button is core flow, not extra polish.
- Deferring it would force every later sprint that adds a route to
  re-justify why logout still doesn't exist.

The route is authenticated and idempotent (repeated calls return
204), so a stale token replay or double-click does not surface an
error. Access tokens issued before `GlobalSignOut` remain valid until
`exp` (≤ 1 h) — best-effort revocation per the security model.

### `forgot_password` enumeration-resistance lives in the adapter, not the use case

`register_user` and `forgot_password` must return uniform HTTP
responses regardless of whether the email exists. For `register_user`
this is straightforward because Cognito's `UsernameExistsException`
is the only "the user already exists" signal — the adapter swallows
it and returns a success-shaped result.

For `forgot_password` the same shape rule applies, but the adapter
side was originally underspecified: Cognito's `ForgotPassword` raises
`UserNotFoundException` for unknown emails, and the local adapter
naturally raises "row not found" when the email is absent from
`auth_local_users`. If either exception reaches the use case, the use
case can't collapse the branches without inspecting adapter-internal
error types — which would couple application code to adapter
internals. So both adapters SHALL swallow the "unknown email" branch
and return a result whose shape matches the real-account reset. The
use case stays clean; the HTTP layer always returns the same response.

`InvalidParameterException` (genuinely malformed email) still
propagates — that's a 422 the operator needs to see.

### Cognito token validities are pinned, not defaulted

`docs/06-security-model.md` §TTLs specifies access 1 h, ID 1 h,
refresh 30 days. Cognito's default `IdTokenValidity` and
`AccessTokenValidity` are 60 minutes today but have historically
differed across regions (some defaults were 60, some 24h). Pinning
`access_token_validity = 60` minutes, `id_token_validity = 60`
minutes, `refresh_token_validity = 30` days, with explicit
`token_validity_units`, removes region-default drift. The local
adapter does the same by deriving the ID-token TTL from
`settings.jwt_access_ttl_seconds` (default 3600 s).

### `SES_FROM_ADDRESS` env-var injection lives in `aws-compute`, not `aws-secrets`

The SSM parameter itself is declared in the `secrets/` Terraform
module (capability `aws-secrets`), but the ECS task definition that
projects it into the API container's env var lives in the `compute/`
module (capability `aws-compute`). Putting the projection requirement
in `aws-secrets` would couple the capability to a resource it does not
own. Sprint 02 therefore modifies `aws-compute` to extend the API
task definition's `secrets[]` array with `SES_FROM_ADDRESS`. The same
split already holds for `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID`
(SSM parameters declared in `aws-secrets` by sprint 01, but task-def
projection lives in `aws-compute`).

## Risks / Trade-offs

- **Risk**: Operators forget to verify the SES sender address before the
  first signup → Cognito outbound mail bounces silently.
  **Mitigation**: `make deploy` prints a banner with the verification
  link after `terraform apply`; the post-deploy verification step in the
  sprint includes "verify SES sender" as a hard prerequisite.

- **Risk**: The `APP_ENV`-gated migration creates a divergence between
  the local and AWS schemas.
  **Mitigation**: the migration logs which branch it took; a test asserts
  that `auth_local_users` exists under `APP_ENV=local` and does not exist
  under `APP_ENV=aws`. Drift is detectable.

- **Risk**: A misconfigured AWS container with an empty `APP_ENV` could
  fall back to `IdentityProviderLocal`, defeating Cognito.
  **Mitigation**: `bootstrap/settings.py` raises at import time if
  `APP_ENV` is empty (no default value). The Fargate task fails fast.

- **Risk**: Signup-verification SMTP failure surfaces as a 500.
  **Mitigation**: accepted for MVP; the SNS alert and the user's retry
  cover the case. Moving to the outbox post-MVP is one method on one
  port.

- **Risk**: `LOCAL_JWT_SECRET` leaks via a committed `.env`.
  **Mitigation**: the `.env` files remain gitignored; the existing
  pre-commit secret-rejection hook from
  [`add-backend-walking-skeleton`](../archive/2026-05-25-add-backend-walking-skeleton/proposal.md)
  catches it.

- **Risk**: A 401 on a route that the SPA's interceptor cannot recover
  from (e.g. a refresh that itself returned 401 because the refresh
  token was rotated) loops to `/login` and the user re-authenticates.
  **Trade-off**: accepted — refresh-token rotation is not enabled in MVP
  (Cognito default), so this loop only triggers on a long-idle session.

- **Risk**: SES permanent sandbox imposes a ≤ 50 verified-recipient cap,
  which constrains demo usage.
  **Trade-off**: explicit — the MVP is single-operator. Exit makes sense
  only with a custom domain.

## Migration Plan

- This change ships migration 0002. The `upgrade()` is reversible.
- Deploy ordering (local): `make migrate` (applies 0002; in `APP_ENV=local`
  it also creates `auth_local_users`) → `make api` → SPA usable.
- Deploy ordering (AWS): `terraform apply` for the `email/` module + the
  enriched `auth/` module → operator verifies SES sender from the console →
  `make migrate` (applies 0002; `auth_local_users` is **not** created
  because `APP_ENV=aws`) → `make deploy` → first signup.
- Rollback (AWS): `make migrate-down` rolls 0002 back; the `users`
  column expansion is reversible (no data exists yet).

## Open Questions

- None for sprint 02 — the contract is frozen by
  [`docs/sprints/02-identity-and-rbac.md`](../../../docs/sprints/02-identity-and-rbac.md),
  [`docs/06-security-model.md`](../../../docs/06-security-model.md), and
  [`docs/08-api-conventions.md`](../../../docs/08-api-conventions.md).
- Re-evaluation triggers (post-MVP, tracked in
  [`docs/18-roadmap.md`](../../../docs/18-roadmap.md)): switch to
  `USER_SRP_AUTH`; activate refresh-token rotation; introduce a BFF for
  HttpOnly cookies; exit SES sandbox once a custom domain ships; promote
  `EmailSender` to `shared_kernel` once sprint 08 lands its second
  consumer.

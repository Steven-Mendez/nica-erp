## Why

Sprint 02 introduces the project's **first DDD bounded context** (`identity`)
and proves the **port/adapter swap pattern** that every later context relies
on. Signup, email verification, login, refresh, password change/reset, and
the authenticated profile (`/me`) work end-to-end **locally** (against
`IdentityProviderLocal` + Mailpit) and **on AWS** (against the real Cognito
User Pool + SES email identity), with the application layer unaware of
which adapter is wired. The HTTP middleware that pins
`CurrentUserContext` is also delivered here — without it, sprint 03 has
nothing to plug `TenantContext` into and no later endpoint can authenticate.
Reference: [`docs/sprints/02-identity-and-rbac.md`](../../../docs/sprints/02-identity-and-rbac.md)
and the canonical security model in
[`docs/06-security-model.md`](../../../docs/06-security-model.md).

> Despite the sprint file name, **RBAC is out of scope for this change** —
> permissions, roles, and the `require(...)` dependency ship in sprint 03
> ([ADR-0022](../../../docs/adr/0022-rbac-model.md)).

## What Changes

### Backend — `identity` bounded context

- New context `apps/api/src/contexts/identity/` with the canonical hexagonal
  layout (`domain/`, `application/`, `adapters/`).
- **Domain**: `User` aggregate (`id`, `external_sub`, `email`,
  `display_name`, `locale`, `timezone`, `preferences`, timestamps),
  `Email` VO (RFC-5321-ish validation + lowercase normalisation), `Password`
  VO (12+ chars, upper + lower + digit + symbol — policy in
  [`docs/06-security-model.md`](../../../docs/06-security-model.md)),
  events `UserRegistered v1` and `PasswordReset v1`.
- **Application use cases** (11):
  `register_user`, `confirm_signup`, `resend_code`, `authenticate`,
  `refresh_token`, `change_password`, `forgot_password`, `reset_password`,
  `logout`, `get_me`, `update_profile`. `logout` invokes
  `IdentityProvider.global_signout(...)` per
  [`docs/06-security-model.md` §Refresh and revocation](../../../docs/06-security-model.md#refresh-and-revocation);
  it is the only authenticated `/v1/auth/*` route besides
  `change-password`.
- **Outbound ports**: `IdentityProvider` (11 methods per
  [`docs/06-security-model.md` §Port methods](../../../docs/06-security-model.md#port-methods)),
  `UserRepository`, and `EmailSender` (used here for the synchronous
  signup-verification and password-reset transactional mails; sprint 08
  reuses the port for async notifications).
- **Two adapters per port** (the first port-swap in the codebase):
  - `IdentityProviderLocal` — JWT HS256 signed with `LOCAL_JWT_SECRET`,
    bcrypt (rounds=12) password hashes, `auth_local_users` table,
    SHA-256 code hashes, lockout after 5 attempts in 1h.
  - `IdentityProviderCognito` — `boto3.client("cognito-idp")` against the
    real User Pool, JWT RS256 validated against Cognito JWKS with a
    24-hour TTL in-memory cache and refresh-on-miss; uses
    `USER_PASSWORD_AUTH` and `REFRESH_TOKEN_AUTH` explicit flows.
  - `EmailSenderSmtp` (Mailpit at `localhost:1025`) and `EmailSenderSes`
    (SES `us-east-1` with the verified operator address as sender).
- Both adapters emit JWTs whose claim shape is **identical**: `sub`,
  `email`, `email_verified`, `custom:active_tenant`, `aud`, `iss`, `exp`,
  `iat`.

### Backend — HTTP layer

- Routers `POST /v1/auth/register`, `/confirm-signup`, `/resend-code`,
  `/login`, `/refresh`, `/password/forgot`, `/password/reset`,
  `/change-password`, `/logout`; `GET /v1/me`; `PATCH /v1/me`.
- `auth_middleware`: reads `Authorization: Bearer <jwt>`, validates per
  `APP_ENV` (`local` → HS256 with `LOCAL_JWT_SECRET`; `aws` → RS256 via
  Cognito JWKS), extracts `sub`, `email`, `custom:active_tenant`, and
  populates `CurrentUserContext`. 401 on missing/invalid JWT.
- Whitelist of unauthenticated endpoints: the seven `/v1/auth/*` routes
  above (everything except `change-password` and `logout`) plus
  `POST /v1/invitations/{token}/accept`, `/healthz`, `/readyz`,
  `/docs`, `/openapi.json`. With a JWT but **no `custom:active_tenant`**:
  `GET /v1/me`, `PATCH /v1/me`, `POST /v1/auth/logout`, `POST /v1/tenants`
  (the latter is stubbed here — sprint 03 implements the body).
- Error mapping per
  [`docs/08-api-conventions.md`](../../../docs/08-api-conventions.md):
  `AuthenticationError` → 401 (`auth.invalid_credentials` /
  `auth.token_expired`); generic responses for signup/forgot to prevent
  email enumeration.

### Backend — migration 0002

- Expand the `users` placeholder added in 0001 with:
  `external_sub TEXT UNIQUE NOT NULL`, `email CITEXT UNIQUE NOT NULL`,
  `display_name TEXT NOT NULL DEFAULT ''`, `locale TEXT NOT NULL DEFAULT
  'es-NI'`, `timezone TEXT NOT NULL DEFAULT 'America/Managua'`,
  `preferences JSONB NOT NULL DEFAULT '{}'`. The `citext` extension is
  enabled here (not in `docker/postgres-init.sql`), so the dependency is
  explicit in the migration tree.
- Create `auth_local_users` (`email CITEXT UNIQUE`,
  `password_hash TEXT`, `email_verified BOOLEAN`,
  `verification_code_hash TEXT`, `verification_code_expires_at TIMESTAMPTZ`,
  `verification_attempts INT`, `verification_attempts_reset_at TIMESTAMPTZ`,
  `attributes JSONB`) **only when `APP_ENV=local`** — the migration reads
  the env var and skips the table in AWS.
- Reversible `downgrade()` that drops `auth_local_users` (if present) and
  removes the columns added to `users`.

### Backend — outbox

- `confirm_signup` writes `identity.UserRegistered v1` to `outbox` in the
  **same transaction** that activates the user. Payload `{user_id, email,
  registered_at}`. Because `outbox.tenant_id` is `NOT NULL`, the row uses
  the **system-global tenant sentinel `00000000-0000-0000-0000-000000000000`**
  — the canonical convention for events without an active tenant. The
  outbox table itself has no RLS; the sentinel is a semantic marker only.

### Frontend — `features/auth/`

- Routes `/signup`, `/confirm`, `/login`, `/forgot-password`,
  `/reset-password`, `/me`. One Zod schema per form
  (`features/auth/schemas/`).
- **Tokens in JavaScript memory only** — not `localStorage`, not
  `sessionStorage`, not a cookie. Page reload loses the session and
  routes to `/login` (full XSS posture in
  [`docs/06-security-model.md`](../../../docs/06-security-model.md)).
- HTTP client interceptor: on a single 401, call `POST /v1/auth/refresh`
  once with the in-memory refresh token and retry the original request
  exactly once; a second failure routes to `/login`.
- `GET /v1/me` populates a `CurrentUser` store used by `/me` and (in
  sprint 03) by tenant-aware routes.

### AWS — `auth/` module enrichment

- The Cognito user-pool client gains `explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH",
  "ALLOW_REFRESH_TOKEN_AUTH"]` so the API can call `InitiateAuth` for
  password and refresh flows from Fargate without Hosted UI.
  `USER_SRP_AUTH` is deliberately excluded for the MVP — re-evaluated for
  the first productive tenant per
  [`docs/06-security-model.md` §Cognito adapter](../../../docs/06-security-model.md#cognito-adapter-identityprovidercognito).
- The same app client pins `access_token_validity = 60` minutes,
  `id_token_validity = 60` minutes, and `refresh_token_validity = 30`
  days to honour the canonical TTLs in
  [`docs/06-security-model.md` §TTLs](../../../docs/06-security-model.md#ttls)
  rather than relying on Cognito region defaults.
- New IAM policy attached to the API's Fargate task role granting
  `cognito-idp:SignUp`, `ConfirmSignUp`, `ResendConfirmationCode`,
  `InitiateAuth`, `GlobalSignOut`, `ForgotPassword`,
  `ConfirmForgotPassword`, `ChangePassword`, `AdminUpdateUserAttributes`,
  `AdminGetUser` on the user-pool ARN. Deliberately no destructive
  actions.

### AWS — new `email/` module (SES sandbox, email-only)

- One `aws_sesv2_email_identity` whose `email_identity` is `var.from_address`
  (the operator's address; defaults to the same value as `alert_email` in
  the demo env). **No domain identity, no DKIM, no SPF** — there is no
  controlled DNS zone, and the MVP accepts a permanent sandbox
  ([ADR-0020](../../../docs/adr/0020-no-custom-domain-mvp.md)).
- The operator MUST verify the address from the SES console **before the
  first signup** by clicking the AWS confirmation email; Terraform cannot
  click links, so the module never tries to mark the identity verified.
- SES stays in **permanent sandbox** (≤ 50 verified recipient addresses,
  200 mails / 24h). No exit ticket; an exit makes sense only when a custom
  domain ships post-MVP.

### AWS — `secrets/` and `envs/demo/`

- Two new SSM parameters: `/nica-erp/demo/cognito/user-pool-domain` (String,
  the literal `nica-erp.auth.us-east-1.amazoncognito.com` resolved from
  the auth module), and `/nica-erp/demo/ses/from-address` (String,
  `var.from_address`).
- `infra/terraform/envs/demo/main.tf` composes the new `email/` module and
  passes `from_address` through to `secrets/`.

### Bootstrap wiring

- `bootstrap/container.py` gains `build_identity_provider()` and
  `build_email_sender()` factories. Both branch on
  `settings.app_env`: `local` returns `IdentityProviderLocal` /
  `EmailSenderSmtp`; `aws` returns `IdentityProviderCognito(client=boto3.client("cognito-idp"),
  user_pool_id=..., client_id=...)` / `EmailSenderSes(client=boto3.client("ses"),
  from_address=...)`. `APP_ENV` is required (no default) — a misconfigured
  prod container with an empty `APP_ENV` MUST fail to start.
- `bootstrap/api.py` mounts the auth router and installs the auth
  middleware **after** CORS, so 401s carry CORS headers in dev.

### `domain-purity` import-linter contract

- Extended to cover `contexts.identity.domain`: it MAY NOT import
  `sqlalchemy`, `fastapi`, `boto3`, any `shared_kernel.adapters` module,
  any `contexts.identity.{application,adapters}`, or any other
  `contexts.<x>` package.

## Capabilities

### New Capabilities

- `identity-domain` — `User` aggregate, `Email` and `Password` value
  objects, `UserRegistered` and `PasswordReset` domain events.
- `identity-application` — the 10 inbound use cases, the `IdentityProvider`
  / `UserRepository` / `EmailSender` outbound ports, and the
  `UserRegistered` outbox emission rule (system-global tenant sentinel).
- `identity-http` — `/v1/auth/*` and `/v1/me` routers, the JWT
  authentication middleware, the unauthenticated allowlist, and the
  authenticated-without-tenant allowlist.
- `identity-provider-local` — `IdentityProviderLocal`, the
  `auth_local_users` table, HS256 JWT signing, bcrypt hashing, SHA-256
  code hashes, and the lockout policy.
- `identity-provider-cognito` — `IdentityProviderCognito`, the
  `USER_PASSWORD_AUTH` flow, the JWKS cache with 24h TTL and
  stale-on-error fallback, and the boto3 client wiring.
- `email-sender` — the `EmailSender` port, the SMTP adapter for Mailpit,
  and the SESv2 adapter pinned to a single verified sender. (Sprint 08
  reuses the port for async notifications.)
- `aws-email` — the Terraform `email/` module with the SES email
  identity, the permanent-sandbox posture, and the operator verification
  ritual.

### Modified Capabilities

- `database-schema-bootstrap` — adds migration 0002 with the `users`
  column expansion, the `citext` extension, and the `APP_ENV`-gated
  `auth_local_users` table.
- `api-bootstrap` — mounts the identity HTTP router, installs the auth
  middleware, and adds the `build_identity_provider()` /
  `build_email_sender()` factories that branch on `settings.app_env`.
- `frontend-shell` — adds the `features/auth/` slice, the in-memory
  token store, and the single-retry 401 interceptor.
- `aws-auth` — adds the `explicit_auth_flows` allow-list on the SPA app
  client and the IAM policy attached to the API task role for the
  cognito-idp action set.
- `aws-secrets` — adds the `user-pool-domain` and `ses/from-address`
  SSM parameters.
- `aws-compute` — extends the API ECS task definition's `secrets[]`
  array with `SES_FROM_ADDRESS` and grants the task role
  `ssm:GetParameters` on the new parameter ARN.
- `aws-demo-environment` — composes the new `email/` module and wires
  the SES sender address through to `secrets/`.

## Impact

- **Affected code**: new `apps/api/src/contexts/identity/` package; new
  `apps/api/alembic/versions/0002_identity.py`; modifications to
  `apps/api/src/bootstrap/api.py`, `bootstrap/container.py`,
  `bootstrap/settings.py` (add `local_jwt_secret`, `cognito_*`,
  `ses_from_address`, `app_env` required); new
  `infra/terraform/modules/email/`; modifications to
  `infra/terraform/modules/{auth,secrets}/` and
  `infra/terraform/envs/demo/main.tf`; new `apps/web/src/features/auth/`
  and `apps/web/src/routes/{signup,confirm,login,forgot-password,reset-password,me}.tsx`.
- **Affected APIs**: introduces seven public auth endpoints
  (`/v1/auth/*`) and three authenticated endpoints
  (`GET /v1/me`, `PATCH /v1/me`, plus the `POST /v1/tenants` stub),
  matching the catalogue in
  [`docs/08-api-conventions.md`](../../../docs/08-api-conventions.md).
- **Dependencies**: adds `pyjwt[crypto]` (or `python-jose[cryptography]`)
  for JWT signing/verification, `bcrypt` for hashing, `aiosmtplib` for
  Mailpit, and uses the existing `boto3` from sprint 01 for both
  `cognito-idp` and `sesv2`. Frontend uses Zod (already present per
  [ADR-0009](../../../docs/adr/0009-frontend-stack.md)).
- **Systems**: locally requires the existing Mailpit container from
  sprint 00 (no compose change) and the `LOCAL_JWT_SECRET` env var in
  `.env.local`. In AWS requires that an operator click the SES email
  verification link **before** the first signup; without that, Cognito's
  outbound mail bounces. SES stays in permanent sandbox.
- **Out of scope** (intentionally): RBAC and the permission catalogue
  ([ADR-0022](../../../docs/adr/0022-rbac-model.md), sprint 03); tenant
  creation, `tenant_members`, and Postgres RLS (sprint 03); the welcome
  email worker and async notification path (sprint 08, which consumes
  the `UserRegistered` event from the outbox); the invitation creation
  endpoint (sprint 03 — sprint 02 only whitelists the accept route);
  refresh-token rotation (`ENABLE_TOKEN_REVOCATION`) and the BFF +
  HttpOnly cookie hardening (post-MVP per
  [`docs/18-roadmap.md`](../../../docs/18-roadmap.md)); SES exit from
  sandbox (only meaningful with a custom domain — post-MVP).

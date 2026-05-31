# Sprint 02 — `identity` context + local IdP + Cognito adapter + deploy

**Goal.** Signup, verification, login and `/me` working locally (`IdentityProviderLocal`) and on AWS (`IdentityProviderCognito` against the real User Pool). First DDD vertical slice + first port swap under rolling deploys. Cognito user pool domain with default prefix `nica-erp.auth.us-east-1.amazoncognito.com` (no Hosted UI; `USER_PASSWORD_AUTH` flow from the API); SES in **permanent sandbox with email-only verification** (no domain identity, no DKIM/SPF, [ADR-0020](../adr/0020-no-custom-domain-mvp.md)).

---

## Dependencies

- **Previous sprints**: [00](00-walking-skeleton.md) (`UnitOfWork`, `OutboxWriter`, `users` placeholder table); [01](01-aws-wiring-rolling-deploys.md) (Cognito User Pool Lite with `custom:active_tenant` declared empty).
- **Ports introduced**: `IdentityProvider` (local + Cognito), `EmailSender` (Mailpit local + SES sandbox for signup). Productive use of `EmailSender` for transactional notifications in [sprint 08](08-notifications-ses.md); contract + both adapters ship here.

---

## `identity/` context

Canonical layout (see README §Shared patterns). Specific modules:

- `domain/model/`: `user.py` (AggregateRoot), `email.py` (VO with validation), `password.py` (VO with policy: 12+ chars, uppercase, lowercase, digit, symbol), `events.py` (`UserRegistered`, `PasswordReset`).
- `application/ports/inbound/`: `register_user`, `confirm_signup`, `resend_code`, `authenticate`, `refresh_token`, `change_password`, `forgot_password`, `reset_password`, `logout`, `get_me`, `update_profile`. `logout` invokes `IdentityProvider.global_signout(...)` per [`../06-security-model.md` §Refresh and revocation](../06-security-model.md#refresh-and-revocation).
- `application/ports/outbound/`: `identity_provider.py` (Protocol — full definition in [`../06-security-model.md`](../06-security-model.md)), `user_repository.py`.
- `adapters/inbound/http/`: routers `/v1/auth/*` and `/v1/me`.
- `adapters/outbound/identity_provider/local.py` + `persistence/sqlalchemy/user_repository.py`.

---

## `IdentityProviderLocal` adapter

- Table `auth_local_users` (migration 0002, only if `APP_ENV=local`).
- JWT HS256 with `LOCAL_JWT_SECRET`.
- Claims shape **identical to Cognito**: `sub`, `email`, `email_verified`, `custom:active_tenant`, `aud`, `iss`, `exp`, `iat`.
- Verification / reset via SMTP to Mailpit (`localhost:1025`).
- bcrypt for hashing.

---

## `users` table (migration 0002)

```sql
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE users (
  id              UUID PRIMARY KEY,
  external_sub    TEXT UNIQUE NOT NULL,   -- JWT `sub`: Cognito in prod, local IdP in dev
  email           CITEXT UNIQUE NOT NULL,
  display_name    TEXT NOT NULL DEFAULT '',
  locale          TEXT NOT NULL DEFAULT 'es-NI',
  timezone        TEXT NOT NULL DEFAULT 'America/Managua',
  preferences     JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`CREATE EXTENSION` is run from Alembic (not `docker/postgres-init.sql`) so the dependency is explicit in the version tree.

---

## `UserRegistered` to outbox

`ConfirmSignup` writes `identity.UserRegistered v1` to `outbox` in the same transaction that activates the user. [Sprint 08](08-notifications-ses.md) consumes it for the welcome email.

Payload: `{user_id, email, registered_at}`. Since `tenant_id` (NOT NULL) is required, we use the **system global tenant `'00000000-0000-0000-0000-000000000000'`**, reserved for events without an active tenant (signup, password reset). Canonical convention for every MVP event without a tenant; the publisher Lambda routes them as globals in EventBridge. The `outbox` table has no RLS, so the sentinel serves only as a semantic marker — not for isolation.

**Boundary with `notifications` (sprint 08)**: this sprint sends *synchronous* emails from the use case (`EmailSender` direct) only for signup-verification and password-reset because the flow requires an immediate response to the user. Sprint 08 adds *asynchronous* sends from `notifications_worker` consuming the outbox (welcome, invoice issued, low stock, member invited). The `password_reset.html` template stays in sprint 08 as a reference for `IdentityProviderLocal`; in prod Cognito generates its own.

---

## Auth middleware

`auth_middleware.py`:

1. Reads `Authorization: Bearer <jwt>`.
2. Validates JWT per `APP_ENV`: `local` HS256 with `LOCAL_JWT_SECRET`; `aws` RS256 with Cognito JWKS (cache TTL 24h with refresh-on-miss; see [`../06-security-model.md` §Cognito adapter](../06-security-model.md#cognito-adapter-identityprovidercognito)).
3. Extracts `sub`, `email`, `custom:active_tenant`; populates `CurrentUserContext`.
4. 401 if no JWT or invalid.

Whitelist without mandatory JWT: `POST /v1/auth/register`, `/v1/auth/confirm-signup`, `/v1/auth/resend-code`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/password/forgot`, `/v1/auth/password/reset`; `POST /v1/invitations/{token}/accept`; `/healthz`, `/readyz`, `/docs`, `/openapi.json`. With JWT but no `custom:active_tenant`: `GET /v1/me`, `POST /v1/auth/logout`, `POST /v1/tenants` (first tenant). `POST /v1/auth/change-password` and `POST /v1/auth/logout` are authenticated; logout calls `GlobalSignOut` server-side to invalidate refresh tokens. Canonical source: [`../06-security-model.md`](../06-security-model.md) and [`../08-api-conventions.md` §identity](../08-api-conventions.md#identity).

---

## Endpoints

See [`../08-api-conventions.md` #identity](../08-api-conventions.md#identity).

## Frontend

Routes `/signup`, `/confirm`, `/login`, `/forgot-password`, `/reset-password`, `/me`. **Access and refresh tokens in JS process memory** (not `localStorage`/`sessionStorage` due to XSS) — the session is lost on reload and re-authenticates. 401 interceptor invokes `POST /v1/auth/refresh` once. `HttpOnly` cookie with BFF is out of MVP scope. Full policy in [`../09-frontend.md` §Authentication](../09-frontend.md#authentication) and [`../06-security-model.md` §Refresh and revocation](../06-security-model.md#refresh-and-revocation). Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: `Email.parse()`, `Password.validate_policy()`, use cases with mocks.
- Integration: `IdentityProviderLocal` against Postgres (register → confirm → login → refresh → forgot → reset).
- E2E: `POST /v1/auth/register` → code in Mailpit → confirm → login → `GET /v1/me`.
- Contract test `IdentityProvider` parametrized over Local and Cognito (consolidated suite in [sprint 09](09-mvp-validation.md); here it already exists and runs when AWS credentials are available).

---

## Verifiable outcome (local)

```bash
curl -X POST localhost:8000/v1/auth/register -H 'content-type: application/json' \
  -d '{"email":"yo@test.dev","password":"Demo1234!@"}'                  # → 201
# Open http://localhost:8025 (Mailpit), copy code
curl -X POST localhost:8000/v1/auth/confirm-signup ... -d '{"email":"yo@test.dev","code":"123456"}'
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/login ... -d '...' | jq -r .access_token)
curl localhost:8000/v1/me -H "Authorization: Bearer $TOKEN"             # → profile
```

---

## Deploy

### Terraform additions

- **`auth/` enriched**: App Client without secret, flow `USER_PASSWORD_AUTH` (MVP by simplicity for a SPA without client secret; evaluate `USER_SRP_AUTH` for production — [`../06-security-model.md` §Cognito adapter](../06-security-model.md#cognito-adapter-identityprovidercognito)); IAM for `cognito-idp:AdminGetUser/AdminUpdateUserAttributes/AdminInitiateAuth`. Callback/logout URLs declared as `"https://${aws_cloudfront_distribution.main.domain_name}/auth/callback"` directly in HCL (no prior apply required). MVP does not consume these callbacks because it does not use Hosted UI; they remain pre-wired for future OAuth flows.
- **`email/` new**: SES **email identity** verified by email of the sender address (`alert_email` or operator). No domain identity, no DKIM/SPF — no controlled DNS zone. The operator verifies their address from the SES console (`us-east-1`) **before** the first signup. SES stays in **permanent sandbox** (≤50 verified recipients, no exit ticket).
- **SSM** ([ADR-0021](../adr/0021-ssm-parameter-store.md)): `/nica-erp/demo/cognito/{user_pool_id,app_client_id,user_pool_domain}`, `/nica-erp/demo/ses/from_address`.

### Wiring

Follows README §Shared patterns. `build_identity_provider()` branches `IdentityProviderLocal` ↔ `IdentityProviderCognito(client=boto3.client("cognito-idp"), user_pool_id=..., client_id=...)`. `build_email_sender()` branches `EmailSenderSmtp` ↔ `EmailSenderSes(client=boto3.client("ses"), from_address=...)`.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus:
- Pre: signup address verified in SES sandbox.
- At `URL/`: `/signup` with verified email → Cognito code via SES → `/confirm` → `/login` (JWT RS256 with empty `custom:active_tenant`) → `/me` shows profile.

Cost: ~3-5 USD.

---

## Post-sprint extensions

The `confirm-signup` request body is extended (additively) by
sprint 3.15 in [`docs/sprints/03-tenants-and-rls.md` §Sprint follow-up — Invited-user onboarding lands session-ready](03-tenants-and-rls.md#sprint-follow-up--invited-user-onboarding-lands-session-ready-sprint-315-2026-05-31)
to accept an optional `password` and return tokens when present,
removing the forced re-login round trip after email
confirmation. The base `204` shape documented above is
preserved when the body omits `password`. Decision recorded in
[ADR-0035](../adr/0035-onboarding-endpoints-return-session.md).

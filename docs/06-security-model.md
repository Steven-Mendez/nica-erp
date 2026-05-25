# 06 — Security Model

Single source of truth for **authentication**, **authorization**, **token handling**, **secrets**, and the **threat surface**. Other docs cross-reference here.

---

## Authentication

The `identity` context defines the `IdentityProvider` port with two interchangeable adapters — Cognito User Pool tier Lite (prod) and `IdentityProviderLocal` (dev). [ADR-0005](adr/0005-cognito-with-local-idp.md).

### Port methods
`register`, `authenticate`, `verify_token`, `refresh`, `confirm_signup`, `resend_confirmation`, `forgot_password`, `confirm_forgot_password`, `change_password`, `global_signout`, `update_active_tenant`.

`Identity` (value object): `sub`, `email`, `access_token`, `refresh_token`, `id_token`, `claims`.

### Cognito adapter (`IdentityProviderCognito`)
- `boto3-cognito-idp`. Flows: `USER_PASSWORD_AUTH` (MVP, no client secret), `REFRESH_TOKEN_AUTH`, `ForgotPassword`/`ConfirmForgotPassword`, `ChangePassword`, `GlobalSignOut`, `AdminUpdateUserAttributes`.
- **JWKS cache**: in-memory in the Fargate task; TTL 24h; refresh-on-miss with a lock against thundering herd; stale cache used if JWKS responds with an error (preferable to rejecting traffic).
- **User Pool**:
  - Tier Lite.
  - App Client without client secret.
  - Custom attribute `custom:active_tenant` (mutable string, empty until first tenant).
  - Email = username; verification required; password 12+ chars with mixed case, digit, symbol.
  - Optional per-user MFA.
  - No Hosted UI; uses the default domain prefix `pyme-erp.auth.us-east-1.amazoncognito.com` ([ADR-0020](adr/0020-no-custom-domain-mvp.md)).
- **IAM (Fargate task role)**: `SignUp`, `ConfirmSignUp`, `ResendConfirmationCode`, `InitiateAuth`, `GlobalSignOut`, `ForgotPassword`, `ConfirmForgotPassword`, `ChangePassword`, `AdminUpdateUserAttributes`, `AdminGetUser`. No destructive permissions.

### Local adapter (`IdentityProviderLocal`)
- Table `auth_local_users` (present only when `APP_ENV=local`): `email` (`CITEXT UNIQUE`), `password_hash` (bcrypt rounds=12), `email_verified`, `verification_code_hash` (SHA-256), `verification_code_expires_at` (15 min for signup / 10 min for reset), `verification_attempts` (lock after 5 in 1h), `attributes` (jsonb; `custom:active_tenant`).
- JWT HS256 with key in `.env.local`. **Same claim shape as Cognito** — middleware validates HS256 in dev, RS256 via Cognito JWKS in prod. Selected in `bootstrap/container.py` based on `APP_ENV`.
- `APP_ENV` is required (no default). `bootstrap/settings.py` fails to start if empty. Prevents a misconfigured container in prod from falling back to local auth.

### `users` table (always present)
Extended profile outside the IdP. Columns: `id` (UUIDv7), `external_sub` (FK-shape to JWT `sub`: Cognito in prod, local IdP in dev), `email`, `display_name`, `locale` (`es-NI`), `timezone` (`America/Managua`), `preferences` (jsonb), timestamps.

Password hash lives in the IdP — Cognito in prod, `auth_local_users` in dev — never in `users`.

---

## JWTs and active tenant

`custom:active_tenant` travels in every JWT. Middleware:

1. Validates signature (Cognito JWKS or HS256).
2. Extracts `sub` and `custom:active_tenant`.
3. Validates membership against `tenant_members` (global table without RLS) **before** `SET LOCAL app.tenant_id`.
4. Sets `current_tenant.set(...)` (`ContextVar`) and the GUCs in the transaction.

If the JWT carries no tenant, only these endpoints are allowed: `POST /v1/tenants`, `POST /v1/invitations/{token}/accept`, `GET /v1/me`.

### TTLs

| Token | TTL |
|---|---|
| Access | 1 hour |
| ID | 1 hour |
| Refresh | 30 days |

| Code | TTL | Retries | Lockout |
|---|---|---|---|
| Signup | 15 min | 5 | 1 hour; resend via `POST /v1/auth/resend-code`, max 1 per 60s per email |
| Password reset | 10 min | 5 | 1 hour; via `POST /v1/auth/password/forgot` |

Configurable via SSM in prod; defaults in `bootstrap/settings.py`.

### Refresh and revocation
- **Refresh token rotation** is **not** active in MVP (Cognito does not rotate by default). Activating with `ENABLE_TOKEN_REVOCATION` + client-side rotation logic is post-MVP work — see [18 — Roadmap](18-roadmap.md).
- `POST /v1/auth/logout` invokes `GlobalSignOut` (invalidates refresh tokens; local deletes `auth_local_refresh_tokens`). Access tokens remain valid until `exp` (≤ 1 hour).
- **Tenant status check** on every authenticated request — the same dependency that loads the tenant context rejects `suspended` or `purged` tenants ([ADR-0026](adr/0026-tenant-lifecycle.md)). Best-effort session revocation.

### Frontend tokens
- **In memory only.** Access AND refresh tokens live in JavaScript memory, not `localStorage`, `sessionStorage`, or any cookie. Lost on reload — the SPA redirects to login. (HttpOnly cookie + BFF is the post-MVP hardening; see the XSS posture below.)
- **One retry on 401 within the same session.** While the SPA is loaded, the HTTP client interceptor catches a single 401, calls `POST /v1/auth/refresh` with the in-memory refresh token, retries the original request once, and gives up on a second failure (no infinite loops). After a reload the refresh token is gone — the interceptor cannot recover and routes to `/login`.
- **XSS posture**: with tokens in memory, an XSS would have to extract them at the moment they're held in JS. A BFF (Backend-for-Frontend) holding tokens server-side via HttpOnly cookies is the post-MVP hardening; out of scope for MVP. See [09 — Frontend](09-frontend.md) for the SPA-side implementation.

---

## Authorization (RBAC)

[ADR-0022](adr/0022-rbac-model.md): RBAC with granular permissions + ownership hybrid. Five fixed roles in MVP; each maps to a set of `<resource>:<action>` permissions. Resources with a natural owner expose `*:read` (own) and `*:read-all` (bypass) — the filter is applied in the query layer.

### Tables (global catalog, no RLS)
- `permissions(code PK, resource, action, scope, description)` — catalog of `<resource>:<action>` strings.
- `role_permissions(role, permission)` (composite PK) — mapping seeded in migration per sprint.

Source of truth: `shared_kernel/permissions/catalog.py` (Python constants). The migration reflects the catalog; a test verifies the two agree. Custom roles per tenant are out of MVP scope.

### Roles
| Role | Focus |
|---|---|
| `viewer` | Read-only on own resources + operational reports (no fiscal) |
| `salesperson` | viewer + create drafts + issue invoice + receive payments. Sees only own documents |
| `accountant` | salesperson + `*:read-all` + credit/debit notes + VAT book + withholdings + IMI + apply/reverse payments |
| `admin` | accountant + catalog, inventory, tax config, number sequences, members, audit log |
| `owner` | admin + ownership transfer. Unique per tenant (`UNIQUE (tenant_id) WHERE role='owner'`) |

### Ownership hybrid

Resources with a natural owner:

| Resource | Ownership column | Permissions | Who bypasses |
|---|---|---|---|
| `Invoice` | `created_by_user_id` | `invoice:read`, `invoice:read-all` | accountant+ |
| `Quotation` | `created_by_user_id` | `quotation:read`, `quotation:read-all` | accountant+ |
| `CustomerPayment` | `recorded_by_user_id` | `customer-payment:read`, `customer-payment:read-all` | accountant+ |
| `Notification` | `user_id` | `notification:read` (no `-all`; everyone gets their own alerts) | admin for resend |

Resources without a natural owner (tenant catalog): `Product`, `Category`, `Warehouse`, `Customer`, `Supplier`, `TaxConfig`, `NumberSequence`, `AuditLogEntry`, `StockMovement`. Only `*:read` with `scope='na'`.

### Enforcement (FastAPI dependency)

```python
# bootstrap/dependencies.py
def require(*codes: str) -> Callable[..., Awaitable[Actor]]:
    async def _check(actor: Actor = Depends(current_actor)) -> Actor:
        missing = [c for c in codes if c not in actor.permissions]
        if missing:
            raise ForbiddenError(missing=missing)
        return actor
    return _check

# router
@router.post("/v1/invoices/{id}/issue")
async def issue(id: UUID, _: Actor = Depends(require("invoice:issue"))) -> InvoiceOut:
    ...
```

`current_actor` resolves `Actor(user_id, tenant_id, role, permissions: frozenset[str])` per request. The set materializes once per request from a 60-second process-local cache over `(role → frozenset)`. Changes to `role_permissions` propagate within ≤ 60s.

### Ownership filter in the query layer

Repositories of owned resources inherit from `OwnedAggregateRepository`:

```python
class InvoiceRepository(OwnedAggregateRepository[Invoice]):
    owner_column = "created_by_user_id"
    bypass_permission = "invoice:read-all"

    async def list(self, actor: Actor, filters: InvoiceFilters) -> list[Invoice]:
        q = select(InvoiceRow).where(InvoiceRow.tenant_id == actor.tenant_id)
        if self.bypass_permission not in actor.permissions:
            q = q.where(InvoiceRow.created_by_user_id == actor.user_id)
        return [r.to_aggregate() for r in await self._session.scalars(q)]
```

Use cases don't know about the filter — ownership logic lives in the repo.

### Permission catalog by context

| Context | Permissions | Sprint |
|---|---|---|
| `tenants` | `tenant:read`, `tenant:write`, `members:read`, `members:invite`, `members:update-role`, `members:remove` | [03](sprints/03-tenants-and-rls.md) |
| `catalog` | `product:read`, `product:write`, `product:delete`, `category:read`, `category:write` | [04](sprints/04-catalog-and-inventory.md) |
| `inventory` | `inventory:read`, `inventory:adjust`, `inventory:transfer`, `inventory:set-threshold` | [04](sprints/04-catalog-and-inventory.md) |
| `parties` | `customer:read`, `customer:write`, `customer:delete`, `supplier:read`, `supplier:write`, `supplier:delete` | [05](sprints/05-parties-and-sales.md) |
| `sales` | `number-sequence:read`, `number-sequence:write`, `quotation:*`, `invoice:*`, `credit-note:*`, `debit-note:*` | [05](sprints/05-parties-and-sales.md) |
| `taxes` | `tax-config:read`, `tax-config:write`, `tax-quote:run` | [06](sprints/06-taxes-payments-reports.md) |
| `payments` | `customer-payment:*`, `accounts-receivable:read` | [06](sprints/06-taxes-payments-reports.md) |
| `reports` | `report:sales`, `report:inventory`, `report:vat-book`, `report:retentions`, `report:imi` | [06](sprints/06-taxes-payments-reports.md) |
| `audit` | `audit-log:read` | [07](sprints/07-outbox-eventbridge-audit.md) |
| `notifications` | `notification:read`, `notification-preference:write`, `notification:resend` | [08](sprints/08-notifications-ses.md) |

### Role-to-permission default matrix

| Permission | viewer | salesperson | accountant | admin | owner |
|---|:-:|:-:|:-:|:-:|:-:|
| `tenant:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tenant:write` |  |  |  | ✓ | ✓ |
| `members:read` |  |  | ✓ | ✓ | ✓ |
| `members:invite`, `members:update-role`, `members:remove` |  |  |  | ✓ | ✓ |
| `product:read`, `category:read`, `inventory:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `product:write`, `category:write`, `inventory:adjust`, `inventory:transfer`, `inventory:set-threshold`, `product:delete` |  |  |  | ✓ | ✓ |
| `customer:read`, `supplier:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `customer:write`, `supplier:write` |  | ✓ | ✓ | ✓ | ✓ |
| `customer:delete`, `supplier:delete` |  |  |  | ✓ | ✓ |
| `number-sequence:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `number-sequence:write` |  |  |  | ✓ | ✓ |
| `quotation:read`, `invoice:read`, `customer-payment:read` (own) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `quotation:read-all`, `invoice:read-all`, `customer-payment:read-all` |  |  | ✓ | ✓ | ✓ |
| `quotation:write`, `quotation:convert`, `invoice:write`, `invoice:issue`, `invoice:send`, `customer-payment:write` |  | ✓ | ✓ | ✓ | ✓ |
| `invoice:cancel`, `customer-payment:apply`, `customer-payment:reverse` |  |  | ✓ | ✓ | ✓ |
| `credit-note:write`, `credit-note:issue`, `debit-note:write`, `debit-note:issue` |  |  | ✓ | ✓ | ✓ |
| `tax-config:read`, `tax-quote:run` |  | ✓ | ✓ | ✓ | ✓ |
| `tax-config:write` |  |  |  | ✓ | ✓ |
| `accounts-receivable:read` |  | ✓ | ✓ | ✓ | ✓ |
| `report:sales`, `report:inventory` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `report:vat-book`, `report:retentions`, `report:imi` |  |  | ✓ | ✓ | ✓ |
| `audit-log:read` |  |  |  | ✓ | ✓ |
| `notification:read`, `notification-preference:write` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `notification:resend` |  |  |  | ✓ | ✓ |

Sprint 03's test enumerates this matrix and fails if a cell diverges from the seed.

### Frontend exposure

`GET /v1/me` returns `permissions: string[]` with the actor's materialized set for the active tenant. The SPA uses this list to show/hide actions (the "Issue" button is hidden if `invoice:issue` is missing). **The backend remains the source of truth** — the endpoint's `require(...)` is the final defense.

### Errors

- `ForbiddenError` → HTTP 403 with RFC 7807 problem details ([ADR-0015](adr/0015-rfc7807-errors.md)), `type=missing-permission`, extension `missing: ["invoice:issue"]`.
- HTTP 404 reserved for "does not exist in this tenant" — including tenant resources the actor can't see by ownership. We prefer 404 over 403 there to avoid leaking existence between users in the same tenant. Reconsider post-MVP if it causes confusion.

---

## Secrets

[ADR-0021](adr/0021-ssm-parameter-store.md): all persistent secrets in **SSM Parameter Store SecureString**. `.env.local` (gitignored) in dev.

| Secret | Location |
|---|---|
| RDS master credentials | `/pyme-erp/db/master` (SecureString) |
| JWT signing key (local IdP only) | `/pyme-erp/jwt/signing-key` (SecureString) |
| Integration credentials (BCN, gateways) | `/pyme-erp/integrations/*` (SecureString) |
| Non-sensitive config (URLs, flags) | `/pyme-erp/config/*` (String) |

ECS task definition references SSM ARNs in `secrets[]`. Lambdas read via `boto3.client("ssm").get_parameter(WithDecryption=True)` at cold start and cache. The `SecretsProvider` port isolates dev (`.env.local`) ↔ prod (SSM).

### Rotation
- **RDS** — manual; reconsidered at first productive tenant.
- **JWT** — manual, only after suspected leak (rotation invalidates all sessions). Runbook in [13 — Operations](13-operations.md).
- **Integrations** — case by case.

---

## Threat surface and mitigations

| Threat | Mitigation |
|---|---|
| **Cross-tenant data leak** | RLS at the DB layer ([ADR-0002](adr/0002-postgres-rls.md)) + tenant_id assertion in application + isolation test per tenant-scoped table ([14 — Testing](14-testing.md)) |
| **Privilege escalation in the same tenant** | Ownership filter in query layer + `require(...)` on every mutating endpoint + matrix test in sprint 03 |
| **JWT replay after logout** | Best-effort: `GlobalSignOut` revokes refresh; access tokens expire ≤ 1h; tenant status check on every request |
| **JWT leak via XSS** | Tokens in memory only, not `localStorage`. BFF + HttpOnly cookies is the post-MVP hardening |
| **JWT leak via leaked signing key** | Manual rotation runbook; key in SSM SecureString; `.env.local` gitignored + pre-commit reject |
| **Brute force on local IdP** | 5 attempts in 1h → 1h lockout; rate-limit on `/v1/auth/login` (CloudFront + ALB level) |
| **Email enumeration** | Signup/forgot return generic responses regardless of email existence |
| **CSRF** | No auth cookies (tokens live in JS memory); all state-changing endpoints require the `Authorization: Bearer` header, which a cross-origin page cannot forge |
| **SQL injection** | Parametrized queries everywhere (SQLAlchemy); raw SQL only in migrations |
| **Privilege escalation via direct DB grant** | API user has no `DELETE` on fiscal tables (deferred until first productive tenant, per [ADR-0029](adr/0029-disaster-recovery-posture.md)) |
| **Secret leak via env var visibility** | Secrets via `secrets[]` SSM refs in task definition, never plain env vars; CloudTrail logs `ssm:GetParameter` calls |
| **Suspended-tenant abuse** | `tenants.status` checked on every authenticated request; suspended tenants get read-only access |
| **PII in logs** | Canonical no-PII rule ([ADR-0024](adr/0024-observability-baseline.md)); structlog processor strips known PII fields |

---

## IdP migration

Future migration to Keycloak self-hosted, Okta, Auth0, or Azure AD:

1. Implement `IdentityProviderXxx` with the same port.
2. Change the wiring in `bootstrap/container.py`.
3. Migrate users: export from Cognito, import mapping `sub` → `external_sub`.
4. Force password reset on first login (Cognito does **not** export hashes).
5. Switch the JWT validator middleware to the new IdP's JWKS.

**Zero changes** in `domain/`, `application/use_cases/`, or any other context. This is what the port abstraction pays for.

---

## Contributor security checklist

When writing code, do not:

| Never                                                          | Do instead                                                                   |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Commit `.env`, AWS keys, JWTs, signing keys, RDS passwords     | Use `.env.local.example` as the template; secrets via SSM ([ADR-0021](adr/0021-ssm-parameter-store.md)) |
| Log PII (names, emails, RUCs, phones, addresses)               | Log IDs only; `structlog` strips known PII as a safety net ([12 — Observability](12-observability.md)) |
| Log JWTs, refresh tokens, passwords                            | Trace via `correlation_id`                                                   |
| Bypass RLS in queries (`SET ROLE`, `SECURITY DEFINER` views)   | Always go through the tenant-scoped repository ([05 — Multi-tenancy](05-multi-tenancy.md)) |
| Build SQL strings via f-string interpolation                   | Use SQLAlchemy expressions; let the driver bind parameters                   |
| Use `eval`, `exec`, `pickle` on untrusted input                | Use Pydantic for validation, `json` for serialization                        |

If you spot a security issue, open a **private** GitHub Security Advisory rather than a public issue.

## References
- [ADR-0005](adr/0005-cognito-with-local-idp.md) — Cognito + local IdP
- [ADR-0021](adr/0021-ssm-parameter-store.md) — SSM secrets
- [ADR-0022](adr/0022-rbac-model.md) — RBAC + ownership hybrid
- [ADR-0026](adr/0026-tenant-lifecycle.md) — Tenant lifecycle
- [ADR-0015](adr/0015-rfc7807-errors.md) — Error response shape
- [05 — Multi-tenancy](05-multi-tenancy.md) — RLS detail
- [09 — Frontend](09-frontend.md) — SPA-side token handling
- [13 — Operations](13-operations.md) — Runbooks (JWT rotation, suspend/reactivate)

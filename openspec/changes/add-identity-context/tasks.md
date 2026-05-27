## 1. Dependencies and settings

- [x] 1.1 Add runtime deps to `apps/api/pyproject.toml`: `pyjwt[crypto]`,
      `bcrypt`, `aiosmtplib`. `boto3` already present.
- [x] 1.2 Extend `bootstrap/settings.py` with `app_env` (required — no
      default, raise on empty), `local_jwt_secret`, `cognito_user_pool_id`,
      `cognito_app_client_id`, `cognito_user_pool_domain`,
      `cognito_region`, `ses_from_address`, `smtp_host`, `smtp_port`,
      `jwt_access_ttl_seconds=3600`, `jwt_refresh_ttl_seconds=2592000`,
      `signup_code_ttl_seconds=900`, `password_reset_code_ttl_seconds=600`,
      `verification_attempts_max=5`,
      `verification_attempts_window_seconds=3600`.
- [x] 1.3 Update `.env.local.example` with `APP_ENV=local`,
      `LOCAL_JWT_SECRET=<placeholder>`, `SES_FROM_ADDRESS=`,
      `SMTP_HOST=localhost`, `SMTP_PORT=1025`.

## 2. Domain (`contexts/identity/domain/`)

- [x] 2.1 Implement `Email` value object: dataclass `frozen=True`,
      `__post_init__` validates with a conservative regex and lowercases
      the local-part comparison; raises `ValueError` on invalid input.
- [x] 2.2 Implement `Password` value object: holds the raw value;
      `validate_policy()` enforces ≥12 chars, ≥1 uppercase, ≥1 lowercase,
      ≥1 digit, ≥1 symbol; raises `PasswordPolicyError` (subclass of
      `ValueError`).
- [x] 2.3 Implement `User` aggregate (`AggregateRoot[UUID]`) with fields
      `external_sub`, `email`, `display_name`, `locale`, `timezone`,
      `preferences`, `created_at`, `updated_at`; class methods
      `register(...)` and `update_profile(...)` recording the relevant
      events.
- [x] 2.4 Define events `UserRegistered v1` (`user_id`, `email`,
      `registered_at`) and `PasswordReset v1` (`user_id`, `reset_at`) as
      frozen `DomainEvent` subclasses.
- [x] 2.5 Unit tests for `Email` (valid/invalid shapes, equality),
      `Password.validate_policy` (each rule independently), and
      `User.register` records `UserRegistered`.

## 3. Application (`contexts/identity/application/`)

- [x] 3.1 Define outbound port `IdentityProvider` (Protocol) with all 11
      methods from
      [`docs/06-security-model.md` §Port methods](../../../docs/06-security-model.md#port-methods).
- [x] 3.2 Define outbound port `UserRepository` (Protocol): `get_by_id`,
      `get_by_external_sub`, `add`, `update`.
- [x] 3.3 Define outbound port `EmailSender` (Protocol): single
      `async send(to: str, subject: str, html: str, text: str) -> None`.
- [x] 3.4 Implement the 11 use cases as keyword-only dataclasses with
      `execute()` methods: `register_user`, `confirm_signup`, `resend_code`,
      `authenticate`, `refresh_token`, `change_password`, `forgot_password`,
      `reset_password`, `logout`, `get_me`, `update_profile`. `logout`
      pulls `external_sub` from `CurrentUserContext` and calls
      `IdentityProvider.global_signout(...)` exactly once; the call is
      idempotent (a second invocation MUST also return `None`).
- [x] 3.5 `confirm_signup.execute()` writes
      `identity.UserRegistered v1` to the outbox via `OutboxWriter`,
      using the system-global tenant sentinel `'00000000-0000-0000-0000-000000000000'`,
      inside the same `UnitOfWork` that activates the user.
- [x] 3.6 `register_user` and `forgot_password` SHALL return the **same
      response shape** regardless of whether the email already exists,
      to prevent email enumeration ([`docs/06-security-model.md`](../../../docs/06-security-model.md)
      §Threat surface).
- [x] 3.7 Unit tests for each use case with mocks (`IdentityProvider`,
      `UserRepository`, `EmailSender`, `UnitOfWork`).

## 4. `IdentityProviderLocal` adapter

- [x] 4.1 Implement `IdentityProviderLocal` against `auth_local_users`
      using `SqlAlchemyUnitOfWork.current_session`. Use bcrypt
      (rounds=12) for password hashes and SHA-256 for verification-code
      hashes.
- [x] 4.2 Implement HS256 JWT signing and verification with
      `LOCAL_JWT_SECRET`. Claim shape MUST equal
      `{sub, email, email_verified, custom:active_tenant, aud, iss,
      exp, iat}`.
- [x] 4.3 Implement lockout policy: 5 failed attempts within 1h locks
      the account for 1h; the counter resets on success.
- [x] 4.4 Implement signup-code TTL (15 min) and reset-code TTL (10 min)
      per [`docs/06-security-model.md`](../../../docs/06-security-model.md).
- [x] 4.4a `forgot_password(email=...)` SHALL silently no-op when no
      `auth_local_users` row matches the email (enumeration-resistance
      half from the local side; no row inserted, no Mailpit send).
- [x] 4.4b `global_signout(external_sub=...)` SHALL return `None` for
      any `external_sub` (MVP has no refresh-token table to clear);
      placeholder for the post-MVP `auth_local_refresh_tokens` truncate.
- [x] 4.4c Issue ID tokens with the same TTL as access tokens
      (`settings.jwt_access_ttl_seconds`, default 3600 s) per
      [`docs/06-security-model.md` §TTLs](../../../docs/06-security-model.md#ttls).
- [x] 4.5 Integration test against a Postgres testcontainer covering the
      full local loop: register → confirm → login → refresh → forgot →
      reset.

## 5. `IdentityProviderCognito` adapter

- [x] 5.1 Implement `IdentityProviderCognito(client, user_pool_id,
      app_client_id)` calling `cognito-idp` for `SignUp`, `ConfirmSignUp`,
      `ResendConfirmationCode`, `InitiateAuth` (USER_PASSWORD_AUTH and
      REFRESH_TOKEN_AUTH), `GlobalSignOut`, `ForgotPassword`,
      `ConfirmForgotPassword`, `ChangePassword`,
      `AdminUpdateUserAttributes`, `AdminGetUser`.
- [x] 5.2 Implement the JWKS cache: module-level dict guarded by a lock,
      TTL 24h, refresh-on-miss; on JWKS fetch error fall back to the
      stale cache when present.
- [x] 5.3 Verify access tokens with RS256 against the cached JWKS;
      enforce `aud`, `iss`, `exp` claims; surface
      `auth.token_expired` vs `auth.invalid_credentials` to the HTTP
      layer.
- [x] 5.4 Unit tests with mocked `boto3` client covering: successful
      auth path; expired token rejection; JWKS cache miss; JWKS error
      with stale cache; JWKS error with empty cache (raises).
- [x] 5.5 `forgot_password(email=...)` SHALL swallow Cognito's
      `UserNotFoundException` and return a result whose shape matches a
      real-account reset; `InvalidParameterException` SHALL still
      propagate (HTTP 422). Test both branches with a mocked client.
- [x] 5.6 `global_signout(external_sub=...)` SHALL swallow
      `UserNotFoundException` and `NotAuthorizedException` and return
      `None`; only successful 2xx and unexpected 5xx propagate. Test
      with a mocked client.

## 6. `EmailSender` adapters

- [x] 6.1 Implement `EmailSenderSmtp(host, port)` using `aiosmtplib`,
      no TLS, no auth (Mailpit).
- [x] 6.2 Implement `EmailSenderSes(client, from_address)` using SESv2
      `send_email` with the verified sender; raises a typed error on
      non-2xx so use cases can map to a 5xx with a clear `code`.
- [x] 6.3 Author signup-verification and password-reset HTML/text
      templates under `contexts/identity/adapters/outbound/email/templates/`.

## 7. `UserRepository` adapter (SQLAlchemy)

- [x] 7.1 Implement `UserRepositorySqlAlchemy(uow)`: `get_by_id`,
      `get_by_external_sub`, `add`, `update`. All reads/writes go
      through `uow.current_session`.
- [x] 7.2 Map between the `User` aggregate and an internal row table
      (`UserRow`) — no SQLAlchemy import inside `domain/`.
- [x] 7.3 Integration test against a testcontainer: round-trip
      add/get/update preserves `preferences` JSONB.

## 8. HTTP adapters (`contexts/identity/adapters/inbound/http/`)

- [x] 8.1 Author routers under `/v1/auth/`:
      `POST /register`, `/confirm-signup`, `/resend-code`, `/login`,
      `/refresh`, `/password/forgot`, `/password/reset`,
      `/change-password`, `/logout`; and `/v1/me` with `GET` and `PATCH`.
      `POST /v1/auth/logout` returns HTTP 204 on success with an empty
      body and is idempotent (a replay still returns 204).
- [x] 8.2 Pydantic request/response schemas per endpoint, RFC-7807
      problem-details on errors with stable `code` values
      (`auth.invalid_credentials`, `auth.token_expired`,
      `auth.signup_email_not_confirmed`,
      `auth.lockout_active`).
- [x] 8.3 Implement `auth_middleware`: read `Authorization: Bearer`,
      validate per `APP_ENV` (HS256 vs RS256 via Cognito JWKS), extract
      `sub`/`email`/`custom:active_tenant`, populate
      `CurrentUserContext`. 401 on missing/invalid.
- [x] 8.4 Implement the path allowlist: unauthenticated routes (the 7
      `/v1/auth/*` endpoints — everything except `change-password` and
      `logout` — plus `POST /v1/invitations/{token}/accept`,
      `/healthz`, `/readyz`, `/docs`, `/openapi.json`) and the
      authenticated-without-tenant routes (`GET /v1/me`, `PATCH /v1/me`,
      `POST /v1/auth/logout`, `POST /v1/tenants`).
- [x] 8.5 Router-level integration tests using `httpx.AsyncClient` over
      the ASGI app, against a Postgres testcontainer.

## 9. Bootstrap wiring

- [x] 9.1 Add `build_identity_provider()` to `bootstrap/container.py`:
      branches on `settings.app_env`.
- [x] 9.2 Add `build_email_sender()` to `bootstrap/container.py`:
      branches on `settings.app_env`.
- [x] 9.3 Mount the identity router and install `AuthMiddleware` in
      `bootstrap/api.py`. Middleware order: CORS → Auth → routes.
- [x] 9.4 Extend the `domain-purity` contract in `apps/api/.importlinter`
      to cover `contexts.identity.domain`.

## 10. Alembic migration 0002

- [x] 10.1 Author `0002_identity.py` with `down_revision='0001_shared_kernel'`.
- [x] 10.2 Enable `CREATE EXTENSION IF NOT EXISTS citext` (move out of
      `docker/postgres-init.sql` if present).
- [x] 10.3 Expand `users` with `external_sub TEXT UNIQUE NOT NULL`,
      `email CITEXT UNIQUE NOT NULL`, `display_name TEXT NOT NULL DEFAULT ''`,
      `locale TEXT NOT NULL DEFAULT 'es-NI'`, `timezone TEXT NOT NULL
      DEFAULT 'America/Managua'`, `preferences JSONB NOT NULL DEFAULT '{}'`.
- [x] 10.4 In `upgrade()`, branch on `os.environ.get("APP_ENV","")` —
      when `local`, create `auth_local_users` with the columns from
      [`docs/06-security-model.md` §Local adapter](../../../docs/06-security-model.md#local-adapter-identityproviderlocal).
- [x] 10.5 Reversible `downgrade()` that drops `auth_local_users IF
      EXISTS` and removes the column expansions.
- [x] 10.6 Log which branch the migration took (`local` or `aws`) so
      operators see the choice in the apply output.

## 11. Frontend (`apps/web/src/features/auth/` + routes)

- [x] 11.1 Regenerate `src/api/schema.d.ts` from the running API
      (`pnpm gen:api`) and commit.
- [x] 11.2 Create Zod schemas per form under
      `apps/web/src/features/auth/schemas/`: `signupSchema`,
      `confirmSchema`, `loginSchema`, `forgotSchema`, `resetSchema`,
      `meSchema`.
- [x] 11.3 Implement an in-memory token store (module-level closure,
      not React state) exposing `getAccessToken`, `getRefreshToken`,
      `setTokens`, `clear`.
- [x] 11.4 Implement the 401 interceptor on the `openapi-fetch` client:
      on a single 401, call `POST /v1/auth/refresh` once with the
      in-memory refresh token and retry the original request once;
      on the second failure, `clear()` and `navigate('/login')`.
- [x] 11.5 Author routes `/signup`, `/confirm`, `/login`,
      `/forgot-password`, `/reset-password`, `/me` under
      `apps/web/src/routes/`. Each route is a `createFileRoute(...)`
      that uses the generated TanStack Query hooks.
- [x] 11.6 Vitest unit tests for the token store and the 401 interceptor
      (mocked fetch).

## 12. Tests

- [x] 12.1 Unit: `Email`, `Password.validate_policy`, each use case
      with mocked ports.
- [x] 12.2 Integration: `IdentityProviderLocal` end-to-end against
      Postgres testcontainer; `UserRepository` round-trip.
- [x] 12.3 E2E: `POST /v1/auth/register` → poll Mailpit's HTTP API for
      the verification code → confirm → login → `GET /v1/me`.
- [x] 12.4 Contract test `IdentityProvider` parametrised over Local and
      Cognito, skipped when AWS credentials are absent.

## 13. AWS Terraform — `auth/` enrichment

- [x] 13.1 Add `explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH",
      "ALLOW_REFRESH_TOKEN_AUTH"]` to the existing SPA app client.
- [x] 13.2 Author the IAM policy attached to the API Fargate task role
      with the cognito-idp action allow-list from §Why.
- [x] 13.3 Output `user_pool_domain` (the literal
      `nica-erp.auth.us-east-1.amazoncognito.com`) so the
      `secrets/` module can store it in SSM.
- [x] 13.4 Pin `access_token_validity = 60`,
      `id_token_validity = 60`, `refresh_token_validity = 30`, and
      `token_validity_units = { access_token = "minutes", id_token =
      "minutes", refresh_token = "days" }` on the SPA app client per
      [`docs/06-security-model.md` §TTLs](../../../docs/06-security-model.md#ttls)
      (do not rely on Cognito region defaults).

## 14. AWS Terraform — new `email/` module

- [x] 14.1 Create `infra/terraform/modules/email/`: variables
      (`from_address`, `tags`); resource
      `aws_sesv2_email_identity.sender` for the address; output
      `from_address`.
- [x] 14.2 Document the operator verification ritual in the module
      README (operator clicks the AWS confirmation link before the
      first signup).
- [x] 14.3 Tag the identity with `Project=nica-erp`.

## 15. AWS Terraform — `secrets/` and `envs/demo/`

- [x] 15.1 Add SSM `String` parameter
      `/nica-erp/demo/cognito/user-pool-domain` sourced from
      `module.auth.user_pool_domain`.
- [x] 15.2 Add SSM `String` parameter
      `/nica-erp/demo/ses/from-address` sourced from
      `var.from_address`.
- [x] 15.3 In `infra/terraform/envs/demo/main.tf`, compose
      `module "email"` and wire its output into `module "secrets"`.
- [x] 15.4 Extend `infra/terraform/modules/compute/` API task
      definition's `secrets[]` array with `SES_FROM_ADDRESS` ← SSM
      `/nica-erp/demo/ses/from-address`, and grant the task role
      `ssm:GetParameters` on that ARN.

## 16. Verification

- [x] 16.1 Local: `make local-up && make migrate && make api`; run the
      `curl` flow from the sprint doc's
      [§Verifiable outcome (local)](../../../docs/sprints/02-identity-and-rbac.md#verifiable-outcome-local).
- [x] 16.2 Local: SPA flow — sign up at `localhost:5173/signup`, confirm
      via the Mailpit message, log in, land on `/me`.
- [x] 16.3 Lint: `make lint` + `uv run lint-imports` (domain-purity
      includes `contexts.identity.domain`).
- [ ] 16.4 AWS (when account verification clears): `make deploy` →
      operator verifies SES sender in the console → sign up against
      Cognito → `/me` shows the live RS256 JWT's profile.

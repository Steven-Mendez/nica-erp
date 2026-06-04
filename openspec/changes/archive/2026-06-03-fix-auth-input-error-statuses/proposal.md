## Why

The identity context's HTTP adapter (`apps/api/src/contexts/identity/adapters/inbound/http/errors.py`) collapses every "wrong-input" failure on the public auth endpoints into `InvalidCredentialsError` → 401 with `code: "auth.invalid_credentials"`. That includes:

- `POST /v1/auth/confirm-signup` with a wrong or expired OTP
- `POST /v1/auth/password/reset` with a used or expired code
- `POST /v1/auth/resend-code` when the IdP rate-limits

None of those scenarios are authentication failures — there is no session to reject. 401 is wrong on HTTP semantics, and the IdP adapter already acknowledges it: `apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py:262-265` carries the comment *"the typed error catalogue does not yet ship a dedicated RateLimitedError, so we surface InvalidCredentialsError. The HTTP adapter maps this to 400."* — the comment lies; the mapper produces 401.

The frontend already documents what the contract should be: `openspec/specs/frontend-auth-error-feedback/spec.md` lists `auth.invalid_confirmation_code`, `auth.reset_token_used`, and `auth.reset_token_expired` in the `messageForProblem` registry, and `apps/web/src/api/errors.ts:129,132,133` already ships Spanish copy for each. The codes are never emitted by the backend, so those mappings are dead.

The companion change `fix-unauth-401-interceptor` papered over the symptom on the SPA side by adding a `__bearerAttached` flag so the 401 interceptor does not redirect to `/login` for these cases. With the right status codes (400/410/429), the interceptor's bearer-attached check is only needed for the one legitimate 401 case — wrong login credentials.

## What Changes

### Identity application — typed errors for each failure mode

- `apps/api/src/contexts/identity/application/errors.py`:
  - Add `InvalidConfirmationCodeError(IdentityError)` for OTP failures during `POST /v1/auth/confirm-signup`.
  - Add `InvalidResetCodeError(IdentityError)` for invalid / used password-reset codes.
  - Add `ExpiredResetCodeError(InvalidResetCodeError)` for explicitly expired password-reset codes.
  - Add `ResendThrottledError(IdentityError)` carrying `retry_after_seconds: int` for the per-account resend cooldown.
- The application use cases (`ConfirmSignup`, `ResetPassword`, `ResendCode`) do not need code changes — they delegate to the IdP port and let the typed exception propagate.

### Identity outbound adapters — raise the specific types

- `apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py`:
  - `confirm_signup` raises `InvalidConfirmationCodeError("invalid code")` instead of `InvalidCredentialsError`.
  - `resend_confirmation` raises `ResendThrottledError(retry_after_seconds=...)` with the remaining cooldown computed from `_RESEND_COOLDOWN_SECONDS - elapsed`.
  - `confirm_forgot_password` raises `ExpiredResetCodeError("reset code expired")` when the stored row's `verification_code_expires_at < now`, and `InvalidResetCodeError("invalid or used reset code")` otherwise (hash mismatch or no row). This is the closest distinction the local adapter can make; "used" vs "never-issued" are indistinguishable at this layer.
- `apps/api/src/contexts/identity/adapters/outbound/identity_provider/cognito.py`:
  - `confirm_signup` raises `InvalidConfirmationCodeError` for `CodeMismatchException` / `ExpiredCodeException`.
  - `resend_confirmation` raises `ResendThrottledError` for `LimitExceededException` / `TooManyRequestsException` (Cognito throttle codes) with a conservative `retry_after_seconds=60`.
  - `confirm_forgot_password` raises `ExpiredResetCodeError` for `ExpiredCodeException` and `InvalidResetCodeError` for `CodeMismatchException`.
  - All other ClientError paths continue to raise `InvalidCredentialsError` (defensive default for unmapped Cognito failures).

### Identity HTTP error mapper — translate to the right status

- `apps/api/src/contexts/identity/adapters/inbound/http/errors.py`:
  - Map `InvalidConfirmationCodeError` → `400` with `code: "auth.invalid_confirmation_code"`, `title: "Invalid confirmation code"`.
  - Map `InvalidResetCodeError` → `410` with `code: "auth.reset_token_used"`, `title: "Reset link no longer valid"`. (Used vs unknown are observationally indistinguishable; "used" is the operator-friendly framing because the only path to seeing this error after a previous reset is reuse.)
  - Map `ExpiredResetCodeError` → `410` with `code: "auth.reset_token_expired"`, `title: "Reset link expired"`. Because `ExpiredResetCodeError` is a subclass of `InvalidResetCodeError`, register it FIRST in `to_problem_detail` so the more specific match wins.
  - Map `ResendThrottledError` → `429` with `code: "auth.resend_throttled"`, `title: "Resend rate-limited"`, plus a `Retry-After: <seconds>` response header and the `retry_after_seconds` extension on the problem body.
  - Register new exception handlers in `register_exception_handlers` mirroring the existing pattern (one handler per type, each calling `_problem_response`). The `ResendThrottledError` handler adds the `Retry-After` header via `_problem_response(..., extra_headers={"Retry-After": str(exc.retry_after_seconds)})`.
  - `InvalidCredentialsError` → 401 remains unchanged. Login, JWT verification, refresh-token validation, and change-password keep their 401 surface.

### Identity router OpenAPI hints

- `apps/api/src/contexts/identity/adapters/inbound/http/router.py`:
  - Update `_UNAUTHENTICATED_RESPONSES` (or its per-route override) so that `/auth/confirm-signup`, `/auth/password/reset`, and `/auth/resend-code` advertise 400 / 410 / 429 in their `responses=` block (in addition to the existing 401 and 422), so the regenerated `apps/web/src/api/schema.d.ts` reflects the new contract.
  - Login keeps its 401-only auth-error response set.

### Frontend — registry entry for the new code

- `apps/web/src/api/errors.ts`:
  - Add `auth.resend_throttled` → Spanish copy `"Espera unos segundos antes de pedir otro código."` to the `messageForProblem` registry.
  - Add `auth.resend_throttled` to the `KNOWN_AUTH_CODES` union used by the type-safe known-codes check (so the existing fallback path is preserved as a regression-resistance guard).
- No changes to the `__bearerAttached` flag, the interceptor, or any auth route component. The new status codes flow through the existing `mapProblemDetails` / `messageForProblem` / `FormErrorAlert` path with no SPA logic changes.

### Regenerated OpenAPI schema

- Regenerate `apps/web/src/api/schema.d.ts` via `pnpm -C apps/web gen:api` (or whichever script the project uses) after the backend route hints change so the typed client matches the new responses block.

### Tests

#### Backend

- `apps/api/tests/integration/contexts/identity/http/test_problem_mapping.py` (new): unit-level coverage of `to_problem_detail` for each new exception type — assert `(status, code, title)`.
- `apps/api/tests/integration/contexts/identity/http/test_resend_throttle_http.py` (new): integration test that hits `POST /v1/auth/resend-code` twice in quick succession and asserts the second call returns `429`, `code: "auth.resend_throttled"`, and a `Retry-After` header.
- `apps/api/tests/e2e/contexts/identity/test_auth_flow.py`: extend the existing `test_confirm_signup_*` suite with a "wrong OTP returns 400 + invalid_confirmation_code" scenario, and add a "used password-reset code returns 410 + reset_token_used" scenario.
- Existing tests asserting `401 + auth.invalid_credentials` on wrong-OTP / used-reset-code paths are updated to assert the new status + code.

#### Frontend

- `apps/web/tests/unit/api/errors.test.ts` (extend): assert `messageForProblem({ code: "auth.resend_throttled" })` returns the Spanish copy, and that it falls through to the generic fallback for an unknown code (regression guard).

## Capabilities

### New Capabilities

- `identity-error-mapping`: codifies the contract that the identity context's HTTP adapter translates each typed application exception to a specific RFC-7807 problem response with a stable `code`, `title`, and HTTP status. Until now this lived implicitly in `errors.py`.

### Modified Capabilities

- `frontend-auth-error-feedback`: extend the `messageForProblem` registry contract with the new `auth.resend_throttled` entry.

## Impact

- Affected code:
  - `apps/api/src/contexts/identity/application/errors.py` — new exception types.
  - `apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py` — raise the new types.
  - `apps/api/src/contexts/identity/adapters/outbound/identity_provider/cognito.py` — raise the new types.
  - `apps/api/src/contexts/identity/adapters/inbound/http/errors.py` — map + register handlers.
  - `apps/api/src/contexts/identity/adapters/inbound/http/router.py` — OpenAPI response hints.
  - `apps/web/src/api/errors.ts` — registry entry for the new code.
  - `apps/web/src/api/schema.d.ts` — regenerated.
- Affected tests:
  - One new backend unit test file, one new backend integration test file, two new e2e scenarios.
  - One new frontend unit assertion.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append "Sprint follow-up — fix identity-context wrong-input statuses (2026-06-03)".
  - No ADR. The HTTP statuses move within the documented 4xx envelope; the contract codes were already promised by `frontend-auth-error-feedback`. This is implementation realignment, not a new architectural decision.
- Affected dependencies: none.
- Affected env: none.
- Affected infra: none.
- Out of scope:
  - The 401 interceptor's `__bearerAttached` discriminator stays in place — it is correct for the login-credentials case, which keeps its 401 contract.
  - Splitting `InvalidCredentialsError` further inside login / change-password / JWT-validation paths. Those keep 401.
  - Surfacing a distinct "code never issued" vs "code used" status on the password-reset path. The local adapter cannot distinguish them; both fall under `InvalidResetCodeError` → 410 `auth.reset_token_used`.

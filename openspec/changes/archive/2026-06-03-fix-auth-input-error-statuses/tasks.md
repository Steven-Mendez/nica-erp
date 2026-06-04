## 1. Sprint doc

- [x] 1.1 Append "Sprint follow-up — fix identity-context wrong-input statuses (2026-06-03)" to `docs/sprints/03-tenants-and-rls.md` (after the most recent 3.x follow-up). Cover: the audit observation (OTP / reset / resend failures all surface as 401 + `auth.invalid_credentials`, masking the existing per-failure copy the frontend already maps), the root cause (`InvalidCredentialsError` is the catch-all for both auth failures and input failures across `local.py` / `cognito.py`), the chosen fix (split into `InvalidConfirmationCodeError`, `InvalidResetCodeError` + `ExpiredResetCodeError`, and `ResendThrottledError`, mapped to 400 / 410 / 410 / 429 respectively), and the non-goals (no change to login's 401 surface, no `__bearerAttached` interceptor removal). Do not reference `openspec/changes/*` (per the doc-hierarchy rule — `docs/` may only be referenced from openspec, not the other way around).

## 2. Application errors

- [x] 2.1 In `apps/api/src/contexts/identity/application/errors.py`, add `InvalidConfirmationCodeError(IdentityError)`, `InvalidResetCodeError(IdentityError)`, `ExpiredResetCodeError(InvalidResetCodeError)`, and `ResendThrottledError(IdentityError)` (with `retry_after_seconds: int` constructor parameter).
- [x] 2.2 Extend `__all__` with the four new names.

## 3. Outbound adapter — local

- [x] 3.1 In `apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py`, `confirm_signup`: replace both `raise InvalidCredentialsError("invalid code")` sites with `raise InvalidConfirmationCodeError("invalid code")`.
- [x] 3.2 `resend_confirmation`: replace `raise InvalidCredentialsError("resend rate-limited")` with `raise ResendThrottledError(retry_after_seconds=max(_RESEND_COOLDOWN_SECONDS - int((now - last_resend_at).total_seconds()), 1))`. Remove the misleading "HTTP adapter maps this to 400" comment.
- [x] 3.3 `confirm_forgot_password`: reorder checks so the expiration branch runs FIRST: if `expires_at is not None and expires_at < self.now()`, raise `ExpiredResetCodeError("reset code expired")`. Then the existing "no row / no hash / no expiry / hash mismatch" branch raises `InvalidResetCodeError("invalid or used reset code")`.
- [x] 3.4 Update the imports at the top of `local.py` to add the new error names.

## 4. Outbound adapter — cognito

- [x] 4.1 In `apps/api/src/contexts/identity/adapters/outbound/identity_provider/cognito.py`, `confirm_signup`: change the `CodeMismatchException` / `ExpiredCodeException` branch to raise `InvalidConfirmationCodeError("confirmation code is invalid or expired") from exc`.
- [x] 4.2 `resend_confirmation`: after the `UserNotFoundException` / "already confirmed" early returns, add a check for `code in {"LimitExceededException", "TooManyRequestsException"}` that raises `ResendThrottledError(retry_after_seconds=60) from exc`. Keep the existing fall-through `raise InvalidCredentialsError(...)` for any other error code (defensive default).
- [x] 4.3 `confirm_forgot_password`: split the `CodeMismatchException` / `ExpiredCodeException` branch — `ExpiredCodeException` → `ExpiredResetCodeError(...)`, `CodeMismatchException` → `InvalidResetCodeError(...)`. Other errors keep raising `InvalidCredentialsError`.
- [x] 4.4 Update the imports at the top of `cognito.py` to add the new error names.

## 5. HTTP error mapper

- [x] 5.1 In `apps/api/src/contexts/identity/adapters/inbound/http/errors.py`, import the four new exception types.
- [x] 5.2 In `to_problem_detail`, add the new isinstance branches BEFORE the existing `InvalidCredentialsError` branch (so the more specific types win). Order: `ExpiredResetCodeError` → 410 `auth.reset_token_expired`; `InvalidResetCodeError` → 410 `auth.reset_token_used`; `InvalidConfirmationCodeError` → 400 `auth.invalid_confirmation_code`; `ResendThrottledError` → 429 `auth.resend_throttled` (carrying `retry_after_seconds` as an extension on the problem body).
- [x] 5.3 In `register_exception_handlers`, register one `@app.exception_handler` per new type. The handler for `ResendThrottledError` MUST set `extra_headers={"Retry-After": str(exc.retry_after_seconds)}` on `_problem_response`.

## 6. Router OpenAPI hints

- [x] 6.1 In `apps/api/src/contexts/identity/adapters/inbound/http/router.py`, extend the `responses=` block on `/auth/confirm-signup` to include `400: {**_PROBLEM, "description": "Invalid confirmation code"}` in addition to the existing entries.
- [x] 6.2 Extend the `responses=` block on `/auth/password/reset` to include `410: {**_PROBLEM, "description": "Reset link no longer valid"}` in addition to existing entries.
- [x] 6.3 Extend the `responses=` block on `/auth/resend-code` to include `429: {**_PROBLEM, "description": "Resend rate-limited"}` in addition to existing entries.
- [x] 6.4 Leave login's responses block unchanged (it still only returns 401 / 422 / 429 for the lockout case).

## 7. Backend tests

- [x] 7.1 Update `apps/api/tests/integration/contexts/identity/test_identity_provider_local.py`: the existing `with pytest.raises(InvalidCredentialsError)` blocks covering `confirm_signup` with a bad code and `confirm_forgot_password` with a bad code should be updated to expect `InvalidConfirmationCodeError` and `InvalidResetCodeError` / `ExpiredResetCodeError` respectively. Add a new case for `resend_confirmation` raising `ResendThrottledError` when called twice inside the cooldown window.
- [x] 7.2 Update `apps/api/tests/unit/contexts/identity/adapters/outbound/identity_provider/test_cognito.py`: the `confirm_signup` / `confirm_forgot_password` / `resend_confirmation` cases assert the new exception types in place of `InvalidCredentialsError` where they correspond to wrong-OTP / used-reset-code / throttle.
- [x] 7.3 Create `apps/api/tests/integration/contexts/identity/http/test_problem_mapping.py` (new): for each new exception type, instantiate it, call `to_problem_detail`, and assert the `(status, code, title)` triple matches the proposal. Also assert the `Retry-After` header is set on the `ResendThrottledError` response via `register_exception_handlers` + a `TestClient` that raises the exception from a stub route.
- [x] 7.4 Update `apps/api/tests/e2e/contexts/identity/test_auth_flow.py`: add (a) "wrong OTP returns 400 + `auth.invalid_confirmation_code`" against `/v1/auth/confirm-signup`, (b) "used reset code returns 410 + `auth.reset_token_used`" against `/v1/auth/password/reset`, (c) "expired reset code returns 410 + `auth.reset_token_expired`" (advance the clock past `password_reset_code_ttl_seconds`). Leave the existing "wrong password returns 401 + `auth.invalid_credentials`" and "no bearer returns 401 + `auth.invalid_credentials`" cases unchanged — they are regression guards.
- [x] 7.5 Run `cd apps/api && uv run pytest -q`. All tests must pass.

## 8. Frontend registry

- [x] 8.1 In `apps/web/src/api/errors.ts`, add `"auth.resend_throttled": () => "Espera unos segundos antes de pedir otro código."` to the `messageForProblem` registry.
- [x] 8.2 Add `"auth.resend_throttled"` to the `KNOWN_AUTH_CODES` tuple (or whatever the existing union shape is named).
- [x] 8.3 In `apps/web/tests/unit/api/errors.test.ts`, add a case asserting `messageForProblem({ code: "auth.resend_throttled", status: 429 })` returns the Spanish copy.
- [x] 8.4 Run `pnpm -C apps/web typecheck`, `pnpm -C apps/web lint`, `pnpm -C apps/web test`. All must pass.

## 9. OpenAPI regeneration

- [x] 9.1 Run `pnpm -C apps/web gen:api` (or the project's documented regenerate script) so `apps/web/src/api/schema.d.ts` matches the new backend `responses=` blocks. Commit the regenerated file as part of this change set.
- [x] 9.2 Re-run `pnpm -C apps/web typecheck` after regeneration; no consumers should have to change because they only branch on the runtime `code` field, not the typed status union.

## 10. Forward-compat

- [x] 10.1 Grep `apps/api/src` for remaining `InvalidCredentialsError` raises and confirm each one is in a *credential rejection* path (login, JWT verify, refresh, change-password). Wrong-input call sites should be empty after this change.
- [x] 10.2 Grep `apps/web/src` for `auth.invalid_credentials` to confirm route components do not branch on it for OTP / reset code paths (they should branch on the new codes).
- [x] 10.3 `openspec validate fix-auth-input-error-statuses --strict` exits 0.

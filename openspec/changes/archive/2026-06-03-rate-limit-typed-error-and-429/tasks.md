## 1. Application error

- [x] 1.1 Added `RateLimitedError(scope, retry_after_seconds)` to `apps/api/src/contexts/identity/application/errors.py`. `ResendThrottledError` is retained as a `RateLimitedError` subclass so existing imports keep working — both surface `code: "auth.rate_limited"`.
- [x] 1.2 Both classes exported from `application/errors.py`'s `__all__`.

## 2. Local IdP — raise typed error

- [x] 2.1 `local.py:resend_confirmation` now raises `RateLimitedError(scope="resend", retry_after_seconds=remaining)`.
- [x] 2.2 No inline-workaround comment to delete (the audit's `local.py:259` reference predates an earlier cleanup; the code already raised the typed error).

## 3. HTTP mapping

- [x] 3.1 `to_problem_detail` maps `RateLimitedError` to 429 + Spanish title `Demasiados intentos` + Spanish detail (`Espera <N> s antes de intentar de nuevo.`) + body fields `code`, `retry_after_seconds`, `scope`. The exception handler also sets the `Retry-After: <N>` header.
- [x] 3.2 The integration test `test_resend_throttled_response_carries_retry_after_header` exercises the full ASGI path and asserts the header survives.

## 4. Frontend copy

- [x] 4.1 `auth.rate_limited` entry added to `apps/web/src/api/errors.ts`: with `retry_after_seconds`, renders `Demasiados intentos. Intenta de nuevo en {{n}} segundos.`; without, falls back to the generic copy.
- [x] 4.2 The per-code formatter API in `SPANISH_BY_CODE` already accepts the parsed problem, so no template helper was required.

## 5. Tests

- [x] 5.1 Backend integration `test_resend_confirmation_rate_limited_within_window` (existing) now asserts the `scope` field; backend mapping unit `test_resend_throttled_maps_to_429_with_rate_limited_code_and_scope` asserts the code rename.
- [x] 5.2 E2E `test_resend_code_within_cooldown_returns_429_resend_throttled` asserts the 429, the `Retry-After` header, `code: "auth.rate_limited"`, `scope: "resend"`, and `retry_after_seconds`.
- [x] 5.3 Frontend Vitest `auth.rate_limited` cases (with and without `retry_after_seconds`) added to `messageForProblem.test.ts`. `KNOWN_AUTH_PROBLEM_CODES` updated.

## 6. Validation

- [x] 6.1 `openspec validate rate-limit-typed-error-and-429 --strict` exits 0.

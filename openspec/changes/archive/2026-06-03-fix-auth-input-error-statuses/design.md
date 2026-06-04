# Design — fix-auth-input-error-statuses

## Problem

`InvalidCredentialsError` is the identity context's catch-all for "the
input did not match what the IdP expected." It is raised in eight
distinct call sites across `local.py` and `cognito.py` and every one
maps to 401 in the HTTP adapter. The semantic spread is too wide:

| Caller | Failure mode | Should map to |
|---|---|---|
| `authenticate` | Wrong password / no user | 401 (current — correct) |
| `verify_token`, `refresh_token` | Bad JWT, malformed claims, used refresh | 401 (current — correct) |
| `change_password` | Wrong old password | 401 (current — correct) |
| `confirm_signup` | Wrong / expired OTP | **400 — input validation** |
| `resend_confirmation` | Per-account cooldown tripped | **429 — throttle** |
| `confirm_forgot_password` | Used or expired reset code | **410 — one-time secret gone** |

The first three rows are authentication-shaped (rejecting a credential
the caller presented as proof of identity). The last three are *input
validation* — there is no session, no Authorization header, just a
form submission that should land in the route component's
`FormErrorAlert` like any other "bad input" 4xx.

The frontend already published the codes it expects in
`openspec/specs/frontend-auth-error-feedback/spec.md` (`auth.invalid_confirmation_code`,
`auth.reset_token_used`, `auth.reset_token_expired`). The registry in
`apps/web/src/api/errors.ts` already maps them to Spanish copy. The
backend never emits them; the registry entries are dead code.

## Design

### Three new typed exceptions

```python
# apps/api/src/contexts/identity/application/errors.py

class InvalidConfirmationCodeError(IdentityError):
    """The OTP supplied to /v1/auth/confirm-signup did not match."""

class InvalidResetCodeError(IdentityError):
    """The reset code is invalid — unknown, already used, or hash mismatch."""

class ExpiredResetCodeError(InvalidResetCodeError):
    """The reset code was issued but its TTL has elapsed."""

class ResendThrottledError(IdentityError):
    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__(f"Resend throttled for {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds
```

`ExpiredResetCodeError` subclasses `InvalidResetCodeError` so callers
that only care "this code is no good, render the generic alert"
(future, not today) can `except InvalidResetCodeError` and catch
both. The HTTP mapper must register `ExpiredResetCodeError` BEFORE
`InvalidResetCodeError` in `to_problem_detail`'s isinstance chain so
the more specific match wins; same in `register_exception_handlers`.

### Mapper additions

```python
if isinstance(exc, ExpiredResetCodeError):
    return (410, _problem(410, "auth.reset_token_expired",
                          "Reset link expired",
                          detail=str(exc) or None))
if isinstance(exc, InvalidResetCodeError):
    return (410, _problem(410, "auth.reset_token_used",
                          "Reset link no longer valid",
                          detail=str(exc) or None))
if isinstance(exc, InvalidConfirmationCodeError):
    return (400, _problem(400, "auth.invalid_confirmation_code",
                          "Invalid confirmation code",
                          detail=str(exc) or None))
if isinstance(exc, ResendThrottledError):
    return (429, _problem(429, "auth.resend_throttled",
                          "Resend rate-limited",
                          detail=str(exc) or None,
                          retry_after_seconds=exc.retry_after_seconds))
```

The handler for `ResendThrottledError` adds the `Retry-After` header
via `_problem_response(..., extra_headers={"Retry-After": str(...)})`
— the existing `AuthLockoutActiveError` handler is the template.

### Adapter site changes

`local.py`:

```python
# confirm_signup
if stored_hash is None or expires_at is None or ...:
    raise InvalidConfirmationCodeError("invalid code")

# resend_confirmation
remaining = _RESEND_COOLDOWN_SECONDS - int((now - last_resend_at).total_seconds())
raise ResendThrottledError(retry_after_seconds=max(remaining, 1))

# confirm_forgot_password
if expires_at is not None and expires_at < self.now():
    raise ExpiredResetCodeError("reset code expired")
if stored_hash is None or expires_at is None or _sha256(code) != stored_hash:
    raise InvalidResetCodeError("invalid or used reset code")
```

The expiration check moves *before* the hash check so an expired but
otherwise-matching code raises the more specific error.

`cognito.py`:

```python
# confirm_signup
if err_code == "CodeMismatchException":
    raise InvalidConfirmationCodeError("code mismatch") from exc
if err_code == "ExpiredCodeException":
    raise InvalidConfirmationCodeError("code expired") from exc
# resend_confirmation
if code in {"LimitExceededException", "TooManyRequestsException"}:
    raise ResendThrottledError(retry_after_seconds=60) from exc
# confirm_forgot_password
if err_code == "ExpiredCodeException":
    raise ExpiredResetCodeError("reset code expired") from exc
if err_code == "CodeMismatchException":
    raise InvalidResetCodeError("reset code mismatch") from exc
```

The Cognito adapter cannot recover a real `retry_after_seconds` from
`LimitExceededException`, so 60 is a conservative fallback that
matches the Cognito-side cooldown documented in the AWS SDK guide.

### Router OpenAPI response hints

```python
_UNAUTHENTICATED_RESPONSES = {
    400: {**_PROBLEM, "description": "Input validation failure"},
    410: {**_PROBLEM, "description": "One-time secret no longer valid"},
    422: {**_PROBLEM, "description": "Request validation failed"},
    429: {**_PROBLEM, "description": "Throttled"},
    **_UNAUTHENTICATED_RESPONSES,  # existing 401 entry
}
```

Login keeps a tighter `responses=` set — only 401 / 422 / 429 — since
none of the new 400 / 410 paths apply to it.

### Frontend registry — `auth.resend_throttled`

`messageForProblem` gains one entry:

```ts
"auth.resend_throttled": () => "Espera unos segundos antes de pedir otro código.",
```

The known-codes union grows by the same key. The interceptor stays
unchanged — 400 / 410 / 429 all fall through the "not a 401" return
path naturally.

## Alternatives considered

### Alt 1: collapse the new types into one `IdentityInputError`

Tempting, but the HTTP status differs per case (400 vs 410 vs 429),
the Spanish copy differs per case (the existing registry expects
three different strings), and `Retry-After` is only meaningful for
throttle errors. One type would force the mapper to peek at a
discriminator field; the typed-exception approach lets `isinstance`
do the dispatch and keeps `errors.py` flat.

### Alt 2: 400 for everything, drop 410 and 429

Simpler, but `Retry-After` on a 429 is what TanStack Query, the
browser DevTools network panel, and any future polling layer
recognise out of the box. And `410 Gone` is the precise RFC 9110
status for "this URL / one-time token used to be valid and is no
longer," which is exactly the password-reset flow's shape. The
extra precision costs almost nothing and yields better diagnostics.

### Alt 3: keep 401 and only add a richer `code`

This is the current state plus better strings. The 401 still
forces the `__bearerAttached` workaround in the interceptor, the
401 still propagates to any future analytics / WAF / CDN rule that
treats 401 as a credential failure, and the frontend interceptor
still has to special-case "no bearer was attached." Loses the whole
benefit.

### Alt 4: change the contract at `to_problem_detail` callsites instead of growing the exception catalogue

Have the use cases catch `InvalidCredentialsError` and re-raise a
`HTTPException(400, ...)`. Couples the use cases to FastAPI, which
the codebase deliberately avoids (the application layer stays
framework-free; only the adapter at `errors.py` knows about HTTP).
The proposed approach keeps the layering.

## Test coverage

Backend:

- `to_problem_detail` unit asserts for each new exception →
  `(status, code, title)`.
- HTTP integration assert that `POST /v1/auth/resend-code` twice in a
  row returns 429 with the `Retry-After` header.
- E2E:
  - Wrong OTP on `/v1/auth/confirm-signup` → 400 + `auth.invalid_confirmation_code`.
  - Used code on `/v1/auth/password/reset` → 410 + `auth.reset_token_used`.
  - Expired code on `/v1/auth/password/reset` → 410 + `auth.reset_token_expired` (advance `now` past the TTL).
  - Wrong password on `/v1/auth/login` still → 401 + `auth.invalid_credentials` (regression guard).
  - `GET /v1/me` with no token still → 401 + `auth.invalid_credentials` (regression guard).

Frontend:

- `apps/web/tests/unit/api/errors.test.ts` extended:
  - `messageForProblem({ code: "auth.resend_throttled" })` → expected Spanish copy.
  - Unknown code → generic fallback.

## Risks / failure modes

- **Existing integration / e2e tests asserting 401 on wrong OTP / used reset code break.** This is expected and is the surface area of the change. The tasks list calls each one out.
- **Cognito adapter retry-after is hard-coded to 60s.** Cognito does not expose the actual cooldown via its SDK; 60s is the AWS-published default for `LimitExceededException`. The `local.py` adapter computes the true remaining cooldown from `_RESEND_COOLDOWN_SECONDS`.
- **Frontend `__bearerAttached` becomes near-vestigial.** Login is the one remaining auth endpoint that returns 401 for wrong input; the flag still does real work there. We do not remove it — the interceptor logic stays the safer default in case a future endpoint adds a 401 surface.

## Out of scope

- Touching the auth-login-rate-limiting flow (`AuthLockoutActiveError` → 429). Already correct.
- Adding a new `IdentityInputError` umbrella base class. The flat hierarchy is fine; subclassing is only used where the spec wants it (Expired ⊂ Invalid reset code).
- A general "RateLimitedError" abstraction. The comment in `local.py:262` will be replaced by the actual implementation; the resend cooldown is the only resend-throttle site in the codebase right now, and login throttling already has its own typed error.

## Why

The 2026-06-03 in-browser audit (see `.claude/goals/audit-report-2026-06-03.md`,
F-002) reproduced a catastrophic first-run UX bug. After a user submits a
**wrong** OTP to `POST /v1/auth/confirm-signup` (which returns 401), the
**same email can never complete signup**. The next attempt with the correct
code returns:

- `HTTP 500 {"detail":"An unexpected error occurred."}` via curl, or
- `HTTP 503` via the browser (with the SPA correctly rendering the Spanish
  inline alert `Ocurrió un error. Intenta de nuevo.`).

The only known recovery is to abandon the email and sign up with a fresh
one. For real Nicaraguan SMB operators this is "the app is broken on the
second screen of my first day."

Root cause is local: `ConfirmSignup.execute` in
`apps/api/src/contexts/identity/application/use_cases/confirm_signup.py`
calls (in order)

1. `identity_provider.confirm_signup(email, code)` — IdP validates the
   code and runs `MARK_VERIFIED` on `auth_local_users`.
2. Inside `uow.begin()`, `user_repository.add(user)` — appends a `User`
   aggregate to the `users` table.

If a prior bad-code attempt left the row in a partially-verified state
(or, on the *second* good-code call following a *good* first call,
crash-recovery races a duplicate insert) the second `add` raises a raw
SQLAlchemy `IntegrityError` that the application layer does not catch.
The `IntegrityError` bubbles to the FastAPI exception handler as
`500 An unexpected error occurred`.

This change makes `ConfirmSignup` **idempotent**: on a valid code, the
use case SHALL succeed whether or not a `User` row already exists for
the same `external_sub`, and whether or not the previous attempt
committed `MARK_VERIFIED`. The outbox event is emitted exactly once
across retries.

## What Changes

### Backend — `ConfirmSignup` idempotency

- `apps/api/src/contexts/identity/application/use_cases/confirm_signup.py`:
  - Wrap the `user_repository.add(user)` call in a typed
    `AlreadyRegisteredError` branch: catch `IntegrityError` (or the
    repository's already-typed equivalent) and treat as "user already
    exists for this external_sub". In that branch, **do not** emit a
    second `UserRegistered` outbox event. Fetch the existing aggregate
    by `external_sub` for the return.
- `apps/api/src/contexts/identity/adapters/outbound/persistence/sqlalchemy/...`:
  - The user repository SHALL expose `find_by_external_sub(sub) -> User | None`
    if it does not already.
- `apps/api/src/contexts/identity/adapters/outbound/identity_provider/local.py`:
  - `confirm_signup` SHALL be safe to call twice with the same code: a
    second call after `MARK_VERIFIED` ran SHALL return the same
    `external_sub` instead of raising `InvalidCredentialsError`. The
    expired-or-mismatch path stays as-is.

### Backend — typed errors and HTTP mapping

- `apps/api/src/contexts/identity/application/errors.py`:
  - No new error class is required if `IntegrityError` is captured at
    the use-case layer. Keep `InvalidCredentialsError` for bad code.
- `apps/api/src/contexts/identity/adapters/inbound/http/errors.py`:
  - No mapping change.

### Tests

- Backend unit test in `apps/api/tests/unit/contexts/identity/use_cases/`:
  - "confirm a code twice with the same `external_sub` succeeds and
    emits exactly one `UserRegistered` outbox row."
- Backend integration test (postgres container) in
  `apps/api/tests/integration/contexts/identity/`:
  - "wrong code then right code on the same email returns 200 OK and
    the `users` table holds exactly one row."

## Non-goals

- Refactoring `ConfirmSignup` to a sourced/outbox-only model. Out of scope.
- Changing the local-IdP storage shape for `auth_local_users`. Out of scope.
- F-001 (the 401 interceptor) — that is owned by `fix-unauth-401-interceptor`.

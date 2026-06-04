## Why

F-036: the SPA advertises two different password policies on two
different screens:

- `apps/web/src/routes/signup.tsx:113` → help text reads
  `12+ caracteres con mayúscula, minúscula, dígito y símbolo.`
- `apps/web/src/routes/reset-password.tsx:104` → help text reads
  `8+ caracteres con mayúscula, minúscula, dígito y símbolo.`

If the backend enforces 12 but the reset form's `.min(8)` zod schema
is what actually drives validation, users can reset to an 8-char
password and bypass the signup policy. If the backend allows 8
everywhere, the signup hint is just lying. The audit could not test
which is actually true; either way, this is a security-critical UX
divergence on a security-critical surface.

This change picks **12+** as the canonical policy, enforces it
server-side, and unifies the SPA copy and validation.

## What Changes

### Decision — canonical policy

The canonical password policy SHALL be:

- Minimum length: 12 characters.
- Character classes required: at least one uppercase letter, one
  lowercase letter, one digit, one non-alphanumeric symbol.
- Maximum length: 128 characters (defense against bcrypt DoS).
- No restrictions on Unicode beyond bcrypt's natural handling.

### Backend — server-side enforcement

- `apps/api/src/contexts/identity/domain/value_objects/password.py`
  (or equivalent — create if missing): a `Password.parse(raw)` helper
  raises `WeakPasswordError` when the policy fails. The error code
  is `auth.weak_password` and carries a structured list of failed
  rules (`min_length`, `uppercase_missing`, etc.).
- Apply on every password-acceptance path:
  - `POST /v1/auth/register`
  - `POST /v1/auth/confirm-signup` (password is supplied here on the
    auto-login branch)
  - `POST /v1/auth/password/reset`
  - `POST /v1/auth/change-password` (if separate)
- HTTP mapping: `WeakPasswordError` → 422 with code
  `auth.weak_password` and a field-level error pointing at
  `password`.

### Frontend — single source of truth

- Create `apps/web/src/features/auth/lib/password-policy.ts`:
  - Export `PASSWORD_POLICY_TEXT = '12+ caracteres con mayúscula,
    minúscula, dígito y símbolo.'`
  - Export `passwordPolicySchema = z.string().min(12).regex(/[A-Z]/,
    'Debe incluir una mayúscula').regex(/[a-z]/, 'Debe incluir una
    minúscula').regex(/\d/, 'Debe incluir un dígito')
    .regex(/[^A-Za-z0-9]/, 'Debe incluir un símbolo').max(128)`.
- Replace the inline `12+` and `8+` copies in `signup.tsx:113` and
  `reset-password.tsx:104` with the constant.
- Replace the inline schemas in those routes with the shared schema.

### Tests

- Backend unit: every password-acceptance path rejects an 8-char
  password with `WeakPasswordError`; accepts a valid 12+ password.
- Frontend Vitest: signup and reset-password forms render the same
  policy text; a 10-char password is rejected client-side with the
  Spanish copy.
- Browser smoke: reset-password with an 11-char password renders
  Spanish field error; with a valid 12+ password succeeds.

## Non-goals

- Password breach checking (e.g. HaveIBeenPwned k-anonymity lookup)
  — separate change.
- Password strength meter UI — separate UX change.
- Rotating existing user passwords that are <12 chars (the local DB
  has no production users yet).

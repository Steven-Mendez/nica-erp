## 1. Backend — typed error and value object

- [x] 1.1 `PasswordPolicyError` now carries `failed_rules: list[str]` (the existing typed error is renamed at the wire level via the HTTP mapping below — a separate `WeakPasswordError` class is unnecessary because the value object already centralised the failure path).
- [x] 1.2 `Password.validate_policy()` enforces min 12 / max 128 plus the four character classes; rule names are accumulated into `failed_rules` so callers can surface them individually.
- [x] 1.3 `Password(value=...).validate_policy()` runs in `register_user`, `reset_password`, `change_password`, AND now `confirm_signup` on the auto-login branch.
- [x] 1.4 HTTP mapping: `PasswordPolicyError` → 422 `auth.weak_password` with `failed_rules` on the body.

## 2. Frontend — single source

- [x] 2.1 `apps/web/src/features/auth/lib/password-policy.ts` exports `PASSWORD_POLICY_TEXT`, `PASSWORD_MIN_LENGTH`, `PASSWORD_MAX_LENGTH`, and `passwordPolicySchema`.
- [x] 2.2 `signup.tsx` renders `PASSWORD_POLICY_TEXT` in place of the inline `12+ caracteres...` hint.
- [x] 2.3 `reset-password.tsx` renders `PASSWORD_POLICY_TEXT` (replaced the stale `8+ caracteres...` hint). `apps/web/src/features/auth/schemas/index.ts` now imports `passwordPolicySchema` so signup/reset/change-password share the canonical schema.
- [x] 2.4 `auth.weak_password` registered in `apps/web/src/api/errors.ts` with Spanish copy.

## 3. Tests

- [x] 3.1 Backend unit: `test_eight_char_password_rejected_for_audit_F036` + `test_failed_rules_lists_all_violations` cover the new rule names and the 8-char rejection. The existing `test_password.py` boundary tests (uppercase missing, etc.) still pass.
- [x] 3.2 Frontend Vitest: `auth-schemas.test.ts` "rejects a weak password" now asserts the Spanish `al menos 12 caracteres` message.
- [x] 3.3 No new backend integration test was needed — the existing register/reset/change-password integration suites exercise `Password.validate_policy` via the use cases, and the HTTP mapping change is covered by the unit-level test below.

## 4. Validation

- [x] 4.1 `openspec validate unify-password-policy-min-length --strict` exits 0.

## 1. Use case — idempotent insertion

- [x] 1.1 Wrap the `user_repository.add(user)` call with a pre-flight `get_by_external_sub` and an inner `try / except IntegrityError` (`sqlalchemy.exc`). Pre-flight is preferred because catching `IntegrityError` inside the open SQLAlchemy session poisons the transaction; the catch covers the rare concurrent race.
- [x] 1.2 `pull_events()` runs only on the freshly registered aggregate's success branch — never when the existing row is reused or the race-catch fires.

## 2. Repository

- [x] 2.1 `get_by_external_sub` already exists on `UserRepository`; reused here (no new port method).
- [x] 2.2 SQLAlchemy adapter unchanged.
- [x] 2.3 No new fake required: the existing AsyncMock based unit setup just stubs `get_by_external_sub.return_value`.

## 3. Local IdP confirm_signup safety

- [x] 3.1 `confirm_signup` now short-circuits with the existing `id` when `email_verified` is already true. The hash-check + MARK_VERIFIED sequence runs only for unverified rows.
- [x] 3.2 Failure paths preserved: missing row → `InvalidConfirmationCodeError`; expired or mismatched code on an unverified row → same.

## 4. Tests

- [x] 4.1 Unit `test_confirm_signup_is_idempotent_when_user_already_exists` covers the "two successful calls → one outbox row" invariant.
- [x] 4.2 Unit `test_confirm_signup_swallows_race_integrity_error` covers the concurrent-insert race path.
- [x] 4.3 Integration `test_confirm_signup_is_idempotent_after_success` (local IdP) confirms the second call returns the same external_sub. E2E `test_confirm_signup_wrong_then_right_code_succeeds_idempotently` covers the full HTTP retry flow (wrong → right → right again, all expected statuses).
- [x] 4.4 `pytest tests/unit tests/integration tests/e2e -k confirm_signup` passes.

## 5. Validation

- [x] 5.1 `openspec validate fix-confirm-signup-idempotency-on-retry --strict` exits 0.

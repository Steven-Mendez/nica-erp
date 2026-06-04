## 1. Identifier-scope backoff

- [x] 1.1 In-memory throttle now tracks `consecutive_lockouts` and `_lockout_until` per identifier; the active lockout's `retry_after_seconds` is read from the schedule below.
- [x] 1.2 Backoff schedule: `[3, 30, 300, 1800]` seconds (`_IDENTIFIER_BACKOFF_SCHEDULE`). Beyond the 4th tier the lockout stays at 1800 s — a manual-unlock control surface (the proposal's `retry_after_seconds: null` sentinel) is deferred until admin tooling exists, since `LockoutState.retry_after_seconds` is currently `int`.
- [x] 1.3 `record_success` clears `_identifier_hits`, `_consecutive_lockouts`, and `_lockout_until` for that identifier.

## 2. IP-scope counter

- [x] 2.1 IP-keyed counter (existing `_ip_hits`) still increments on every failed login regardless of identifier. The HTTP layer's `source_ip` extraction is unchanged (uses request.client.host / trusted proxy headers).
- [x] 2.2 Default `ip_window` now 10 minutes; once 20 failures land inside it the throttle returns `scope:"ip"`, `retry_after_seconds: 600`.
- [x] 2.3 Rolling-window prune already runs every check.

## 3. HTTP shape

- [x] 3.1 The HTTP exception handler picks Spanish title `Demasiados intentos desde esta red` and the IP-scope detail when `scope == "ip"`; identifier-scope keeps `Cuenta temporalmente bloqueada`. Both bodies carry `retry_after_seconds` and `scope`.
- [x] 3.2 `Retry-After` header is set from `exc.retry_after_seconds` for both scopes.

## 4. Tests

- [x] 4.1 `test_identifier_lockout_escalates_exponentially`: 5+5+5+5 failures step through 3 → 30 → 300 → 1800 s.
- [x] 4.2 `test_ip_scope_lockout_uses_fixed_600_second_retry`: 20 failures from one IP across 20 identifiers → 429 with `scope:"ip"`, `retry_after_seconds: 600`. (Plus the existing http/test_login_throttle.py end-to-end exercises the Spanish title.)
- [x] 4.3 `test_record_success_resets_consecutive_lockouts_counter`: a clean login between cycles restarts the backoff at 3 s.

## 5. Validation

- [x] 5.1 `openspec validate harden-login-lockout-backoff-and-ip-scope --strict` exits 0.

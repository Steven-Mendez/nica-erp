# auth-login-rate-limiting Specification

## Purpose
TBD - created by archiving change harden-auth-flows. Update Purpose after archive.
## Requirements
### Requirement: AuthenticateUseCase consults a LoginAttemptThrottle port before checking credentials

A `LoginAttemptThrottle` protocol SHALL be defined in
`apps/api/src/contexts/identity/application/` with the following
synchronous methods:

- `record_failure(identifier: str, source_ip: str, when: datetime) -> None`
- `record_success(identifier: str) -> None`
- `check(identifier: str, source_ip: str, when: datetime) -> LockoutState`

`LockoutState` SHALL be a value object with at minimum:
`locked: bool`, `retry_after_seconds: int` (≥ 1 when `locked` is
true; 0 when `locked` is false), and `scope: Literal["identifier",
"ip", "none"]`.

`AuthenticateUseCase` SHALL call `check` at the start of its execute
method, before any password comparison. If the returned
`LockoutState.locked` is true, the use case SHALL raise
`AuthLockoutActiveError(retry_after_seconds=…, scope=…)`. The check uses
the use case's existing `Clock` port for `when`.

On a failed authentication (wrong password, unknown identifier — the
case shapes are not distinguished externally), the use case SHALL
call `record_failure` with the identifier (as submitted, lowercased
for emails) and the source IP, before raising the existing
`InvalidCredentials` exception.

On a successful authentication, the use case SHALL call
`record_success(identifier)` after the token bundle is issued.

#### Scenario: Locked identifier short-circuits before the password check

- **WHEN** the throttle reports `LockoutState(locked=True, scope="identifier", retry_after_seconds=120)` for a given identifier
- **THEN** `AuthenticateUseCase.execute` raises `AuthLockoutActiveError` and never invokes the password-compare adapter

#### Scenario: Failure increments the throttle, then raises invalid credentials

- **WHEN** the throttle reports unlocked and the password compare fails
- **THEN** `record_failure` is called once with the identifier and IP, and `InvalidCredentials` is raised

#### Scenario: Success clears the identifier counter

- **WHEN** authentication succeeds for an identifier
- **THEN** `record_success(identifier)` is called after the token bundle is issued

### Requirement: HTTP router maps AuthLockoutActiveError to 429 + auth.lockout_active problem + Retry-After

The inbound HTTP router SHALL handle `AuthLockoutActiveError` exceptions raised by `AuthenticateUseCase` and respond:

- Status code: `429 Too Many Requests`
- `Content-Type: application/problem+json`
- Body includes `code: "auth.lockout_active"` and a Spanish-language
  `title`/`detail` consistent with the existing problem-doc style.
- Header: `Retry-After: <integer seconds from the exception>`.

The response body MUST include the `scope` field from `LockoutState`
so the frontend can choose between identifier-level and IP-level copy.

#### Scenario: Locked-out POST /v1/auth/login returns 429 with Retry-After

- **WHEN** `POST /v1/auth/login` is invoked with credentials whose identifier the throttle has locked
- **THEN** the response is `429`, the body is `application/problem+json` with `code: "auth.lockout_active"` and `scope: "identifier"`, and `Retry-After: 120` (or whatever the exception carried)

### Requirement: Identifier lockout fires at 5 failures / 15-minute sliding window, IP at 20 / 15 minutes

The default thresholds for the `LoginAttemptThrottle` adapters SHALL
be:

- **Identifier**: 5 failures within a 15-minute sliding window
  triggers `locked=True, scope="identifier"`; the lockout persists
  until the window slides such that the count is below 5; on
  `record_success(identifier)` the identifier's counter is reset.
- **IP**: 20 failures within a 15-minute sliding window triggers
  `locked=True, scope="ip"`; `record_success` does NOT reset the
  IP counter.

Both thresholds SHALL be overridable via the existing bootstrap
settings without code branches.

#### Scenario: Five identifier failures in 15 minutes triggers identifier lockout

- **WHEN** the throttle records 5 failures for `"user@example.com"` from any IP within 15 minutes
- **THEN** the next `check("user@example.com", …)` returns `locked=True, scope="identifier"`

#### Scenario: Successful auth clears identifier counter

- **WHEN** the throttle has 4 recorded failures for `"user@example.com"` and `record_success("user@example.com")` is called
- **THEN** the next `check` for the same identifier returns `locked=False` regardless of remaining IP-counter state

#### Scenario: IP threshold is independent of identifier

- **WHEN** the throttle records 20 failures from `203.0.113.4` against 20 different identifiers within 15 minutes
- **THEN** the next `check(<any-identifier>, "203.0.113.4")` returns `locked=True, scope="ip"`

### Requirement: Redis adapter fails open on connection errors

The `RedisLoginAttemptThrottle` adapter SHALL treat a Redis
connection failure as "no lockout" (`check` returns
`LockoutState(locked=False, retry_after_seconds=0, scope="none")`)
and SHALL log a warning. `record_failure` and `record_success`
SHALL swallow connection errors silently after logging.

#### Scenario: Redis unreachable does not deny logins

- **WHEN** the Redis client raises a connection error inside `check`
- **THEN** the adapter returns `LockoutState(locked=False, …)` and the use case proceeds with the password compare


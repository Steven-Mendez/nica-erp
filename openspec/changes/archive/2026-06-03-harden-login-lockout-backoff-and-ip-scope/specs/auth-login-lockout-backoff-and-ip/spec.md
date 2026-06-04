## ADDED Requirements

### Requirement: Identifier-scope login lockouts escalate with exponential backoff

The login lockout MUST escalate the lockout duration with each
consecutive lockout cycle for the same identifier. The schedule SHALL
be 3 seconds for the first cycle, 30 seconds for the second, 300
seconds for the third, 1800 seconds for the fourth, and `manual
unlock required` for any cycle beyond the fourth. A successful login
SHALL reset both the failed-attempt counter and the
consecutive-lockouts counter for that identifier.

#### Scenario: Three consecutive lockouts escalate 3 → 30 → 300

- **GIVEN** the identifier counter is clean for `eve@evil.test`
- **WHEN** 5 consecutive failed-login attempts are made
- **THEN** the next attempt SHALL receive 429 with
  `retry_after_seconds: 3`, scope `identifier`
- **WHEN** the operator waits 3 seconds and runs another 5 failed
  attempts
- **THEN** the next attempt SHALL receive 429 with
  `retry_after_seconds: 30`
- **WHEN** the cycle repeats once more
- **THEN** `retry_after_seconds` SHALL be 300

#### Scenario: Successful login clears the counters

- **GIVEN** an identifier that has hit the 30-second lockout once
- **WHEN** the operator waits out the lockout and submits the correct
  password
- **THEN** the API SHALL respond 200 with valid tokens
- **AND** subsequent failed attempts SHALL start counting from zero
  again (next lockout is 3 seconds, not 30)

### Requirement: IP-scope lockout fires independently of identifier

The login endpoint SHALL maintain an IP-keyed rolling counter
covering the most recent 10 minutes. After 20 failed login attempts
from the same source IP within that window — regardless of which
identifier was tried — the endpoint SHALL respond 429 with
`scope:"ip"`, `retry_after_seconds: 600`, and Spanish detail copy
`Demasiados intentos desde esta red. Espera <N> s antes de intentar
de nuevo.`. The response SHALL NOT reveal which identifier triggered
the lockout.

#### Scenario: IP-scope lockout from credential spraying across identifiers

- **GIVEN** a clean IP counter
- **WHEN** an attacker sends 20 failed login attempts from one IP
  using 20 different email identifiers
- **THEN** the 21st attempt from that IP SHALL receive 429 with
  `scope:"ip"`, `retry_after_seconds: 600`
- **AND** the response body SHALL NOT include any of the tried
  identifiers

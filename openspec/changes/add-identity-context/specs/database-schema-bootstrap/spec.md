## ADDED Requirements

### Requirement: Migration 0002 expands the `users` table

Alembic migration `0002_identity` SHALL have `down_revision =
"0001_shared_kernel"` and SHALL extend the existing `users` table
with: `external_sub TEXT UNIQUE NOT NULL`, `email CITEXT UNIQUE NOT
NULL`, `display_name TEXT NOT NULL DEFAULT ''`, `locale TEXT NOT NULL
DEFAULT 'es-NI'`, `timezone TEXT NOT NULL DEFAULT 'America/Managua'`,
`preferences JSONB NOT NULL DEFAULT '{}'`. The `id`, `created_at`, and
`updated_at` columns from 0001 SHALL remain unchanged. The
`citext` extension SHALL be enabled by this migration (`CREATE
EXTENSION IF NOT EXISTS citext`); it MUST NOT be assumed to exist
from `docker/postgres-init.sql`.

#### Scenario: `users` has the expanded columns post-upgrade

- **WHEN** `alembic upgrade head` is run against the 0001 schema
- **THEN** `\d users` SHALL list at least the columns `id`,
  `external_sub`, `email`, `display_name`, `locale`, `timezone`,
  `preferences`, `created_at`, `updated_at`

#### Scenario: `email` is `citext` not `text`

- **WHEN** the `users.email` column type is queried after upgrade
- **THEN** the column type SHALL be `citext` (case-insensitive
  comparison)

### Requirement: `auth_local_users` is created only when `APP_ENV=local`

The `upgrade()` step of migration 0002 SHALL read
`os.environ.get("APP_ENV", "")` and SHALL create the table
`auth_local_users` only when the value is `local`. The table SHALL
have columns `id UUID PRIMARY KEY`, `email CITEXT UNIQUE NOT NULL`,
`password_hash TEXT NOT NULL`, `email_verified BOOLEAN NOT NULL
DEFAULT FALSE`, `verification_code_hash TEXT`,
`verification_code_expires_at TIMESTAMPTZ`, `verification_attempts
INT NOT NULL DEFAULT 0`, `verification_attempts_reset_at TIMESTAMPTZ`,
`attributes JSONB NOT NULL DEFAULT '{}'`, `last_resend_at
TIMESTAMPTZ`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`,
`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. The migration SHALL
log the branch it took (`local` vs `aws`).

#### Scenario: Local migration creates the table

- **WHEN** `APP_ENV=local alembic upgrade head` is run
- **THEN** the schema SHALL contain a relation named
  `auth_local_users`

#### Scenario: AWS migration skips the table

- **WHEN** `APP_ENV=aws alembic upgrade head` is run
- **THEN** the schema SHALL NOT contain `auth_local_users`

### Requirement: Reversible `downgrade()`

`downgrade()` SHALL drop `auth_local_users` if and only if the table
exists (`DROP TABLE IF EXISTS auth_local_users`), SHALL drop the six
columns added to `users`, and SHALL drop the `citext` extension last.
After `downgrade()` the database SHALL match the post-0001 state.

#### Scenario: Round-trip leaves no residue

- **WHEN** `alembic upgrade head` then `alembic downgrade -1` is run
  against the 0001 schema (in either branch)
- **THEN** the `users` table SHALL have only the columns present in
  0001 and `auth_local_users` SHALL NOT exist

## ADDED Requirements

### Requirement: Migration 0001 creates required Postgres extensions

The baseline migration SHALL ensure that `pgcrypto` (for
`gen_random_uuid()`) and `citext` (for case-insensitive email storage)
are installed in the target database before any table is created.
Re-running the migration on a database where the extensions already exist
MUST NOT fail.

#### Scenario: Extensions are present after migrate
- **WHEN** `alembic upgrade head` is run against an empty database
- **THEN** `SELECT extname FROM pg_extension` SHALL include both
  `pgcrypto` and `citext`

### Requirement: tenants table exists with UUID primary key

The `tenants` table SHALL be created with at minimum: `id UUID PRIMARY
KEY DEFAULT gen_random_uuid()`, `name TEXT NOT NULL`, and `created_at
TIMESTAMPTZ NOT NULL DEFAULT now()`. Additional columns MAY be added by
later migrations without altering existing ones.

#### Scenario: Insert succeeds with only `name`
- **WHEN** an `INSERT INTO tenants (name) VALUES ('Acme')` runs after
  migrate
- **THEN** a row SHALL appear with a generated UUID and a timestamp

### Requirement: users table exists with CITEXT unique email

The `users` table SHALL be created with at minimum: `id UUID PRIMARY KEY
DEFAULT gen_random_uuid()`, `email CITEXT NOT NULL UNIQUE`, and
`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

#### Scenario: Case-insensitive uniqueness on email
- **WHEN** `INSERT INTO users (email) VALUES ('a@b.co')` succeeds, and a
  second `INSERT INTO users (email) VALUES ('A@B.CO')` is attempted
- **THEN** the second insert SHALL fail with a unique-violation error

### Requirement: outbox table ships in its final shape

The `outbox` table SHALL be created with: `event_id UUID PRIMARY KEY`,
`tenant_id UUID NOT NULL`, `event_type TEXT NOT NULL`, `event_version
INTEGER NOT NULL DEFAULT 1`, `aggregate_type TEXT NOT NULL`, `aggregate_id
UUID NOT NULL`, `payload JSONB NOT NULL`, `occurred_at TIMESTAMPTZ NOT
NULL DEFAULT now()`, `correlation_id UUID NULL`, `published_at TIMESTAMPTZ
NULL`, `publish_attempts INTEGER NOT NULL DEFAULT 0`. A partial index
`idx_outbox_unpublished` SHALL exist on `(occurred_at)` filtered by
`WHERE published_at IS NULL`. No row-level security policy SHALL be
created in this migration.

#### Scenario: tenant_id is required even before RLS arrives
- **WHEN** an `INSERT INTO outbox (...)` omits `tenant_id`
- **THEN** the insert SHALL fail with a NOT NULL violation

#### Scenario: Partial index restricted to unpublished rows
- **WHEN** the partial index is inspected via `pg_indexes` after migrate
- **THEN** its definition SHALL include `WHERE (published_at IS NULL)`

### Requirement: processed_events table for consumer idempotency

`processed_events` SHALL be created with composite primary key
`(consumer TEXT, event_id UUID)` and `processed_at TIMESTAMPTZ NOT NULL
DEFAULT now()`.

#### Scenario: Duplicate consumer/event_id insert is rejected
- **WHEN** the same `(consumer, event_id)` pair is inserted twice
- **THEN** the second insert SHALL fail with a primary-key violation

### Requirement: idempotency_keys table for inbound deduplication

`idempotency_keys` SHALL be created with composite primary key
`(tenant_id UUID, key TEXT, endpoint TEXT)`, plus `request_hash TEXT NOT
NULL`, `response_status INTEGER NULL`, `response_body JSONB NULL`, and
`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

#### Scenario: Same key for different endpoints does not collide
- **WHEN** the same `(tenant_id, key)` is used with two different
  `endpoint` values
- **THEN** both inserts SHALL succeed

### Requirement: system_info singleton enables /healthz

`system_info` SHALL be created with `id INTEGER PRIMARY KEY DEFAULT 1`,
`migrated_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `seed_version TEXT
NULL`, and a check constraint `CHECK (id = 1)`. The migration SHALL
insert exactly one row.

#### Scenario: Second row is rejected
- **WHEN** an `INSERT INTO system_info (id) VALUES (2)` is attempted
- **THEN** the insert SHALL fail because of the singleton check constraint

#### Scenario: Row exists after migrate
- **WHEN** `SELECT COUNT(*) FROM system_info` is run after `alembic
  upgrade head`
- **THEN** the count SHALL be exactly `1`

### Requirement: downgrade is reversible

`alembic downgrade -1` from `0001_shared_kernel` SHALL drop all six
tables created by the upgrade and SHALL drop the partial index, leaving
the database empty of project-owned objects.

#### Scenario: Downgrade clears the schema
- **WHEN** `alembic upgrade head` is followed by `alembic downgrade -1`
- **THEN** none of `tenants`, `users`, `outbox`, `processed_events`,
  `idempotency_keys`, `system_info`, `idx_outbox_unpublished` SHALL
  remain in the schema

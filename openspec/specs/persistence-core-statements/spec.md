# persistence-core-statements Specification

## Purpose

Persistence adapters build business-table statements from shared SQLAlchemy Core `Table` metadata via the statement builder — no raw SQL strings, no ORM mapping. Domain hydration stays manual and the metadata is verified against the Alembic-migrated schema.

## Requirements

### Requirement: Business-table statements are built from Core Table metadata

Persistence adapters SHALL build every SELECT/INSERT/UPDATE against business
tables (`tenants`, `tenant_members`, `invitations`, `users`,
`auth_local_users`, `auth_local_refresh_tokens`, `outbox`,
`role_permissions`) using the SQLAlchemy Core statement builder over shared
`Table` metadata. Raw SQL strings via `text()` MUST NOT be used for
business-table statements in adapters, inbound middleware, or bootstrap
dependencies. `text()` remains permitted only for session GUC statements
(`set_config`), health probes, and test utilities.

#### Scenario: Repository query round-trips through builder statements

- **WHEN** `MembershipRepositorySqlAlchemy.find(user_id=..., tenant_id=...)`
  executes inside a Unit of Work
- **THEN** the emitted statement SHALL be a single parameterized SELECT
  produced from the `tenant_members` Table metadata, and the returned value
  SHALL be a hydrated `Membership` domain object

#### Scenario: Adapter sources contain no business-table text() statements

- **WHEN** the persistence adapters, tenant middleware, and bootstrap
  dependencies are audited for `text(` usage
- **THEN** the only matches SHALL be `set_config` GUC statements and health
  probe queries, with no `nosemgrep: avoid-sqlalchemy-text` suppressions
  remaining in adapter files

### Requirement: Each business table is modeled exactly once

Every business table SHALL have exactly one `Table` definition, attached to
the single shared `MetaData` registry. Tables created by shared-kernel
migrations (`users`, `tenants`, `outbox`, `role_permissions`) SHALL be
defined in the shared kernel; context-owned tables SHALL be defined in that
context's persistence package. A bounded context MUST NOT import table
metadata from another bounded context.

#### Scenario: Cross-context join uses shared-kernel metadata

- **WHEN** the tenants context builds its members page query joining
  `tenant_members` with `users`
- **THEN** the `users` Table SHALL be imported from the shared kernel, not
  from the identity context

### Requirement: Table metadata matches the migrated schema

The Core `Table` metadata SHALL stay consistent with the schema produced by
the hand-written Alembic migrations. An automated integration test SHALL
compare the metadata against a freshly migrated database and fail on any
column-level drift for modeled tables. Alembic SHALL continue to run with
hand-written revisions only (no autogenerate).

#### Scenario: Consistency test passes on a migrated database

- **WHEN** all Alembic migrations are applied to a fresh database and the
  consistency test compares the shared metadata against it
- **THEN** the comparison SHALL report no missing tables, no missing or
  extra columns, and no type mismatches for the modeled tables

#### Scenario: Drift is detected

- **WHEN** a future migration alters a modeled business table without a
  matching update to its `Table` definition
- **THEN** the consistency test SHALL fail identifying the drifted table and
  column

### Requirement: Dynamic member-list queries compose expressions instead of strings

`MembershipRepository.list_page` SHALL build its dynamic WHERE, ORDER BY,
and IN-list filters as composed Core column expressions. Sort keys SHALL map
to `Column` objects through a fixed dictionary, list filters SHALL use
`Column.in_()`, and the search term SHALL reach the database only as a bound
parameter with `%`, `_`, and `\` escaped under an explicit LIKE ESCAPE
clause. No user-derived value SHALL be interpolated into SQL.

#### Scenario: Wildcard search input stays literal

- **WHEN** `list_page` runs with search term `100%`
- **THEN** only members whose display name, email, or user id contain the
  literal substring `100%` SHALL match, and members not containing it SHALL
  be excluded

#### Scenario: Role and status filters expand safely

- **WHEN** `list_page` runs with two roles and one status selected
- **THEN** the emitted SELECT and COUNT statements SHALL filter via
  parameterized IN clauses and return only matching members with a correct
  total

### Requirement: Domain objects remain free of persistence instrumentation

Repositories SHALL continue to hydrate domain objects manually from result
rows. Domain classes MUST NOT be mapped to tables (no declarative base, no
imperative `map_imperatively`), and returned domain objects MUST NOT carry
SQLAlchemy instrumentation state.

#### Scenario: Hydrated aggregate is a plain domain object

- **WHEN** a repository returns a `Membership`, `Tenant`, `Invitation`, or
  `User`
- **THEN** the object SHALL be constructed via the domain `hydrate`
  factory and SHALL have no `_sa_instance_state` attribute

### Requirement: Statement-count guarantees are preserved

The migration to builder statements SHALL NOT change how many statements an
adapter method emits. Existing query-count gates SHALL keep passing
unchanged.

#### Scenario: Tenant-picker query stays a single JOIN

- **WHEN** `list_active_with_tenant_for_user` runs under
  `assert_query_count(max_queries=1)`
- **THEN** the test SHALL pass with one JOIN statement, as before the
  migration

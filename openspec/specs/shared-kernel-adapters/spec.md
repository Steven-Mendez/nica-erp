# shared-kernel-adapters Specification

## Purpose
TBD - created by archiving change add-backend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: SqlAlchemyUnitOfWork honours commit and rollback semantics

`SqlAlchemyUnitOfWork(session_factory)` SHALL implement `UnitOfWork` over
SQLAlchemy's async session. `begin()` SHALL open an `AsyncSession`,
start a transaction via `session.begin()`, yield the session, and on a
clean exit commit the transaction; on an unhandled exception inside the
`async with` block, the transaction SHALL roll back and the exception
SHALL propagate. The session MUST be closed in every code path.

#### Scenario: Clean exit commits
- **WHEN** code inside `async with uow.begin() as session:` runs a
  `SELECT 1` and exits normally
- **THEN** the transaction SHALL be committed and the query result SHALL
  be available outside the block

#### Scenario: Exception rolls back
- **WHEN** code inside `async with uow.begin() as session:` performs a
  DDL operation and then raises
- **THEN** the DDL operation SHALL be rolled back and the exception SHALL
  propagate to the caller

### Requirement: Active session exposed for collaborating adapters

`SqlAlchemyUnitOfWork.current_session` SHALL return the active
`AsyncSession` while inside a `begin()` block, and SHALL raise
`RuntimeError` when accessed outside one. This allows request-scoped
adapters (notably `OutboxWriterSqlAlchemy`) to join the same transaction
without re-injecting the session.

#### Scenario: Access outside begin raises
- **WHEN** `current_session` is read on a fresh UoW that has never
  entered `begin()`
- **THEN** a `RuntimeError` SHALL be raised

### Requirement: OutboxWriterSqlAlchemy joins the active UoW session

`OutboxWriterSqlAlchemy(uow)` SHALL implement `OutboxWriter.append()` by
executing an `INSERT INTO outbox (...)` statement on
`uow.current_session`. The `payload` argument SHALL be serialized to
JSON and cast to `jsonb` in the statement. The row SHALL persist only if
the surrounding transaction commits.

#### Scenario: Append uses the UoW session
- **WHEN** `append(...)` is called inside `async with uow.begin():`
- **THEN** the `INSERT` SHALL execute on the same session and SHALL be
  visible inside the block before commit

#### Scenario: Payload stored as JSONB
- **WHEN** an `append()` call passes `payload={"k":"v"}`
- **THEN** the persisted column value SHALL be a JSONB object that
  round-trips to the same dict

### Requirement: Request-scoped tenant and current-user context

`TenantContext` and `CurrentUserContext` SHALL expose `get()`, `set(...)`,
and `clear()` static methods backed by `contextvars.ContextVar`s. Each
context SHALL default to `None`. `CurrentUser` SHALL carry at least
`user_id: UUID` and `email: str`. The context variables MUST be defined
at module scope so that they are isolated per asyncio task.

#### Scenario: Default values are None
- **WHEN** `TenantContext.get()` or `CurrentUserContext.get()` is called
  before any `set()` in the current task
- **THEN** both calls SHALL return `None`

#### Scenario: Set then clear restores None
- **WHEN** code calls `TenantContext.set(uuid4())` and then
  `TenantContext.clear()`
- **THEN** the next `TenantContext.get()` in the same task SHALL return
  `None`


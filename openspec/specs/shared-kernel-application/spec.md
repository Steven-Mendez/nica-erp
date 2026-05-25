# shared-kernel-application Specification

## Purpose
TBD - created by archiving change add-backend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: UnitOfWork transactional boundary

`shared_kernel.application.unit_of_work.UnitOfWork` SHALL be a
`typing.Protocol` exposing an async-context-manager `begin()` that yields
a `sqlalchemy.ext.asyncio.AsyncSession`, plus `commit()` and `rollback()`
coroutines. Implementations SHALL commit the transaction on a clean exit
from `begin()` and roll it back on an unhandled exception.

#### Scenario: Protocol satisfies runtime isinstance
- **WHEN** any concrete UoW implementing `begin`, `commit`, `rollback`
  is checked against `isinstance(obj, UnitOfWork)`
- **THEN** the check SHALL return true (the Protocol is
  `@runtime_checkable`)

### Requirement: Command and Query markers

`Command` and `Query` SHALL be slot-only marker classes that concrete
CQRS messages subclass through `@dataclass(frozen=True)`. They MUST NOT
declare any payload fields themselves.

#### Scenario: Subclassing produces a frozen, slotted dataclass
- **WHEN** a developer declares `@dataclass(frozen=True) class
  CreateInvoice(Command)`
- **THEN** instances of `CreateInvoice` SHALL be immutable and inherit
  the `Command` marker

### Requirement: In-process EventBus for intra-context domain events

`EventBus` SHALL be a `typing.Protocol` with `subscribe(event_type,
handler)` and `publish(event)`. `InProcessEventBus` SHALL provide a
synchronous, single-process implementation: `publish(event)` calls every
handler registered for `type(event)`, in subscription order, on the
calling thread.

#### Scenario: Handler runs when its event type is published
- **WHEN** a handler is subscribed to `OrderPlaced` and an `OrderPlaced`
  is published
- **THEN** the handler SHALL be invoked exactly once with that event

#### Scenario: Inter-context events MUST NOT travel through EventBus
- **WHEN** a context wants to emit an event consumed by another context
- **THEN** the system SHALL require that event to be appended to the
  outbox instead of published on `InProcessEventBus`

### Requirement: OutboxWriter port for atomic event publication

`OutboxWriter` SHALL be a `typing.Protocol` exposing
`append(*, event_id, event_type, event_version, aggregate_type,
aggregate_id, tenant_id, payload, correlation_id=None)`. All arguments
SHALL be keyword-only. The concrete implementation MUST write the row
inside the same database transaction as the aggregate change so that the
row and the aggregate either both commit or both roll back.

#### Scenario: Append signature is keyword-only
- **WHEN** a caller tries to invoke `append` with positional arguments
- **THEN** Python SHALL raise `TypeError`

#### Scenario: Outbox row commits atomically with the aggregate
- **WHEN** an aggregate change and an `append()` happen inside the same
  `UnitOfWork.begin()` block and an exception is raised before exit
- **THEN** neither the aggregate change nor the outbox row SHALL be
  visible after rollback


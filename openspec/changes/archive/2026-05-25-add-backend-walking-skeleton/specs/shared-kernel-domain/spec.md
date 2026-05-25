## ADDED Requirements

### Requirement: Identity-based Entity equality

`Entity[IdT]` SHALL define equality and hashing by the identifier alone,
ignoring all other attributes. Two `Entity` instances of the same concrete
type with the same `id` SHALL compare equal; two instances of different
concrete types MUST NOT compare equal even if their ids match.

#### Scenario: Same type, same id compare equal
- **WHEN** two `Entity` subclasses of the same class are created with the
  same identifier
- **THEN** they SHALL compare equal under `==` and produce the same hash

#### Scenario: Different types never compare equal
- **WHEN** an `Entity` subclass `A` and an `Entity` subclass `B` share an
  identifier value
- **THEN** they SHALL NOT compare equal under `==`

### Requirement: AggregateRoot collects and releases domain events

`AggregateRoot[IdT]` SHALL extend `Entity` with an internal event buffer.
The aggregate SHALL expose `pull_events()` that returns the recorded events
and atomically empties the buffer. The buffer MUST start empty.

#### Scenario: pull_events returns recorded events and empties the buffer
- **WHEN** an aggregate records two `DomainEvent`s and then `pull_events()`
  is called
- **THEN** the call SHALL return the two events in insertion order, and a
  subsequent call SHALL return an empty list

### Requirement: DomainEvent immutability and auto-populated metadata

`DomainEvent` SHALL be a frozen, kw-only dataclass. Every concrete event
SHALL inherit `event_id: UUID` (default-factory UUIDv4) and
`occurred_at: datetime` (default-factory `datetime.now(tz=UTC)`).
Attempting to mutate a `DomainEvent` field after construction MUST raise.

#### Scenario: Default event_id and occurred_at are populated
- **WHEN** a concrete `DomainEvent` subclass is instantiated without
  passing `event_id` or `occurred_at`
- **THEN** `event_id` SHALL be a `uuid.UUID` and `occurred_at` SHALL be a
  timezone-aware `datetime` in UTC

#### Scenario: Events are immutable
- **WHEN** code attempts to reassign any attribute on an existing event
- **THEN** the assignment SHALL raise an error

### Requirement: ValueObject marker

`ValueObject` SHALL be a marker base class with no instance fields, so that
concrete value objects declared with `@dataclass(frozen=True)` can inherit
from it. Adapters and type-checkers MAY use `isinstance(x, ValueObject)`
to recognise value objects.

#### Scenario: Money is a ValueObject
- **WHEN** a `Money` instance is created
- **THEN** `isinstance(money, ValueObject)` SHALL be true

### Requirement: Money value object with currency-safe arithmetic

`Money(amount: Decimal, currency: str)` SHALL coerce non-`Decimal` amounts
by `Decimal(str(value))`. The `currency` SHALL be a 3-letter uppercase
ISO code; any other shape MUST raise `ValueError`. `Money + Money` and
`Money - Money` SHALL succeed only when both operands share the same
currency, otherwise SHALL raise `CurrencyMismatchError` (a `ValueError`
subclass). Subtraction MAY produce a negative amount. Unary negation SHALL
preserve the currency.

#### Scenario: Same-currency addition
- **WHEN** `Money(Decimal("10.00"), "NIO") + Money(Decimal("2.50"), "NIO")`
  is evaluated
- **THEN** the result SHALL equal `Money(Decimal("12.50"), "NIO")`

#### Scenario: Mixed-currency arithmetic rejected
- **WHEN** `Money(_, "NIO")` is added to `Money(_, "USD")`
- **THEN** a `CurrencyMismatchError` SHALL be raised

#### Scenario: Subtraction can go negative
- **WHEN** `Money(Decimal("1.00"), "NIO") - Money(Decimal("3.00"), "NIO")`
  is evaluated
- **THEN** the result SHALL equal `Money(Decimal("-2.00"), "NIO")`

#### Scenario: Currency must be a 3-letter uppercase code
- **WHEN** `Money` is constructed with `currency="nio"` or `"NIOO"`
- **THEN** a `ValueError` SHALL be raised at construction time

#### Scenario: Equality by structural value
- **WHEN** two `Money` instances with the same `amount` and `currency`
  are compared
- **THEN** they SHALL compare equal under `==`

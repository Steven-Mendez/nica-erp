## MODIFIED Requirements

### Requirement: `User` aggregate SHALL expose nullable profile fields

The `User` aggregate in `apps/api/src/contexts/identity/domain/user.py` SHALL declare `display_name: str | None`, `locale: str | None`, and `timezone: str | None`. The constructor SHALL accept `None` for any of the three fields. The `update_profile(...)` method SHALL accept partial updates with `None` left untouched.

#### Scenario: Constructing a User with NULL profile fields succeeds

- **WHEN** `User(id=…, external_sub=…, email=…, display_name=None, locale=None, timezone=None)` is called
- **THEN** the resulting aggregate SHALL have all three fields equal to `None`

#### Scenario: `update_profile` setting only `display_name` leaves the others NULL

- **GIVEN** a `User` with `display_name=None`, `locale=None`, `timezone=None`
- **WHEN** `user.update_profile(display_name="Ada", locale=None, timezone=None)` is called
- **THEN** `user.display_name` SHALL equal `"Ada"` and the other two fields SHALL remain `None`

### Requirement: User repository SHALL roundtrip NULL profile fields

The SQLAlchemy `UserRepository` adapter SHALL persist and retrieve `display_name`, `locale`, and `timezone` as nullable columns. `INSERT` SHALL accept `None`; `SELECT` SHALL return `None` for NULL values; `UPDATE` SHALL allow setting any of the three to `None`.

#### Scenario: Inserting a user with NULL profile fields

- **WHEN** the repository's `add(user)` is invoked with a `User` whose profile fields are all `None`
- **THEN** the `users` row SHALL contain `display_name IS NULL`, `locale IS NULL`, `timezone IS NULL` in the database

#### Scenario: Reading a user with NULL profile fields

- **GIVEN** a `users` row with `display_name IS NULL`
- **WHEN** the repository's `get_by_external_sub(...)` is invoked
- **THEN** the returned `User.display_name` SHALL be `None`

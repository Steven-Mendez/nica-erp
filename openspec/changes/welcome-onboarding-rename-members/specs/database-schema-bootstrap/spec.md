## MODIFIED Requirements

### Requirement: Migration 0004 SHALL drop NOT NULL and defaults on user profile fields

Alembic migration `0004_drop_user_profile_defaults` SHALL alter the `users` table by dropping the `NOT NULL` constraint AND the `server_default` clause on each of `display_name`, `locale`, and `timezone`. The migration SHALL be reversible. The `upgrade()` body SHALL touch column metadata only; existing row values SHALL be preserved unchanged.

The `downgrade()` body SHALL re-attach the original defaults (`''`, `'es-NI'`, `'America/Managua'` respectively) AND back-fill any NULL values to those defaults before re-applying `NOT NULL`, so a downgrade against a populated, post-3.6 database does not violate the constraint.

#### Scenario: After upgrade, NULL inserts succeed

- **GIVEN** an empty `users` table after migration 0004 has run
- **WHEN** `INSERT INTO users (id, external_sub, email, display_name, locale, timezone) VALUES (gen_random_uuid(), 'sub', 'a@test.dev', NULL, NULL, NULL)` is executed
- **THEN** the row SHALL be inserted with all three columns NULL

#### Scenario: Downgrade back-fills NULL rows before re-applying NOT NULL

- **GIVEN** a `users` table with one row whose `display_name` is NULL
- **WHEN** `alembic downgrade 0003` is executed
- **THEN** the row SHALL afterward have `display_name=''`, `locale='es-NI'`, `timezone='America/Managua'`, and the columns SHALL be NOT NULL again

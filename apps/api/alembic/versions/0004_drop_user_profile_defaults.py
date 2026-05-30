"""drop NOT NULL and defaults on users profile fields

Revision ID: 0004_drop_user_profile_defaults
Revises: 0003_tenants_and_rbac
Create Date: 2026-05-27

Sprint 3.6 captures `display_name` and `timezone` on a `/welcome`
screen at first login instead of assuming the Nicaragua-centric
defaults sprint 02 hard-coded. `locale` is kept in the schema but
deferred from the UI per the future i18n sprint.

`upgrade()` only changes column metadata; existing row values stay
untouched. `downgrade()` is reversible: it back-fills any NULL rows
with the previous defaults before re-applying NOT NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_drop_user_profile_defaults"
down_revision: str | None = "0003_tenants_and_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN display_name DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN display_name DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN locale DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN locale DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN timezone DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN timezone DROP DEFAULT")


def downgrade() -> None:
    # Back-fill NULLs with the previous defaults before re-applying NOT
    # NULL — otherwise the constraint would be violated by any row that
    # was set to NULL while running on sprint 3.6.
    op.execute("UPDATE users SET display_name = '' WHERE display_name IS NULL")
    op.execute("UPDATE users SET locale = 'es-NI' WHERE locale IS NULL")
    op.execute("UPDATE users SET timezone = 'America/Managua' WHERE timezone IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN display_name SET DEFAULT ''")
    op.execute("ALTER TABLE users ALTER COLUMN display_name SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN locale SET DEFAULT 'es-NI'")
    op.execute("ALTER TABLE users ALTER COLUMN locale SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN timezone SET DEFAULT 'America/Managua'")
    op.execute("ALTER TABLE users ALTER COLUMN timezone SET NOT NULL")

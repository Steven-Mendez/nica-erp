"""identity: auth_local_refresh_tokens jti ledger

Revision ID: 0007_auth_local_refresh_tokens
Revises: 0006_tenants_fiscal_contact
Create Date: 2026-06-03

Audit F-005 / F-011 / F-016: stateless refresh tokens combined with the
JWT verifier accepting any signed token made one XSS payload sufficient
for a 30-day account takeover. This migration introduces a server-side
``jti`` ledger so refresh tokens can be revoked at logout and rejected
on every subsequent ``/v1/auth/refresh``.

Columns:
  - ``jti`` UUID primary key (matches the JWT ``jti`` claim minted by
    the local IdP)
  - ``user_id`` UUID — the ``auth_local_users.id`` the token was
    issued to (no FK, mirroring the rest of the local-auth schema
    which deliberately avoids cross-schema constraints)
  - ``issued_at`` TIMESTAMPTZ
  - ``revoked_at`` TIMESTAMPTZ NULL — set on logout
  - ``user_agent`` TEXT NULL — best-effort audit trail
  - ``ip`` TEXT NULL — best-effort audit trail

Index ``(user_id, revoked_at)`` accelerates the "is this jti live?"
lookup on the refresh hot path and supports a future "revoke all my
sessions" admin tool.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_auth_local_refresh_tokens"
down_revision: str | None = "0006_tenants_fiscal_contact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_local_refresh_tokens",
        sa.Column("jti", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_auth_local_refresh_tokens_user_revoked",
        "auth_local_refresh_tokens",
        ["user_id", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_local_refresh_tokens_user_revoked",
        table_name="auth_local_refresh_tokens",
    )
    op.drop_table("auth_local_refresh_tokens")

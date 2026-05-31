"""add (tenant_id, joined_at) index on tenant_members

Revision ID: 0005_tenant_members_lookup_index
Revises: 0004_drop_user_profile_defaults
Create Date: 2026-05-31

The ``tenant_members`` table only had ``(user_id, tenant_id)`` as a
non-partial index (via the unique constraint). The list-members query
runs ``WHERE tenant_id = ? ORDER BY joined_at`` so it must seq-scan the
table to find the rows for one tenant — fine while every tenant has a
handful of members, but linear in total ``tenant_members`` row count and
will degrade as the platform grows.

Add a composite btree on ``(tenant_id, joined_at)`` so the query can:

  - filter on ``tenant_id`` via an index scan, and
  - return rows in ``ORDER BY joined_at`` order without a sort step.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_tenant_members_lookup_index"
down_revision: str | None = "0004_drop_user_profile_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tenant_members_tenant_id_joined_at",
        "tenant_members",
        ["tenant_id", "joined_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_members_tenant_id_joined_at", table_name="tenant_members")

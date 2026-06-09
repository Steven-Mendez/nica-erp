"""invitations lookup indexes

Revision ID: 0008_invitations_lookup_indexes
Revises: 0007_auth_local_refresh_tokens
Create Date: 2026-06-09

The ``invitations`` table only had ``idx_invitations_tenant`` on
``(tenant_id)``. Two hot queries outgrow it:

  - ``list_by_tenant`` runs ``WHERE tenant_id = ? ORDER BY created_at
    DESC`` and needs a sort step after the index scan.
  - ``list_pending_by_email`` runs ``WHERE tenant_id = ? AND
    lower(email) = lower(?) AND status = 'pending'`` and can only use
    the ``tenant_id`` prefix.

Replace ``idx_invitations_tenant`` with a composite
``(tenant_id, created_at)`` — it still serves the bare ``tenant_id``
filter (including the ``tenant_isolation`` RLS policy qual) and a
backward index scan satisfies the ``DESC`` ordering without a sort.
Add a partial expression index ``(tenant_id, lower(email))
WHERE status = 'pending'`` matching the exact predicate of the
pending-by-email lookup. ``email`` is CITEXT, but the query compares
``lower(email)`` explicitly, so the indexed expression must match it
verbatim for the planner to use it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_invitations_lookup_indexes"
down_revision: str | None = "0007_auth_local_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_invitations_tenant_id_created_at",
        "invitations",
        ["tenant_id", "created_at"],
    )
    # Expression + partial indexes are clearer as raw DDL than through
    # the op.create_index expression API.
    op.execute(
        "CREATE INDEX ix_invitations_pending_tenant_lower_email "
        "ON invitations (tenant_id, lower(email)) WHERE status = 'pending'"
    )
    op.execute("DROP INDEX idx_invitations_tenant")


def downgrade() -> None:
    op.execute("CREATE INDEX idx_invitations_tenant ON invitations (tenant_id)")
    op.execute("DROP INDEX ix_invitations_pending_tenant_lower_email")
    op.drop_index("ix_invitations_tenant_id_created_at", table_name="invitations")

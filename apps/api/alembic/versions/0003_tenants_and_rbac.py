"""tenants + RLS + RBAC catalog

Revision ID: 0003_tenants_and_rbac
Revises: 0002_identity
Create Date: 2026-05-27

Expands the `tenants` placeholder from migration 0001 with fiscal
metadata; creates `tenant_members` with the special "self-OR-tenant"
RLS policy and the partial unique single-owner index; creates
`invitations` with the canonical per-tenant RLS policy; creates
`permissions` and `role_permissions` (global, no RLS) and seeds them
from `shared_kernel.permissions.catalog`.

`outbox`, `processed_events`, and `idempotency_keys` remain without
RLS by design — the publisher is a system process that reads across
tenants. The DB role separation between the application and the
publisher provides the isolation, not a policy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tenants_and_rbac"
down_revision: str | None = "0002_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------------- tenants
    op.add_column("tenants", sa.Column("ruc", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("regime", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("municipality", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("authorization_dgi_number", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("authorization_dgi_valid_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("authorization_dgi_valid_to", sa.Date(), nullable=True),
    )
    op.add_column("tenants", sa.Column("fiscal_address", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "is_withholder",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "ALTER TABLE tenants ADD CONSTRAINT ck_tenants_regime "
        "CHECK (regime IN ('general','simplified') OR regime IS NULL)"
    )
    op.execute(
        "ALTER TABLE tenants ADD CONSTRAINT ck_tenants_status "
        "CHECK (status IN ('provisioning','active','suspended','purged'))"
    )
    op.create_unique_constraint("uq_tenants_ruc", "tenants", ["ruc"])

    # ---------------------------------------------------------- tenant_members
    op.create_table(
        "tenant_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("removed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_tenant_members_user_tenant"),
    )
    op.execute(
        "ALTER TABLE tenant_members ADD CONSTRAINT ck_tenant_members_role "
        "CHECK (role IN ('owner','admin','accountant','salesperson','viewer'))"
    )
    op.execute(
        "ALTER TABLE tenant_members ADD CONSTRAINT ck_tenant_members_status "
        "CHECK (status IN ('active','removed'))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tenant_members_owner "
        "ON tenant_members(tenant_id) WHERE role='owner' AND status='active'"
    )
    op.execute("ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_members FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_members_self ON tenant_members "
        "USING ("
        "  user_id = current_setting('app.current_user_id', true)::uuid "
        "  OR tenant_id = current_setting('app.tenant_id', true)::uuid"
        ") "
        "WITH CHECK ("
        "  tenant_id = current_setting('app.tenant_id', true)::uuid"
        ")"
    )

    # ------------------------------------------------------------- invitations
    op.create_table(
        "invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("proposed_role", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "ALTER TABLE invitations ADD CONSTRAINT ck_invitations_role "
        "CHECK (proposed_role IN ('admin','accountant','salesperson','viewer'))"
    )
    op.execute(
        "ALTER TABLE invitations ADD CONSTRAINT ck_invitations_status "
        "CHECK (status IN ('pending','accepted','cancelled','expired'))"
    )
    op.execute("CREATE INDEX idx_invitations_tenant ON invitations(tenant_id)")
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON invitations "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    )

    # ----------------------------------------------- permissions / role_perms
    op.create_table(
        "permissions",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.execute(
        "ALTER TABLE permissions ADD CONSTRAINT ck_permissions_scope "
        "CHECK (scope IN ('own','all','na'))"
    )

    op.create_table(
        "role_permissions",
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "permission",
            sa.Text(),
            sa.ForeignKey("permissions.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role", "permission"),
    )
    op.execute(
        "ALTER TABLE role_permissions ADD CONSTRAINT ck_role_permissions_role "
        "CHECK (role IN ('viewer','salesperson','accountant','admin','owner'))"
    )

    # Seed from the Python catalog (source of truth). Sprints 04-08 will add
    # their own seed blocks using the same ON CONFLICT DO NOTHING idiom.
    from shared_kernel.permissions.catalog import (
        DEFAULT_ROLE_PERMISSIONS,
        TENANT_PERMISSIONS,
    )

    bind = op.get_bind()
    perm_count = 0
    for perm in TENANT_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (code, resource, action, scope, description) "
                "VALUES (:code, :resource, :action, :scope, :description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "code": perm.code,
                "resource": perm.resource,
                "action": perm.action,
                "scope": perm.scope,
                "description": perm.description,
            },
        )
        perm_count += 1

    rp_count = 0
    for role, codes in DEFAULT_ROLE_PERMISSIONS.items():
        for code in codes:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role, permission) "
                    "VALUES (:role, :permission) "
                    "ON CONFLICT (role, permission) DO NOTHING"
                ),
                {"role": role, "permission": code},
            )
            rp_count += 1

    print(f"[migration 0003] permissions seeded: {perm_count}")
    print(f"[migration 0003] role_permissions seeded: {rp_count}")


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invitations")
    op.drop_table("invitations")
    op.execute("DROP POLICY IF EXISTS tenant_members_self ON tenant_members")
    op.execute("DROP INDEX IF EXISTS uq_tenant_members_owner")
    op.drop_table("tenant_members")
    op.drop_constraint("uq_tenants_ruc", "tenants", type_="unique")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_status")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_regime")
    op.drop_column("tenants", "updated_at")
    op.drop_column("tenants", "status")
    op.drop_column("tenants", "is_withholder")
    op.drop_column("tenants", "fiscal_address")
    op.drop_column("tenants", "authorization_dgi_valid_to")
    op.drop_column("tenants", "authorization_dgi_valid_from")
    op.drop_column("tenants", "authorization_dgi_number")
    op.drop_column("tenants", "municipality")
    op.drop_column("tenants", "regime")
    op.drop_column("tenants", "ruc")

"""tenants: departamento + fiscal_email + fiscal_phone + tri-valent regime

Revision ID: 0006_tenants_fiscal_contact
Revises: 0005_tenant_members_lookup_index
Create Date: 2026-06-02

Adds the fields the ``/empresa/settings`` editor writes that did not
exist in the 0003 baseline:

  - ``departamento`` TEXT (the Nicaraguan department, distinct from the
    ``municipality`` column which holds the municipio)
  - ``fiscal_email`` TEXT (RFC-5321 lite email, ≤ 320 chars)
  - ``fiscal_phone`` TEXT (the ``+505 NNNN-NNNN`` canonical shape)

Also widens the ``ck_tenants_regime`` CHECK constraint from
``{general, simplified}`` to ``{general, cuota_fija, pequeno_contribuyente}``
so the three Nicaraguan tax regimes are representable. Existing rows
keep their value — ``simplified`` is not in the new set, so the
upgrade rewrites any prior ``simplified`` rows to ``cuota_fija`` (the
closest Nicaraguan equivalent) before swapping the constraint. The
downgrade reverses the rename.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_tenants_fiscal_contact"
down_revision: str | None = "0005_tenant_members_lookup_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- New columns -------------------------------------------------
    op.add_column("tenants", sa.Column("departamento", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("fiscal_email", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("fiscal_phone", sa.Text(), nullable=True))

    # ---- Widen the regime CHECK constraint ---------------------------
    # Rewrite any pre-existing ``simplified`` rows to ``cuota_fija`` (the
    # closest Nicaraguan equivalent). In a fresh-install timeline this
    # is a no-op because the editor was wired up before the first
    # ``simplified`` row landed.
    op.execute("UPDATE tenants SET regime = 'cuota_fija' WHERE regime = 'simplified'")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_regime")
    op.execute(
        "ALTER TABLE tenants ADD CONSTRAINT ck_tenants_regime "
        "CHECK (regime IN ('general','cuota_fija','pequeno_contribuyente') OR regime IS NULL)"
    )


def downgrade() -> None:
    # Reverse the constraint widening first so rows that were rewritten
    # on upgrade map back into the old vocabulary.
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_regime")
    op.execute("UPDATE tenants SET regime = 'simplified' WHERE regime = 'cuota_fija'")
    op.execute("UPDATE tenants SET regime = NULL WHERE regime = 'pequeno_contribuyente'")
    op.execute(
        "ALTER TABLE tenants ADD CONSTRAINT ck_tenants_regime "
        "CHECK (regime IN ('general','simplified') OR regime IS NULL)"
    )
    op.drop_column("tenants", "fiscal_phone")
    op.drop_column("tenants", "fiscal_email")
    op.drop_column("tenants", "departamento")

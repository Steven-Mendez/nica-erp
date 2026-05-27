"""identity: expand users + auth_local_users (local only)

Revision ID: 0002_identity
Revises: 0001_shared_kernel
Create Date: 2026-05-26

Expands the `users` placeholder added by 0001 with the profile/preferences
columns the identity context needs, and conditionally creates
`auth_local_users` (the local-only password ledger) when `APP_ENV=local`.

`auth_local_users` is never created in AWS — Cognito owns local-auth state
there. The Python branch on `APP_ENV` is deliberate: identical to the
deploy-time wiring choice and easy to inspect via stdout during migration.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity"
down_revision: str | None = "0001_shared_kernel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 already enables citext; re-asserting is idempotent and keeps this
    # migration self-contained per the identity-context spec.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.add_column(
        "users",
        sa.Column("external_sub", sa.Text(), nullable=False),
    )
    op.create_unique_constraint("uq_users_external_sub", "users", ["external_sub"])
    op.add_column(
        "users",
        sa.Column("display_name", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'es-NI'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'America/Managua'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # `created_at` is already present from 0001; `updated_at` is added here
    # so the identity aggregate can round-trip its mutate-on-profile-edit
    # timestamp through the `users` table without a follow-up migration.
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    app_env = os.environ.get("APP_ENV", "")
    branch = "local" if app_env == "local" else "aws"
    print(f"[migration 0002] APP_ENV={app_env!r} branch: {branch}")

    if app_env == "local":
        op.create_table(
            "auth_local_users",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
            sa.Column("verification_code_hash", sa.Text(), nullable=True),
            sa.Column(
                "verification_code_expires_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "verification_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "verification_attempts_reset_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "attributes",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("last_resend_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_local_users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "preferences")
    op.drop_column("users", "timezone")
    op.drop_column("users", "locale")
    op.drop_column("users", "display_name")
    op.drop_constraint("uq_users_external_sub", "users", type_="unique")
    op.drop_column("users", "external_sub")
    # `citext` stays — 0001 created it and other tables depend on it.

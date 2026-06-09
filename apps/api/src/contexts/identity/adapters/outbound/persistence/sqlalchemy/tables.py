"""Core ``Table`` metadata for identity-context-owned tables.

Attached to the shared-kernel ``MetaData`` registry. Columns, types,
nullability, and primary keys only — constraints, indexes, and server
defaults live in the hand-written Alembic migrations.

``auth_local_users`` exists only when the database was migrated with
``APP_ENV=local``; in AWS, Cognito owns that state and the table is
never created. The metadata still models it unconditionally — the
local IdP adapter is the only consumer.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, Table, Text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TIMESTAMP, UUID

from shared_kernel.adapters.tables import metadata

auth_local_users = Table(
    "auth_local_users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", CITEXT(), nullable=False),
    Column("password_hash", Text(), nullable=False),
    Column("email_verified", Boolean(), nullable=False),
    Column("verification_code_hash", Text(), nullable=True),
    Column("verification_code_expires_at", TIMESTAMP(timezone=True), nullable=True),
    Column("verification_attempts", Integer(), nullable=False),
    Column("verification_attempts_reset_at", TIMESTAMP(timezone=True), nullable=True),
    Column("attributes", JSONB(), nullable=False),
    Column("last_resend_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

auth_local_refresh_tokens = Table(
    "auth_local_refresh_tokens",
    metadata,
    Column("jti", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("issued_at", TIMESTAMP(timezone=True), nullable=False),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("user_agent", Text(), nullable=True),
    Column("ip", Text(), nullable=True),
)

__all__ = ["auth_local_refresh_tokens", "auth_local_users"]

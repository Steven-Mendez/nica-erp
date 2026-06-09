"""Core ``Table`` metadata for tenants-context-owned tables.

Attached to the shared-kernel ``MetaData`` registry. Columns, types,
nullability, and primary keys only — constraints, indexes, server
defaults, and the RLS policies live in the hand-written Alembic
migrations.
"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID

from shared_kernel.adapters.tables import metadata

tenant_members = Table(
    "tenant_members",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("tenant_id", UUID(as_uuid=True), nullable=False),
    Column("role", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("joined_at", TIMESTAMP(timezone=True), nullable=False),
    Column("removed_at", TIMESTAMP(timezone=True), nullable=True),
)

invitations = Table(
    "invitations",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), nullable=False),
    Column("email", CITEXT(), nullable=False),
    Column("proposed_role", Text(), nullable=False),
    Column("token_hash", Text(), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("status", Text(), nullable=False),
    Column("cancelled_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

__all__ = ["invitations", "tenant_members"]

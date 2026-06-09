"""Core ``Table`` metadata for shared-kernel-owned tables.

Single shared ``MetaData`` registry: every business table the adapters
build statements against attaches here (context-owned tables register
from their own ``tables.py`` modules). The metadata models columns,
types, nullability, and primary keys only — constraints, indexes,
server defaults, and RLS policies live exclusively in the hand-written
Alembic migrations, which remain the source of truth for the schema.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, Integer, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TIMESTAMP, UUID

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", CITEXT(), nullable=False),
    Column("external_sub", Text(), nullable=False),
    Column("display_name", Text(), nullable=True),
    Column("locale", Text(), nullable=True),
    Column("timezone", Text(), nullable=True),
    Column("preferences", JSONB(), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

tenants = Table(
    "tenants",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", Text(), nullable=False),
    Column("ruc", Text(), nullable=True),
    Column("regime", Text(), nullable=True),
    Column("departamento", Text(), nullable=True),
    Column("municipality", Text(), nullable=True),
    Column("authorization_dgi_number", Text(), nullable=True),
    Column("authorization_dgi_valid_from", Date(), nullable=True),
    Column("authorization_dgi_valid_to", Date(), nullable=True),
    Column("fiscal_address", Text(), nullable=True),
    Column("fiscal_email", Text(), nullable=True),
    Column("fiscal_phone", Text(), nullable=True),
    Column("is_withholder", Boolean(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

outbox = Table(
    "outbox",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), nullable=False),
    Column("event_type", Text(), nullable=False),
    Column("event_version", Integer(), nullable=False),
    Column("aggregate_type", Text(), nullable=False),
    Column("aggregate_id", UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB(), nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=True),
    Column("published_at", TIMESTAMP(timezone=True), nullable=True),
    Column("publish_attempts", Integer(), nullable=False),
)

role_permissions = Table(
    "role_permissions",
    metadata,
    Column("role", Text(), primary_key=True),
    Column("permission", Text(), primary_key=True),
)

__all__ = ["metadata", "outbox", "role_permissions", "tenants", "users"]

"""Invitation token generator (HS256 JWT)."""

from __future__ import annotations

from contexts.tenants.adapters.outbound.tokens.jwt import (
    InvitationTokenGeneratorJwt,
)

__all__ = ["InvitationTokenGeneratorJwt"]

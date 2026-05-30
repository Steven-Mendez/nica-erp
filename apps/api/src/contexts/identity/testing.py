"""Test helpers for the identity context.

This module is intentionally split from the productive adapter
package so that the ``forge_jwt`` helper — which can mint a JWT for
an arbitrary ``custom:active_tenant`` regardless of real membership
— stays out of every productive import path. ``import-linter``
forbids importing this module from anything under
``contexts/*/adapters/``, ``contexts/*/application/``, or
``bootstrap/``. The tests in ``apps/api/tests/`` are the only
sanctioned consumers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt


def forge_jwt(
    *,
    user_id: UUID,
    email: str,
    active_tenant: str | UUID | None,
    secret: str,
    aud: str = "nica-erp-local",
    iss: str = "nica-erp-local-idp",
    ttl_seconds: int = 3600,
    now: datetime | None = None,
    **extra_claims: Any,
) -> str:
    """Mint an HS256 JWT byte-identical to ``IdentityProviderLocal.authenticate``.

    The returned token's claim shape is
    ``sub / email / email_verified / custom:active_tenant / aud / iss / exp / iat``.
    The ``active_tenant`` argument MAY refer to a tenant the user is
    not a member of — the helper deliberately performs no membership
    check; that is the job of ``TenantMiddleware``.
    """

    issued_at = now if now is not None else datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    claim_tenant: str
    if active_tenant is None:
        claim_tenant = ""
    elif isinstance(active_tenant, UUID):
        claim_tenant = str(active_tenant)
    else:
        claim_tenant = active_tenant
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "email_verified": True,
        "custom:active_tenant": claim_tenant,
        "aud": aud,
        "iss": iss,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        **extra_claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


__all__ = ["forge_jwt"]

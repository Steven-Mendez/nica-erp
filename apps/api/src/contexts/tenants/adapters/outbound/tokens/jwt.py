"""``InvitationTokenGeneratorJwt`` — HS256 invitation tokens.

The signing key is the local-IdP secret (``LOCAL_JWT_SECRET``). The
token carries ``{tenant_id, email, role, exp, iat, iss, sub}`` and
is signed HS256. The SHA-256 hash of the *encoded* token is stored
in ``invitations.token_hash`` — the plaintext only travels via
email.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import jwt

from contexts.tenants.application.ports.outbound import (
    InvitationTokenClaims,
    InvitationTokenIssued,
)
from contexts.tenants.domain import Role

_AUD = "nica-erp-invitations"
_ISS = "nica-erp"


@dataclass(slots=True)
class InvitationTokenGeneratorJwt:
    secret: str
    ttl_seconds: int

    def mint(
        self,
        *,
        tenant_id: UUID,
        email: str,
        proposed_role: Role,
        now: datetime,
    ) -> InvitationTokenIssued:
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        # ``jti`` makes two invitations with identical
        # ``(tenant_id, email, role, iat)`` produce different encoded
        # tokens (and therefore different ``token_hash`` values), so
        # the ``invitations.token_hash`` UNIQUE constraint cannot fire
        # when an operator cancels and re-invites within the same
        # second.
        payload = {
            "iss": _ISS,
            "aud": _AUD,
            "sub": email.lower(),
            "tenant_id": str(tenant_id),
            "role": proposed_role.value,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid4()),
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return InvitationTokenIssued(
            token=token, token_hash=self.hash(token=token), expires_at=expires_at
        )

    def verify(self, *, token: str) -> InvitationTokenClaims:
        decoded = jwt.decode(token, self.secret, algorithms=["HS256"], audience=_AUD)
        return InvitationTokenClaims(
            tenant_id=UUID(decoded["tenant_id"]),
            email=decoded["sub"],
            proposed_role=Role(decoded["role"]),
            expires_at=datetime.fromtimestamp(decoded["exp"]),
        )

    def hash(self, *, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = ["InvitationTokenGeneratorJwt"]

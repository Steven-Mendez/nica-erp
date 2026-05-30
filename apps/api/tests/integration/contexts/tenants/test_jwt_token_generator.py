"""Integration tests for :class:`InvitationTokenGeneratorJwt`.

Verifies the HS256 sign/verify roundtrip, expiry handling, and
signature tampering rejection. These are integration tests because
they exercise ``pyjwt`` (no in-house crypto) — a regression in the
library's API surface or default options should be caught here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from contexts.tenants.adapters.outbound.tokens.jwt import InvitationTokenGeneratorJwt
from contexts.tenants.domain import Role


@pytest.mark.integration
def test_mint_then_verify_roundtrip() -> None:
    gen = InvitationTokenGeneratorJwt(secret="s" * 32, ttl_seconds=3600)
    tenant_id = uuid4()
    now = datetime.now(UTC)

    issued = gen.mint(
        tenant_id=tenant_id, email="x@test.dev", proposed_role=Role.ACCOUNTANT, now=now
    )

    claims = gen.verify(token=issued.token)
    assert claims.tenant_id == tenant_id
    assert claims.email == "x@test.dev"
    assert claims.proposed_role is Role.ACCOUNTANT


@pytest.mark.integration
def test_hash_is_deterministic_and_sha256() -> None:
    gen = InvitationTokenGeneratorJwt(secret="s" * 32, ttl_seconds=3600)
    h1 = gen.hash(token="abc")
    h2 = gen.hash(token="abc")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


@pytest.mark.integration
def test_verify_rejects_signature_tampering() -> None:
    gen = InvitationTokenGeneratorJwt(secret="s" * 32, ttl_seconds=3600)
    issued = gen.mint(
        tenant_id=uuid4(),
        email="x@test.dev",
        proposed_role=Role.VIEWER,
        now=datetime.now(UTC),
    )

    # Flip a payload character; signature no longer matches.
    parts = issued.token.split(".")
    tampered_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
    tampered = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    with pytest.raises(jwt.InvalidTokenError):
        gen.verify(token=tampered)


@pytest.mark.integration
def test_verify_rejects_wrong_secret() -> None:
    issuer = InvitationTokenGeneratorJwt(secret="s" * 32, ttl_seconds=3600)
    issued = issuer.mint(
        tenant_id=uuid4(),
        email="x@test.dev",
        proposed_role=Role.VIEWER,
        now=datetime.now(UTC),
    )

    verifier_with_other_secret = InvitationTokenGeneratorJwt(secret="t" * 32, ttl_seconds=3600)
    with pytest.raises(jwt.InvalidSignatureError):
        verifier_with_other_secret.verify(token=issued.token)


@pytest.mark.integration
def test_verify_rejects_expired_token() -> None:
    gen = InvitationTokenGeneratorJwt(secret="s" * 32, ttl_seconds=1)
    past = datetime.now(UTC) - timedelta(seconds=10)
    issued = gen.mint(tenant_id=uuid4(), email="x@test.dev", proposed_role=Role.VIEWER, now=past)
    with pytest.raises(jwt.ExpiredSignatureError):
        gen.verify(token=issued.token)

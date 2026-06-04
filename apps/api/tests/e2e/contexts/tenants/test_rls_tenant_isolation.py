"""End-to-end isolation gate for the tenants context.

This test materialises the merge gate declared by sprint 03
(see ``docs/sprints/03-tenants-and-rls.md`` §Critical isolation
test). Closure of sprint 03 was prematurely declared without this
gate landing on disk; sprint 3.5 (test backfill) re-introduces it
as a real, executable assertion.

Two principles are enforced:

1. **Postgres RLS isolation** — a user authenticated for tenant B
   MUST NOT observe tenant A's invitations through the public HTTP
   surface. The list response either reports the resource as
   missing or returns an empty collection; what it MUST NOT do is
   leak any row tagged with another tenant's id.
2. **Membership enforcement against forgery** — a JWT crafted off
   the LOCAL_JWT_SECRET that claims ``custom:active_tenant`` for a
   tenant the bearer is not a member of MUST be rejected by the
   tenant middleware with HTTP 403 before any handler runs.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from bootstrap.settings import get_settings
from contexts.identity.testing import forge_jwt
from tests.e2e.conftest import E2E_PASSWORD, extract_signup_code
from tests.integration.contexts.identity.conftest import RecordingEmailSender

pytestmark = pytest.mark.e2e


# --- helpers --------------------------------------------------------------


def _email_for(recorder: RecordingEmailSender, address: str) -> str:
    """Return the body of the most recent recorded email to *address*."""

    for sent in reversed(recorder.sent):
        if sent.to == address:
            return sent.text
    raise AssertionError(f"no email recorded for {address!r}")


async def _signup_confirm_login(
    client: AsyncClient, recorder: RecordingEmailSender, email: str
) -> tuple[dict[str, Any], str]:
    """Register + confirm + log in one user; return (tokens, refresh_cookie)."""

    register = await client.post(
        "/v1/auth/register", json={"email": email, "password": E2E_PASSWORD}
    )
    assert register.status_code == 201, register.text

    code = extract_signup_code(_email_for(recorder, email))
    confirm = await client.post("/v1/auth/confirm-signup", json={"email": email, "code": code})
    assert confirm.status_code == 204, confirm.text

    login = await client.post("/v1/auth/login", json={"email": email, "password": E2E_PASSWORD})
    assert login.status_code == 200, login.text
    refresh_cookie = login.cookies.get("nica_erp_rt")
    assert refresh_cookie is not None, "login MUST set the nica_erp_rt cookie"
    return login.json(), refresh_cookie


def _tenant_payload(name: str, ruc: str) -> dict[str, Any]:
    return {
        "name": name,
        "ruc": ruc,
        "regime": "general",
        "municipality": "Managua",
        "authorization_dgi": {
            "number": "A-001",
            "valid_from": "2026-01-01",
            "valid_to": "2027-01-01",
        },
        "fiscal_address": "Rotonda Centroamérica, Managua",
        "is_withholder": False,
    }


async def _create_and_switch(
    client: AsyncClient,
    tokens: dict[str, Any],
    refresh_cookie: str,
    *,
    name: str,
    ruc: str,
) -> tuple[str, str]:
    """Create a tenant + switch into it; return ``(tenant_id, access_token)``."""

    access = tokens["access_token"]
    create = await client.post(
        "/v1/tenants",
        headers={"Authorization": f"Bearer {access}"},
        json=_tenant_payload(name=name, ruc=ruc),
    )
    assert create.status_code == 201, create.text
    tenant_id = create.json()["id"]

    # The refresh token rides in the `nica_erp_rt` httpOnly cookie. We
    # extract it from the login response (httpx does NOT auto-store
    # `Secure` cookies over plain http:// in tests) and re-attach it
    # explicitly here.
    switch = await client.post(
        f"/v1/tenants/{tenant_id}/switch",
        headers={"Authorization": f"Bearer {access}"},
        json={},
        cookies={"nica_erp_rt": refresh_cookie},
    )
    assert switch.status_code == 200, switch.text
    return tenant_id, switch.json()["access_token"]


# --- the gate -------------------------------------------------------------


async def test_user_b_cannot_observe_tenant_a_invitations(
    wired_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """B (active = tenant B) MUST NOT see invitations belonging to A."""

    client, recorder = wired_app

    tokens_a, refresh_a = await _signup_confirm_login(client, recorder, "a@test.dev")
    tokens_b, refresh_b = await _signup_confirm_login(client, recorder, "b@test.dev")

    tenant_a_id, access_a_in_a = await _create_and_switch(
        client, tokens_a, refresh_a, name="Empresa A", ruc="0010101800010X"
    )
    tenant_b_id, access_b_in_b = await _create_and_switch(
        client, tokens_b, refresh_b, name="Empresa B", ruc="0010101800020Y"
    )

    # A invites a third party so tenant A has at least one invitation row
    # to leak.
    invite = await client.post(
        f"/v1/tenants/{tenant_a_id}/invitations",
        headers={"Authorization": f"Bearer {access_a_in_a}"},
        json={"email": "x@test.dev", "proposed_role": "accountant"},
    )
    assert invite.status_code == 201, invite.text

    # B (with active tenant B) probes tenant A's invitations. RLS hides
    # the rows; the contract today is either "empty list" or
    # "not found"; the leak we guard against is *seeing the invitation
    # row*.
    probe = await client.get(
        f"/v1/tenants/{tenant_a_id}/invitations",
        headers={"Authorization": f"Bearer {access_b_in_b}"},
    )
    assert probe.status_code in (200, 403, 404), probe.text
    if probe.status_code == 200:
        items = probe.json()
        rows = items if isinstance(items, list) else items.get("items", [])
        assert rows == [], (
            f"RLS leak: tenant B with active={tenant_b_id} observed rows from "
            f"tenant A={tenant_a_id}: {rows!r}"
        )

    # Sanity: A still sees A's invitation when authenticated for A.
    own = await client.get(
        f"/v1/tenants/{tenant_a_id}/invitations",
        headers={"Authorization": f"Bearer {access_a_in_a}"},
    )
    assert own.status_code == 200, own.text
    own_rows = own.json() if isinstance(own.json(), list) else own.json().get("items", [])
    assert any(r.get("email") == "x@test.dev" for r in own_rows), own.text


async def test_forged_jwt_is_rejected_by_tenant_middleware(
    wired_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """A JWT forged to claim a tenant the bearer doesn't belong to → 403."""

    client, recorder = wired_app

    tokens_a, refresh_a = await _signup_confirm_login(client, recorder, "a2@test.dev")
    tokens_b, refresh_b = await _signup_confirm_login(client, recorder, "b2@test.dev")

    tenant_a_id, _ = await _create_and_switch(
        client, tokens_a, refresh_a, name="Empresa A2", ruc="0010101800030Z"
    )
    _tenant_b_id, _ = await _create_and_switch(
        client, tokens_b, refresh_b, name="Empresa B2", ruc="0010101800040W"
    )

    # Recover B's user id from a /v1/me call signed with B's real access.
    me_b = await client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert me_b.status_code == 200, me_b.text
    user_b_id = me_b.json()["id"]

    settings = get_settings()
    forged = forge_jwt(
        user_id=user_b_id,
        email="b2@test.dev",
        active_tenant=tenant_a_id,
        secret=settings.local_jwt_secret,
    )

    attack = await client.get(
        f"/v1/tenants/{tenant_a_id}/members",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert attack.status_code == 403, attack.text

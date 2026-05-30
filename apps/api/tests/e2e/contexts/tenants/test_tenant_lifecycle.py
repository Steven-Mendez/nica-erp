"""End-to-end lifecycle gate for the tenants context.

Walks the owner-driven flow against the real FastAPI app + Postgres
testcontainer:

    create tenant
        ↓
    switch into it (token now carries ``custom:active_tenant``)
        ↓
    list members (owner only)
        ↓
    invite a second user (email captured, returns 201)
        ↓
    list invitations and observe the ``pending`` row
        ↓
    cancel the invitation, re-invite the same address, then
    have the invitee accept the new token

The cancel + re-invite path exercises the outbox PK boundary
(two ``MemberInvited`` rows for the same ``aggregate_id`` plus
the ``InvitationCancelled`` row in between). The accept leg
exercises the per-tenant ``app.tenant_id`` GUC the use case
re-issues from the verified token claim before loading the row.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from bootstrap import container as container_module
from contexts.tenants.adapters.inbound.http import dependencies as tenants_deps_module
from tests.e2e.conftest import E2E_PASSWORD, extract_signup_code
from tests.integration.contexts.identity.conftest import RecordingEmailSender

pytestmark = pytest.mark.e2e


@pytest_asyncio.fixture
async def wired_app_recording_invites(
    wired_app: tuple[AsyncClient, RecordingEmailSender],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AsyncClient, RecordingEmailSender]:
    """Wraps ``wired_app`` so ``InviteMember`` records to the same recorder.

    The base fixture patches the identity provider's ``email_sender``, but
    the tenants invite flow goes through ``build_email_sender()`` in the
    container, which by default returns the SMTP adapter. Redirecting both
    the container hook and the per-request dependency to the recorder lets
    this test read invite emails by destination address.
    """

    client, recorder = wired_app
    monkeypatch.setattr(container_module, "build_email_sender", lambda: recorder)
    monkeypatch.setattr(tenants_deps_module, "build_email_sender", lambda: recorder)
    return client, recorder


# --- helpers --------------------------------------------------------------


def _last_email_to(recorder: RecordingEmailSender, address: str) -> str:
    for sent in reversed(recorder.sent):
        if sent.to == address:
            return sent.text
    raise AssertionError(f"no email recorded for {address!r}")


def _find_invite_token(recorder: RecordingEmailSender, address: str) -> str:
    """Return the invite token from the most recent invite email to *address*.

    The recorder also captures the signup-confirmation email, so we filter
    on the invite URL pattern instead of taking the last email by address.
    """

    import re

    pattern = re.compile(r"/invitations/accept#t=([A-Za-z0-9_\-.]+)")
    for sent in reversed(recorder.sent):
        if sent.to != address:
            continue
        match = pattern.search(sent.text)
        if match is not None:
            return match.group(1)
    raise AssertionError(f"no invite email recorded for {address!r}")


async def _signup_confirm_login(
    client: AsyncClient, recorder: RecordingEmailSender, email: str
) -> dict[str, Any]:
    register = await client.post(
        "/v1/auth/register", json={"email": email, "password": E2E_PASSWORD}
    )
    assert register.status_code == 201, register.text

    code = extract_signup_code(_last_email_to(recorder, email))
    confirm = await client.post("/v1/auth/confirm-signup", json={"email": email, "code": code})
    assert confirm.status_code == 204, confirm.text

    login = await client.post("/v1/auth/login", json={"email": email, "password": E2E_PASSWORD})
    assert login.status_code == 200, login.text
    return login.json()


# --- the gate -------------------------------------------------------------


async def test_owner_walks_create_switch_invite_lifecycle(
    wired_app_recording_invites: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """Owner creates → switches → lists members → invites → lists invitations."""

    client, recorder = wired_app_recording_invites

    owner_tokens = await _signup_confirm_login(client, recorder, "owner@test.dev")
    # Second user exists so the recorder has a known invite recipient; the
    # accept leg is deferred (see module docstring).
    await _signup_confirm_login(client, recorder, "invitee@test.dev")

    owner_access = owner_tokens["access_token"]

    # Create the tenant.
    create = await client.post(
        "/v1/tenants",
        headers={"Authorization": f"Bearer {owner_access}"},
        json={
            "name": "Empresa Lifecycle",
            "ruc": "0010101800010X",
            "regime": "general",
            "municipality": "Managua",
            "authorization_dgi": {
                "number": "A-L1",
                "valid_from": "2026-01-01",
                "valid_to": "2027-01-01",
            },
            "fiscal_address": "Rotonda Centroamérica, Managua",
            "is_withholder": False,
        },
    )
    assert create.status_code == 201, create.text
    tenant_id = create.json()["id"]

    # Switch into the tenant — the access token now carries
    # ``custom:active_tenant``.
    switch = await client.post(
        f"/v1/tenants/{tenant_id}/switch",
        headers={"Authorization": f"Bearer {owner_access}"},
        json={"refresh_token": owner_tokens["refresh_token"]},
    )
    assert switch.status_code == 200, switch.text
    owner_in_tenant = switch.json()["access_token"]

    # Owner lists members and observes themselves as the only member.
    members_before = await client.get(
        f"/v1/tenants/{tenant_id}/members",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
    )
    assert members_before.status_code == 200, members_before.text
    rows_before = (
        members_before.json()
        if isinstance(members_before.json(), list)
        else members_before.json().get("items", [])
    )
    assert any(r.get("role") == "owner" for r in rows_before), rows_before

    # Owner invites the second user as ``accountant``.
    invite = await client.post(
        f"/v1/tenants/{tenant_id}/invitations",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
        json={"email": "invitee@test.dev", "proposed_role": "accountant"},
    )
    assert invite.status_code == 201, invite.text
    invitation_id = invite.json()["id"]

    # Email was sent and the URL contains a token.
    first_token = _find_invite_token(recorder, "invitee@test.dev")
    assert first_token

    # Owner lists pending invitations and observes the row.
    invitations = await client.get(
        f"/v1/tenants/{tenant_id}/invitations",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
    )
    assert invitations.status_code == 200, invitations.text
    inv_rows = (
        invitations.json()
        if isinstance(invitations.json(), list)
        else invitations.json().get("items", [])
    )
    pending = [r for r in inv_rows if r.get("email") == "invitee@test.dev"]
    assert pending, inv_rows
    assert pending[0]["status"] == "pending"

    # The row carries the same ``invitation_id`` the create response
    # returned, proving the SPA can drive cancel / accept by id.
    assert pending[0]["id"] == invitation_id

    # Owner cancels the pending invitation. This used to collide on
    # the outbox primary key because ``InviteMember`` and
    # ``CancelInvitation`` both wrote with ``event_id =
    # invitation.id``; both now mint fresh UUID v4s per event.
    cancel = await client.delete(
        f"/v1/tenants/{tenant_id}/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
    )
    assert cancel.status_code == 204, cancel.text

    # Re-invite the same address. The second ``MemberInvited`` outbox
    # row shares the previous ``aggregate_id`` (invitation.id of the
    # new invitation row) but lives under its own ``event_id``.
    reinvite = await client.post(
        f"/v1/tenants/{tenant_id}/invitations",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
        json={"email": "invitee@test.dev", "proposed_role": "accountant"},
    )
    assert reinvite.status_code == 201, reinvite.text
    second_token = _find_invite_token(recorder, "invitee@test.dev")
    assert second_token != first_token

    # The invitee logs in (their JWT has no active tenant yet) and
    # POSTs the fresh token to the public accept endpoint. The use
    # case verifies the JWT, re-issues ``set_config('app.tenant_id',
    # ..., true)`` from the claim, then writes the ``MemberJoined``
    # outbox row.
    invitee_login = await client.post(
        "/v1/auth/login",
        json={"email": "invitee@test.dev", "password": E2E_PASSWORD},
    )
    assert invitee_login.status_code == 200, invitee_login.text
    invitee_access = invitee_login.json()["access_token"]

    accept = await client.post(
        "/v1/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_access}"},
        json={"token": second_token},
    )
    assert accept.status_code == 200, accept.text
    body = accept.json()
    assert body["tenant_id"] == tenant_id
    assert body["role"] == "accountant"

    # Owner re-lists members and now observes the invitee as a
    # second active row.
    members_after = await client.get(
        f"/v1/tenants/{tenant_id}/members",
        headers={"Authorization": f"Bearer {owner_in_tenant}"},
    )
    assert members_after.status_code == 200, members_after.text
    rows_after = (
        members_after.json()
        if isinstance(members_after.json(), list)
        else members_after.json().get("items", [])
    )
    accountants = [r for r in rows_after if r.get("role") == "accountant"]
    assert accountants, rows_after
    assert any(r.get("email") == "invitee@test.dev" for r in accountants)

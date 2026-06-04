"""End-to-end tests for the identity HTTP flow.

These run the real FastAPI app through ``httpx.AsyncClient`` + ASGI
transport, with the following surgeries:

- The shared testcontainer ``session_factory`` is patched into
  ``bootstrap.db.get_session_factory`` so ``get_uow``, the identity
  provider, and the middleware's verifier all hit the same database.
- The recording :class:`RecordingEmailSender` is injected into the
  process-wide ``IdentityProviderLocal`` so the test can read the
  signup code out of the captured email body instead of running Mailpit.
- ``get_uow`` is overridden so each request gets a UoW bound to the
  same ``session_factory``; the identity provider used by the request
  (built by :func:`build_identity_provider_for_request`) shares the
  UoW, so its ``auth_local_users`` writes commit with the outbox row
  in ``ConfirmSignup``.

Skip when the testcontainer / migration didn't create
``auth_local_users`` (e.g. because Docker isn't available).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bootstrap import api as api_module
from bootstrap import container as container_module
from bootstrap import db as db_module
from bootstrap import dependencies as bootstrap_deps_module
from bootstrap.db import get_uow
from contexts.identity.adapters.inbound.http import dependencies as deps_module
from contexts.identity.adapters.outbound.identity_provider.local import (
    IdentityProviderLocal,
)
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from tests.integration.contexts.identity.conftest import RecordingEmailSender

_PASSWORD = "Demo1234!@xy"
_CODE_RE = re.compile(r"\b(\d{6})\b")


def _extract_code(body: str) -> str:
    match = _CODE_RE.search(body)
    assert match is not None, f"no 6-digit code in body: {body!r}"
    return match.group(1)


@pytest.fixture
async def _wire_app(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, RecordingEmailSender]]:
    """Wire the app + a recording email sender against the testcontainer."""

    # Confirm migration 0002 created auth_local_users; skip when missing.
    async with session_factory() as probe:
        exists = (
            await probe.execute(text("SELECT to_regclass('public.auth_local_users') IS NOT NULL"))
        ).scalar_one()
    if not exists:
        pytest.skip(
            "auth_local_users missing; rerun with APP_ENV=local so migration "
            "0002 creates the local ledger"
        )
        return

    # Truncate so the test is order-independent.
    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE auth_local_users RESTART IDENTITY"))
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE outbox RESTART IDENTITY"))
        await session.commit()

    monkeypatch.setattr(db_module, "get_session_factory", lambda: session_factory)

    # Replace the middleware's IdP singleton so verify_token also signs with
    # the test secret, and wire a recording email sender so signup codes are
    # captured. The middleware IdP uses a private UoW for the local adapter
    # but its UoW is never activated for verify_token.
    email_sender = RecordingEmailSender()

    container_module.build_identity_provider_for_middleware.cache_clear()
    middleware_idp = container_module.build_identity_provider_for_middleware()
    assert isinstance(middleware_idp, IdentityProviderLocal)
    middleware_idp.email_sender = email_sender

    # Patch the per-request builder so the SMTP-bound EmailSenderSmtp is
    # replaced with the recorder. We rebuild via the local helper directly,
    # passing the request's UoW unchanged.
    original_for_request = container_module.build_identity_provider_for_request

    def _patched_for_request(uow: SqlAlchemyUnitOfWork) -> IdentityProviderLocal:
        idp = original_for_request(uow)
        assert isinstance(idp, IdentityProviderLocal)
        idp.email_sender = email_sender
        return idp

    monkeypatch.setattr(
        container_module, "build_identity_provider_for_request", _patched_for_request
    )
    monkeypatch.setattr(deps_module, "build_identity_provider_for_request", _patched_for_request)

    # Make the request UoW use the testcontainer session factory too.
    def _request_uow_factory() -> container_module._RequestUnitOfWork:
        return container_module._RequestUnitOfWork(session_factory)

    monkeypatch.setattr(container_module, "build_request_uow", _request_uow_factory)
    monkeypatch.setattr(bootstrap_deps_module, "build_request_uow", _request_uow_factory)

    async def _override_uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
        yield SqlAlchemyUnitOfWork(session_factory)

    api_module.app.dependency_overrides[get_uow] = _override_uow

    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            yield client, email_sender
        finally:
            api_module.app.dependency_overrides.pop(get_uow, None)


@pytest.mark.e2e
async def test_register_returns_201_with_empty_body(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, _email = _wire_app
    response = await client.post(
        "/v1/auth/register",
        json={"email": "alice@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 201
    assert response.json() == {}


@pytest.mark.e2e
async def test_register_is_enumeration_resistant(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, _email = _wire_app
    body = {"email": "bob@example.com", "password": _PASSWORD}
    first = await client.post("/v1/auth/register", json=body)
    second = await client.post("/v1/auth/register", json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json() == {}


@pytest.mark.e2e
async def test_full_auth_loop(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    register = await client.post(
        "/v1/auth/register",
        json={"email": "carol@example.com", "password": _PASSWORD},
    )
    assert register.status_code == 201
    # Extract the 6-digit signup code from the recorded email body.
    assert email.sent, "register did not send an email"
    code = _extract_code(email.sent[-1].text)

    confirm = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "carol@example.com", "code": code},
    )
    assert confirm.status_code == 204

    login = await client.post(
        "/v1/auth/login",
        json={"email": "carol@example.com", "password": _PASSWORD},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"]
    assert tokens["id_token"]
    # The refresh token rides only in the `nica_erp_rt` httpOnly cookie
    # — the JSON body MUST NOT carry it (audit F-011).
    assert "refresh_token" not in tokens
    assert "nica_erp_rt=" in login.headers.get("set-cookie", "")

    access = tokens["access_token"]
    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == "carol@example.com"

    logout = await client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {access}"})
    assert logout.status_code == 204


@pytest.mark.e2e
async def test_login_sets_refresh_cookie(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """Audit F-005: every endpoint that mints a refresh token MUST
    pin it as the httpOnly ``nica_erp_rt`` cookie so the SPA does not
    need to stash it in sessionStorage."""
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "cookie@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "cookie@example.com", "code": code},
    )

    response = await client.post(
        "/v1/auth/login",
        json={"email": "cookie@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "nica_erp_rt=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()
    assert "Path=/v1" in set_cookie


@pytest.mark.e2e
async def test_logout_revokes_refresh_token_and_blocks_subsequent_refresh(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """Audit F-016: logout SHALL revoke the refresh token's jti and
    the next /v1/auth/refresh with the same token MUST return 401."""
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "f016@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "f016@example.com", "code": code},
    )
    login = await client.post(
        "/v1/auth/login",
        json={"email": "f016@example.com", "password": _PASSWORD},
    )
    tokens = login.json()
    access = tokens["access_token"]
    # Refresh token lives in the cookie set by /v1/auth/login.
    refresh_cookie = login.cookies.get("nica_erp_rt")
    assert refresh_cookie is not None

    logout = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        cookies={"nica_erp_rt": refresh_cookie},
    )
    assert logout.status_code == 204

    follow_up = await client.post(
        "/v1/auth/refresh",
        cookies={"nica_erp_rt": refresh_cookie},
    )
    assert follow_up.status_code == 401
    assert follow_up.json()["code"] == "auth.invalid_credentials"


@pytest.mark.e2e
async def test_refresh_token_rejected_on_bearer_auth_path(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """Audit F-011: a refresh JWT MUST NOT be accepted as a Bearer
    access token on any protected endpoint."""
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "f011@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "f011@example.com", "code": code},
    )
    login = await client.post(
        "/v1/auth/login",
        json={"email": "f011@example.com", "password": _PASSWORD},
    )
    # The refresh token is delivered in the httpOnly cookie now;
    # tests grab it from there to assert it gets rejected as a Bearer.
    refresh_token = login.cookies.get("nica_erp_rt")
    assert refresh_token is not None

    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert me.status_code == 401


@pytest.mark.e2e
async def test_me_without_token_is_401_problem_detail(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, _email = _wire_app
    response = await client.get("/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "auth.invalid_credentials"


@pytest.mark.e2e
async def test_patch_me_rejects_unknown_field(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    # Register + confirm + login to get a valid token.
    await client.post(
        "/v1/auth/register",
        json={"email": "dan@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "dan@example.com", "code": code},
    )
    login = await client.post(
        "/v1/auth/login",
        json={"email": "dan@example.com", "password": _PASSWORD},
    )
    access = login.json()["access_token"]

    response = await client.patch(
        "/v1/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"email": "x@x.io"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation.request_invalid"


@pytest.mark.e2e
async def test_confirm_signup_writes_user_registered_outbox_row(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Contract the future outbox publisher will consume.

    Locks the event_type, event_version, sentinel tenant_id, and the
    payload keys so any change to the wire shape forces an explicit
    update to the publisher contract — not a silent one.
    """

    client, email = _wire_app
    register = await client.post(
        "/v1/auth/register",
        json={"email": "outbox-contract@example.com", "password": _PASSWORD},
    )
    assert register.status_code == 201
    code = _extract_code(email.sent[-1].text)
    confirm = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "outbox-contract@example.com", "code": code},
    )
    assert confirm.status_code == 204

    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT event_type, event_version, tenant_id, aggregate_type, "
                    "payload FROM outbox WHERE event_type = :t"
                ),
                {"t": "identity.UserRegistered"},
            )
        ).all()

    assert len(rows) == 1, rows
    (event_type, event_version, tenant_id, aggregate_type, payload) = rows[0]
    assert event_type == "identity.UserRegistered"
    assert event_version == 1
    assert str(tenant_id) == "00000000-0000-0000-0000-000000000000"
    assert aggregate_type == "User"
    assert set(payload.keys()) == {"user_id", "email", "registered_at"}
    assert payload["email"] == "outbox-contract@example.com"


@pytest.mark.e2e
async def test_confirm_signup_with_wrong_otp_returns_400_invalid_confirmation_code(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "wrong-otp@example.com", "password": _PASSWORD},
    )
    # email captured but the test submits the wrong code on purpose
    assert email.sent

    response = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "wrong-otp@example.com", "code": "000000"},
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "auth.invalid_confirmation_code"


@pytest.mark.e2e
async def test_confirm_signup_wrong_then_right_code_succeeds_idempotently(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    """Audit F-002 regression: a wrong OTP followed by the correct OTP
    on the same email must succeed, not 500 / 503. Two successful
    confirm-signup calls in a row must also be idempotent.
    """
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "f002@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)

    # First attempt: wrong code
    wrong = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "f002@example.com", "code": "000000"},
    )
    assert wrong.status_code == 400

    # Retry with the right code: must succeed (204 when no auto-login).
    right = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "f002@example.com", "code": code},
    )
    assert right.status_code == 204, right.text

    # A second confirm with the same code must ALSO succeed (idempotency).
    again = await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "f002@example.com", "code": code},
    )
    assert again.status_code == 204, again.text


@pytest.mark.e2e
async def test_reset_password_with_used_code_returns_410_reset_token_used(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "reset-twice@example.com", "password": _PASSWORD},
    )
    signup_code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "reset-twice@example.com", "code": signup_code},
    )
    email.sent.clear()
    await client.post(
        "/v1/auth/password/forgot",
        json={"email": "reset-twice@example.com"},
    )
    reset_code = _extract_code(email.sent[-1].text)
    first = await client.post(
        "/v1/auth/password/reset",
        json={
            "email": "reset-twice@example.com",
            "code": reset_code,
            "new_password": "NewPass5678!@ab",
        },
    )
    assert first.status_code == 204

    second = await client.post(
        "/v1/auth/password/reset",
        json={
            "email": "reset-twice@example.com",
            "code": reset_code,
            "new_password": "OtherPass9012!@cd",
        },
    )
    assert second.status_code == 410
    assert second.headers["content-type"].startswith("application/problem+json")
    assert second.json()["code"] == "auth.reset_token_used"


@pytest.mark.e2e
async def test_resend_code_within_cooldown_returns_429_resend_throttled(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "resend-throttle@example.com", "password": _PASSWORD},
    )
    email.sent.clear()
    response = await client.post(
        "/v1/auth/resend-code",
        json={"email": "resend-throttle@example.com"},
    )
    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["retry-after"]
    body = response.json()
    assert body["code"] == "auth.rate_limited"
    assert body["scope"] == "resend"
    assert isinstance(body.get("retry_after_seconds"), int)
    assert body["retry_after_seconds"] >= 1


@pytest.mark.e2e
async def test_login_with_wrong_password_returns_problem_detail(
    _wire_app: tuple[AsyncClient, RecordingEmailSender],
) -> None:
    client, email = _wire_app
    await client.post(
        "/v1/auth/register",
        json={"email": "evil@example.com", "password": _PASSWORD},
    )
    code = _extract_code(email.sent[-1].text)
    await client.post(
        "/v1/auth/confirm-signup",
        json={"email": "evil@example.com", "code": code},
    )

    response = await client.post(
        "/v1/auth/login",
        json={"email": "evil@example.com", "password": "WrongPass99!@xy"},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "auth.invalid_credentials"

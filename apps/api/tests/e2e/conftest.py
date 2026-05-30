"""Shared fixtures for end-to-end tests.

The ``wired_app`` fixture brings up the real FastAPI app against the
session-scoped Postgres testcontainer + ``session_factory`` from the
root conftest, with the same surgical patches the identity auth-flow
test introduced: the request UoW, the per-request identity-provider
builder, the middleware identity-provider singleton, and the
``get_uow`` dependency override are all bound to the testcontainer
session factory; a :class:`RecordingEmailSender` is injected into the
local identity provider so signup verification codes can be read out
of the captured email body.

The same fixture is consumed by the tenants RLS-isolation gate
(``tests/e2e/contexts/tenants/test_rls_tenant_isolation.py``) and is
available to any future cross-context e2e that needs the wired-app
shape.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
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

E2E_PASSWORD = "Demo1234!@xy"
_CODE_RE = re.compile(r"\b(\d{6})\b")


def extract_signup_code(body: str) -> str:
    """Return the 6-digit confirmation code embedded in an email body."""

    match = _CODE_RE.search(body)
    assert match is not None, f"no 6-digit code in body: {body!r}"
    return match.group(1)


@pytest_asyncio.fixture
async def wired_app(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, RecordingEmailSender]]:
    """Yield an :class:`AsyncClient` bound to the real app + a recorder.

    Truncates the identity + tenant tables before yielding so each test
    is order-independent. Skips when ``auth_local_users`` is missing
    (i.e. the test session was not started with ``APP_ENV=local``).
    """

    async with session_factory() as probe:
        exists = (
            await probe.execute(text("SELECT to_regclass('public.auth_local_users') IS NOT NULL"))
        ).scalar_one()
    if not exists:
        pytest.skip(
            "auth_local_users missing; rerun with APP_ENV=local so "
            "migration 0002 creates the local ledger"
        )
        return

    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE auth_local_users RESTART IDENTITY"))
        await session.execute(text("TRUNCATE TABLE invitations RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenant_members RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.execute(text("TRUNCATE TABLE outbox RESTART IDENTITY"))
        await session.commit()

    monkeypatch.setattr(db_module, "get_session_factory", lambda: session_factory)
    # ``bootstrap.container`` did ``from bootstrap.db import get_session_factory``
    # at import time, so the helper inside ``container`` still points at the
    # un-patched function. Re-patch the local reference so
    # ``build_request_uow`` (used by ``TenantMiddleware``) returns a UoW
    # bound to the testcontainer.
    monkeypatch.setattr(container_module, "get_session_factory", lambda: session_factory)

    email_sender = RecordingEmailSender()

    container_module.build_identity_provider_for_middleware.cache_clear()
    middleware_idp = container_module.build_identity_provider_for_middleware()
    assert isinstance(middleware_idp, IdentityProviderLocal)
    middleware_idp.email_sender = email_sender

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


__all__ = ["E2E_PASSWORD", "extract_signup_code", "wired_app"]

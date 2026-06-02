"""Composition root for the identity-context outbound ports.

Two builder pairs exist by design:

- :func:`build_identity_provider_for_middleware` returns a process-wide
  singleton. The middleware only ever calls
  :meth:`IdentityProvider.verify_token`, which is database-free for both
  the local (HS256 JWT decode against ``LOCAL_JWT_SECRET``) and Cognito
  (JWKS lookup + RS256 decode) adapters. Caching the instance avoids
  rebuilding the boto3 client on every request.
- :func:`build_identity_provider_for_request` returns a fresh adapter
  bound to the request's :class:`SqlAlchemyUnitOfWork`. The local
  adapter writes to ``auth_local_users`` through
  ``uow.current_session``; the HTTP dependency layer wraps each request
  in ``async with uow.begin():`` so the adapter joins it.

Reentrant UoW
-------------

The local identity adapter needs ``uow.current_session`` set whenever
its methods are called (it reaches into ``auth_local_users`` directly).
Use cases like ``ConfirmSignup``, ``GetMe``, and ``UpdateProfile``
already open ``async with uow.begin():`` themselves. To make both styles
compose — adapter-first calls require the UoW to be active before the
use case body runs; use-case-opened begins re-enter the same UoW — the
HTTP request UoW is a :class:`_RequestUnitOfWork`: a reentrant
``SqlAlchemyUnitOfWork`` whose nested ``begin()`` is a no-op (yields the
currently active session) so the inner block commits/rolls back with the
outer one.

:func:`build_email_sender` is a per-call factory — both ``smtp`` and
``ses`` adapters are stateless after construction.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.db import get_session_factory
from bootstrap.settings import get_settings
from contexts.identity.application.ports.outbound import EmailSender, IdentityProvider

if TYPE_CHECKING:
    from contexts.identity.application.login_attempt_throttle import (
        LoginAttemptThrottle,
    )
from contexts.tenants.application.ports.outbound import (
    InvitationRepository,
    InvitationTokenGenerator,
    MembershipRepository,
    TenantRepository,
)
from shared_kernel.adapters.context import CurrentUserContext, TenantContext
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork

# Sentinel UUID used when no tenant / user is active. The canonical RLS
# policies use ``current_setting('app.tenant_id', true)::uuid`` — comparing
# against this zero UUID returns ``false`` for every real row, so the
# sentinel acts as "no tenant active" without requiring policy changes.
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


class _RequestUnitOfWork(SqlAlchemyUnitOfWork):
    """``SqlAlchemyUnitOfWork`` whose ``begin()`` is reentrant.

    The first entry opens a real session + transaction via the parent
    implementation. Nested re-entries (e.g. when a use case opens
    ``async with self.uow.begin():`` inside an HTTP request that already
    opened the outer transaction) yield the currently active session
    without starting a new SAVEPOINT — the outer ``__aexit__`` is the one
    that commits or rolls back. This lets HTTP-level transaction
    wrapping coexist with use cases that still open their own UoW.
    """

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        if self._session is not None:
            # Reentrant: yield the already-active session without starting
            # a nested transaction. The outer ``begin`` already issued the
            # SET LOCAL statements; they remain in effect for the inner
            # block because PostgreSQL scopes them to the transaction.
            yield self._session
            return
        async with super().begin() as session:
            tenant = TenantContext.get()
            current_user = CurrentUserContext.get()
            tenant_id_param = str(tenant) if tenant is not None else _ZERO_UUID
            user_id_param = str(current_user.user_id) if current_user is not None else _ZERO_UUID
            # ``set_config(name, value, is_local=true)`` is the function
            # form of ``SET LOCAL`` — it is transaction-scoped (clears on
            # COMMIT/ROLLBACK, zero leak between pooled connections) and
            # accepts bound parameters, which the ``SET LOCAL`` SQL form
            # does not. The RLS policies read the GUC via
            # ``current_setting('app.tenant_id', true)::uuid``.
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"),
                {"t": tenant_id_param},
            )
            await session.execute(
                text("SELECT set_config('app.current_user_id', :u, true)"),
                {"u": user_id_param},
            )
            yield session


def _build_local_idp(uow: SqlAlchemyUnitOfWork) -> IdentityProvider:
    from contexts.identity.adapters.outbound.email.smtp import EmailSenderSmtp
    from contexts.identity.adapters.outbound.identity_provider.local import (
        IdentityProviderLocal,
    )

    settings = get_settings()
    return IdentityProviderLocal(
        uow=uow,
        email_sender=EmailSenderSmtp(host=settings.smtp_host, port=settings.smtp_port),
        jwt_secret=settings.local_jwt_secret,
        jwt_access_ttl_seconds=settings.jwt_access_ttl_seconds,
        jwt_refresh_ttl_seconds=settings.jwt_refresh_ttl_seconds,
        signup_code_ttl_seconds=settings.signup_code_ttl_seconds,
        password_reset_code_ttl_seconds=settings.password_reset_code_ttl_seconds,
        verification_attempts_max=settings.verification_attempts_max,
        verification_attempts_window_seconds=settings.verification_attempts_window_seconds,
    )


def _build_cognito_idp() -> IdentityProvider:
    import boto3

    from contexts.identity.adapters.outbound.identity_provider.cognito import (
        IdentityProviderCognito,
    )

    settings = get_settings()
    client: Any = boto3.client("cognito-idp", region_name=settings.cognito_region)
    return IdentityProviderCognito(
        client=client,
        user_pool_id=settings.cognito_user_pool_id,
        app_client_id=settings.cognito_app_client_id,
        region=settings.cognito_region,
    )


def build_identity_provider(
    uow: SqlAlchemyUnitOfWork | None = None,
) -> IdentityProvider:
    """Build the ``IdentityProvider`` adapter that matches ``settings.app_env``.

    ``uow`` is required when ``app_env == "local"`` because the local
    adapter writes to ``auth_local_users`` through the UoW's session.
    The Cognito adapter is stateless and ignores ``uow``.
    """

    settings = get_settings()
    if settings.app_env == "local":
        if uow is None:
            raise RuntimeError(
                "IdentityProviderLocal requires a SqlAlchemyUnitOfWork; "
                "pass `uow=` when `app_env == 'local'`."
            )
        return _build_local_idp(uow)
    if settings.app_env == "aws":
        return _build_cognito_idp()
    raise ValueError(f"Unknown app_env: {settings.app_env!r}")


@lru_cache(maxsize=1)
def build_identity_provider_for_middleware() -> IdentityProvider:
    """Process-wide :class:`IdentityProvider` for ``AuthMiddleware.verify_token``.

    The middleware only calls :meth:`IdentityProvider.verify_token`, which
    touches no database state in either adapter. We bind a single
    :class:`SqlAlchemyUnitOfWork` to satisfy the local adapter's
    constructor — it's never activated.
    """

    settings = get_settings()
    if settings.app_env == "local":
        return _build_local_idp(SqlAlchemyUnitOfWork(get_session_factory()))
    if settings.app_env == "aws":
        return _build_cognito_idp()
    raise ValueError(f"Unknown app_env: {settings.app_env!r}")


def build_identity_provider_for_request(
    uow: SqlAlchemyUnitOfWork,
) -> IdentityProvider:
    """Per-request :class:`IdentityProvider` bound to the request's UoW."""

    return build_identity_provider(uow)


def build_email_sender() -> EmailSender:
    """Build the ``EmailSender`` adapter that matches ``settings.app_env``."""

    settings = get_settings()
    if settings.app_env == "local":
        from contexts.identity.adapters.outbound.email.smtp import EmailSenderSmtp

        return EmailSenderSmtp(host=settings.smtp_host, port=settings.smtp_port)
    if settings.app_env == "aws":
        import boto3

        from contexts.identity.adapters.outbound.email.ses import EmailSenderSes

        client: Any = boto3.client("ses", region_name=settings.cognito_region)
        return EmailSenderSes(client=client, from_address=settings.ses_from_address)
    raise ValueError(f"Unknown app_env: {settings.app_env!r}")


def build_request_uow() -> _RequestUnitOfWork:
    """Construct the reentrant UoW used by the HTTP request lifecycle."""

    return _RequestUnitOfWork(get_session_factory())


# --------------------------------------------------------------------- tenants


def build_tenant_repository(uow: SqlAlchemyUnitOfWork) -> TenantRepository:
    from contexts.tenants.adapters.outbound.persistence.sqlalchemy import (
        TenantRepositorySqlAlchemy,
    )

    return TenantRepositorySqlAlchemy(uow)


def build_membership_repository(uow: SqlAlchemyUnitOfWork) -> MembershipRepository:
    from contexts.tenants.adapters.outbound.persistence.sqlalchemy import (
        MembershipRepositorySqlAlchemy,
    )

    return MembershipRepositorySqlAlchemy(uow)


def build_invitation_repository(uow: SqlAlchemyUnitOfWork) -> InvitationRepository:
    from contexts.tenants.adapters.outbound.persistence.sqlalchemy import (
        InvitationRepositorySqlAlchemy,
    )

    return InvitationRepositorySqlAlchemy(uow)


def build_invitation_token_generator() -> InvitationTokenGenerator:
    from contexts.tenants.adapters.outbound.tokens import (
        InvitationTokenGeneratorJwt,
    )

    settings = get_settings()
    return InvitationTokenGeneratorJwt(
        secret=settings.local_jwt_secret,
        ttl_seconds=settings.invitation_token_ttl_seconds,
    )


@lru_cache(maxsize=1)
def build_login_throttle() -> LoginAttemptThrottle:
    """Process-wide singleton for the login-attempt throttle.

    Local + test profiles get the in-memory adapter (the failure
    counters live inside this single process — fine for development
    and the test fixtures that synthesise time). The AWS profile
    builds the Redis adapter against ``settings.redis_url``; if that
    is empty (Redis not yet provisioned) we fall back to the
    in-memory adapter and log a one-time warning. Both adapters
    honour the same threshold settings.
    """
    from datetime import timedelta

    from contexts.identity.adapters.outbound.login_attempt_throttle_memory import (
        InMemoryLoginAttemptThrottle,
    )

    settings = get_settings()
    identifier_window = timedelta(seconds=settings.login_throttle_identifier_window_seconds)
    ip_window = timedelta(seconds=settings.login_throttle_ip_window_seconds)

    if settings.app_env == "aws" and settings.redis_url:
        try:
            from redis import Redis  # imported lazily so the local

            # profile does not require the redis package at runtime.
            from contexts.identity.adapters.outbound.login_attempt_throttle_redis import (
                RedisLoginAttemptThrottle,
            )
        except ImportError:  # pragma: no cover — defensive
            pass
        else:
            client = Redis.from_url(settings.redis_url)
            return RedisLoginAttemptThrottle(
                client=client,
                identifier_limit=settings.login_throttle_identifier_limit,
                identifier_window=identifier_window,
                ip_limit=settings.login_throttle_ip_limit,
                ip_window=ip_window,
            )

    throttle: LoginAttemptThrottle = InMemoryLoginAttemptThrottle(
        identifier_limit=settings.login_throttle_identifier_limit,
        identifier_window=identifier_window,
        ip_limit=settings.login_throttle_ip_limit,
        ip_window=ip_window,
    )
    return throttle


def get_login_throttle() -> LoginAttemptThrottle:
    """FastAPI dependency-friendly wrapper around the singleton builder."""

    return build_login_throttle()


__all__ = [
    "build_email_sender",
    "build_identity_provider",
    "build_identity_provider_for_middleware",
    "build_identity_provider_for_request",
    "build_invitation_repository",
    "build_invitation_token_generator",
    "build_login_throttle",
    "build_membership_repository",
    "build_request_uow",
    "build_tenant_repository",
    "get_login_throttle",
]

"""FastAPI dependencies for the identity HTTP adapter.

Each dependency is a thin factory that wires the inbound HTTP layer to a
fresh use case constructed per request, sharing a reentrant
:class:`bootstrap.container._RequestUnitOfWork` between the
identity-provider adapter (``auth_local_users`` writes) and the outbox
writer so all writes commit in the same transaction.

Transaction boundaries
----------------------

The :func:`get_request_uow` dependency wraps every HTTP request in
``async with uow.begin():`` before yielding the UoW, so adapter calls
(notably ``IdentityProviderLocal``'s methods that read/write
``auth_local_users``) always see ``uow.current_session`` populated.

Use cases that re-enter ``begin()`` themselves — ``ConfirmSignup``,
``GetMe``, ``UpdateProfile`` — get the same session back because
``_RequestUnitOfWork.begin`` is reentrant: nested calls yield the
already-active session instead of starting a new one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Depends, Header

from bootstrap.container import (
    build_identity_provider_for_request,
    build_request_uow,
)
from bootstrap.db import get_uow
from contexts.identity.adapters.outbound.persistence.sqlalchemy.user_repository import (
    UserRepositorySqlAlchemy,
)
from contexts.identity.application.errors import InvalidCredentialsError
from contexts.identity.application.ports.outbound import IdentityProvider
from contexts.identity.application.use_cases import (
    Authenticate,
    ChangePassword,
    ConfirmSignup,
    ForgotPassword,
    GetMe,
    Logout,
    RefreshToken,
    RegisterUser,
    ResendCode,
    ResetPassword,
    UpdateProfile,
)
from shared_kernel.adapters.context import CurrentUser, CurrentUserContext
from shared_kernel.adapters.outbox_sqlalchemy import OutboxWriterSqlAlchemy
from shared_kernel.adapters.unit_of_work import SqlAlchemyUnitOfWork
from shared_kernel.application.unit_of_work import UnitOfWork


async def get_request_uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Yield the reentrant :class:`_RequestUnitOfWork` for the request.

    Wrapping the entire HTTP request in a single ``async with uow.begin():``
    means every adapter call sees ``uow.current_session`` populated.
    Use cases that re-enter ``begin()`` (``ConfirmSignup``, ``GetMe``,
    ``UpdateProfile``) get the same session back because
    :class:`_RequestUnitOfWork.begin` is reentrant.
    """

    uow = build_request_uow()
    async with uow.begin():
        yield uow


def get_sa_uow(uow: UnitOfWork = Depends(get_uow)) -> SqlAlchemyUnitOfWork:
    """Narrow ``get_uow`` to the SQLAlchemy implementation for adapter wiring.

    Retained for routes that don't need transactional wrapping (none today,
    but keeping the helper makes future additions easier).
    """

    return cast(SqlAlchemyUnitOfWork, uow)


def get_identity_provider(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> IdentityProvider:
    """Build a request-scoped :class:`IdentityProvider` bound to the reentrant UoW."""

    return build_identity_provider_for_request(uow)


# --- Use case factories ----------------------------------------------------


def get_register_user(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> RegisterUser:
    return RegisterUser(identity_provider=idp)


def get_confirm_signup(
    idp: IdentityProvider = Depends(get_identity_provider),
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> ConfirmSignup:
    return ConfirmSignup(
        identity_provider=idp,
        user_repository=UserRepositorySqlAlchemy(uow),
        outbox_writer=OutboxWriterSqlAlchemy(uow),
        uow=uow,
    )


def get_resend_code(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> ResendCode:
    return ResendCode(identity_provider=idp)


def get_authenticate(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> Authenticate:
    return Authenticate(identity_provider=idp)


def get_refresh_token(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> RefreshToken:
    return RefreshToken(identity_provider=idp)


def get_forgot_password(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> ForgotPassword:
    return ForgotPassword(identity_provider=idp)


def get_reset_password(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> ResetPassword:
    return ResetPassword(identity_provider=idp)


def get_change_password(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> ChangePassword:
    return ChangePassword(identity_provider=idp)


def get_logout(
    idp: IdentityProvider = Depends(get_identity_provider),
) -> Logout:
    return Logout(identity_provider=idp)


def get_get_me(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> GetMe:
    return GetMe(user_repository=UserRepositorySqlAlchemy(uow), uow=uow)


def get_update_profile(
    uow: SqlAlchemyUnitOfWork = Depends(get_request_uow),
) -> UpdateProfile:
    return UpdateProfile(
        user_repository=UserRepositorySqlAlchemy(uow),
        uow=uow,
    )


# --- Auth dependencies -----------------------------------------------------


def get_current_user() -> CurrentUser:
    """Return the user the middleware bound to the request context.

    The middleware populates :class:`CurrentUserContext` after verifying the
    bearer token. Raising :class:`InvalidCredentialsError` here causes the
    registered exception handler to return a 401 with the
    ``auth.invalid_credentials`` problem code — that path only fires when a
    route in the unauthenticated allowlist accidentally uses this
    dependency.
    """

    user = CurrentUserContext.get()
    if user is None:
        raise InvalidCredentialsError("No authenticated user in context")
    return user


def get_access_token(authorization: str = Header(default="")) -> str:
    """Extract the bearer token from the inbound ``Authorization`` header."""

    if not authorization.startswith("Bearer "):
        raise InvalidCredentialsError("Missing or malformed Authorization header")
    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise InvalidCredentialsError("Empty bearer token")
    return token


__all__ = [
    "get_access_token",
    "get_authenticate",
    "get_change_password",
    "get_confirm_signup",
    "get_current_user",
    "get_forgot_password",
    "get_get_me",
    "get_identity_provider",
    "get_logout",
    "get_refresh_token",
    "get_register_user",
    "get_request_uow",
    "get_resend_code",
    "get_reset_password",
    "get_sa_uow",
    "get_update_profile",
]

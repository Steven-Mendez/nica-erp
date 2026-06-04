"""Authentication middleware for the identity HTTP adapter.

The middleware:

1. Allows public routes (per ``allowlist.is_unauthenticated``) through
   without inspecting the ``Authorization`` header.
2. For every other route, parses ``Authorization: Bearer <jwt>``, calls
   ``IdentityProvider.verify_token`` (HS256 locally, RS256 via Cognito
   JWKS in AWS), and populates ``CurrentUserContext`` for the request.
3. Enforces the "no active tenant" allowlist: tenantless JWTs may only
   reach the routes in ``allowlist.NO_TENANT_REQUIRED``; everywhere else
   they get a 403 ``tenant.required``.

The 401/403 responses use ``application/problem+json`` so the SPA's
generic RFC-7807 handler can render them. The middleware is installed
**before** ``CORSMiddleware`` in ``bootstrap.api.create_app()`` so the
CORS layer runs OUTERMOST and can decorate the 401 response with the
allow-origin headers the browser requires. (Starlette runs middleware in
reverse order of addition — the last ``add_middleware`` call is the
outermost layer.)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from contexts.identity.adapters.inbound.http.allowlist import (
    is_no_tenant_required,
    is_unauthenticated,
)
from contexts.identity.adapters.inbound.http.errors import (
    PROBLEM_CONTENT_TYPE,
)
from contexts.identity.adapters.inbound.http.schemas import ProblemDetail
from contexts.identity.application.errors import TokenExpiredError
from contexts.identity.application.ports.outbound import IdentityProvider
from shared_kernel.adapters.context import CurrentUser, CurrentUserContext

_BEARER = "Bearer "


def _problem_response(status: int, code: str, title: str, **extra: Any) -> JSONResponse:
    problem = ProblemDetail(status=status, code=code, title=title, **extra)
    return JSONResponse(
        content=problem.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate the bearer token and populate :class:`CurrentUserContext`."""

    def __init__(
        self,
        app: Any,
        *,
        identity_provider: IdentityProvider,
        is_unauthenticated_fn: Callable[[str, str], bool] = is_unauthenticated,
        is_no_tenant_required_fn: Callable[[str, str], bool] = is_no_tenant_required,
    ) -> None:
        super().__init__(app)
        self._idp = identity_provider
        self._is_unauthenticated = is_unauthenticated_fn
        self._is_no_tenant_required = is_no_tenant_required_fn

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method.upper()
        path = request.url.path

        if self._is_unauthenticated(method, path):
            return await call_next(request)

        header = request.headers.get("authorization") or request.headers.get("Authorization")
        if not header or not header.startswith(_BEARER):
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="Missing or malformed Authorization header",
            )

        token = header[len(_BEARER) :].strip()
        if not token:
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="Empty bearer token",
            )

        try:
            claims = await self._idp.verify_token(token=token)
        except TokenExpiredError as exc:
            return _problem_response(
                401,
                "auth.token_expired",
                "Token expired",
                detail=str(exc) or None,
            )
        except Exception:
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="Token verification failed",
            )

        sub_raw = claims.get("sub")
        if not isinstance(sub_raw, str) or not sub_raw:
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="Token is missing the 'sub' claim",
            )

        try:
            user_id = UUID(sub_raw)
        except (ValueError, AttributeError):
            return _problem_response(
                401,
                "auth.invalid_credentials",
                "Invalid credentials",
                detail="'sub' claim is not a UUID",
            )

        email_raw = claims.get("email", "")
        email = email_raw if isinstance(email_raw, str) else ""

        active_tenant_raw = claims.get("custom:active_tenant")
        active_tenant: str | None
        if isinstance(active_tenant_raw, str) and active_tenant_raw != "":
            active_tenant = active_tenant_raw
        else:
            active_tenant = None

        if active_tenant is None and not self._is_no_tenant_required(method, path):
            # Audit F-030: detail SHALL be a generic Spanish message;
            # the internal claim path is not user-facing and pairs
            # poorly with token-type confusion attacks.
            return _problem_response(
                403,
                "tenant.required",
                "Acceso denegado",
                detail="Acceso denegado: empresa no seleccionada.",
            )

        current_user = CurrentUser(
            user_id=user_id,
            email=email,
            external_sub=sub_raw,
            active_tenant=active_tenant,
        )
        CurrentUserContext.set(current_user)
        try:
            return await call_next(request)
        finally:
            CurrentUserContext.clear()


__all__ = ["AuthMiddleware"]

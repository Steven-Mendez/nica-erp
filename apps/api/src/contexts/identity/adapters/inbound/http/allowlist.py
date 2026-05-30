"""Path allowlists for the authentication middleware.

Pure data + the two predicate helpers ``is_unauthenticated`` and
``is_no_tenant_required``. Kept side-effect-free so the middleware (and
tests) can import without pulling in FastAPI.

The middleware strips a leading ``/api`` prefix before matching so the
same allowlist works in both the local route layout (routes at root) and
the AWS layout where CloudFront's ``/api/*`` behaviour forwards the full
path to the ALB.
"""

from __future__ import annotations

# (method, path) tuples that bypass JWT validation entirely.
UNAUTHENTICATED_EXACT: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/v1/auth/register"),
        ("POST", "/v1/auth/confirm-signup"),
        ("POST", "/v1/auth/resend-code"),
        ("POST", "/v1/auth/login"),
        ("POST", "/v1/auth/refresh"),
        ("POST", "/v1/auth/password/forgot"),
        ("POST", "/v1/auth/password/reset"),
        ("GET", "/healthz"),
        ("GET", "/readyz"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
        ("GET", "/redoc"),
    }
)

# Invitation preview endpoint: GET /v1/invitations/{token}/preview is
# public per ADR-0031 so the pre-signup screen can render the invited
# email + organization name before the recipient has an account.
NO_AUTH_INVITATION_PREVIEW_PREFIX: str = "/v1/invitations/"
NO_AUTH_INVITATION_PREVIEW_SUFFIX: str = "/preview"

# Switching the active tenant happens by definition before the JWT
# carries one — the response IS the new JWT. The route must therefore
# be reachable with a tenantless bearer token.
NO_TENANT_SWITCH_PREFIX: str = "/v1/tenants/"
NO_TENANT_SWITCH_SUFFIX: str = "/switch"

# Authenticated routes a JWT with an empty / missing ``custom:active_tenant``
# is still allowed to call. Everything else returns 403 ``tenant.required``
# until the user picks (or creates) a tenant.
NO_TENANT_REQUIRED: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/v1/me"),
        ("PATCH", "/v1/me"),
        ("GET", "/v1/tenants/me"),
        ("POST", "/v1/auth/logout"),
        ("POST", "/v1/auth/change-password"),
        ("POST", "/v1/tenants"),
        # Hash-fragment accept endpoint (ADR-0031): authenticated user
        # without an active tenant may still accept an invitation.
        ("POST", "/v1/invitations/accept"),
    }
)


def _strip_api_prefix(path: str) -> str:
    """Drop a leading ``/api`` segment so allowlists are deployment-agnostic."""

    if path == "/api":
        return "/"
    if path.startswith("/api/"):
        return path[len("/api") :]
    return path


def is_unauthenticated(method: str, path: str) -> bool:
    """Return True if the middleware should skip JWT validation for this request."""

    upper = method.upper()
    normalised = _strip_api_prefix(path)
    if (upper, normalised) in UNAUTHENTICATED_EXACT:
        return True
    if (
        upper == "GET"
        and normalised.startswith(NO_AUTH_INVITATION_PREVIEW_PREFIX)
        and normalised.endswith(NO_AUTH_INVITATION_PREVIEW_SUFFIX)
        and len(normalised)
        > len(NO_AUTH_INVITATION_PREVIEW_PREFIX) + len(NO_AUTH_INVITATION_PREVIEW_SUFFIX)
    ):
        return True
    return False


def is_no_tenant_required(method: str, path: str) -> bool:
    """Return True if the route is reachable without an ``active_tenant`` claim."""

    upper = method.upper()
    normalised = _strip_api_prefix(path)
    if (upper, normalised) in NO_TENANT_REQUIRED:
        return True
    if (
        upper == "POST"
        and normalised.startswith(NO_TENANT_SWITCH_PREFIX)
        and normalised.endswith(NO_TENANT_SWITCH_SUFFIX)
        and len(normalised) > len(NO_TENANT_SWITCH_PREFIX) + len(NO_TENANT_SWITCH_SUFFIX)
    ):
        return True
    return False


__all__ = [
    "NO_AUTH_INVITATION_PREVIEW_PREFIX",
    "NO_AUTH_INVITATION_PREVIEW_SUFFIX",
    "NO_TENANT_REQUIRED",
    "NO_TENANT_SWITCH_PREFIX",
    "NO_TENANT_SWITCH_SUFFIX",
    "UNAUTHENTICATED_EXACT",
    "is_no_tenant_required",
    "is_unauthenticated",
]

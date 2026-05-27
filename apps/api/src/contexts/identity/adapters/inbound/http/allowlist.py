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

# (method, prefix) tuples for routes whose path is parametric. The middleware
# matches when ``path.startswith(prefix)`` AND the path's suffix exactly
# equals "/accept" — this scopes the allowance to ``POST
# /v1/invitations/{token}/accept`` without opening up the rest of the
# ``/v1/invitations`` namespace.
UNAUTHENTICATED_INVITATION_ACCEPT_PREFIX: str = "/v1/invitations/"
UNAUTHENTICATED_INVITATION_ACCEPT_SUFFIX: str = "/accept"

# Authenticated routes a JWT with an empty / missing ``custom:active_tenant``
# is still allowed to call. Everything else returns 403 ``tenant.required``
# until the user picks (or creates) a tenant.
NO_TENANT_REQUIRED: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/v1/me"),
        ("PATCH", "/v1/me"),
        ("POST", "/v1/auth/logout"),
        ("POST", "/v1/auth/change-password"),
        ("POST", "/v1/tenants"),
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
        upper == "POST"
        and normalised.startswith(UNAUTHENTICATED_INVITATION_ACCEPT_PREFIX)
        and normalised.endswith(UNAUTHENTICATED_INVITATION_ACCEPT_SUFFIX)
        and len(normalised)
        > len(UNAUTHENTICATED_INVITATION_ACCEPT_PREFIX)
        + len(UNAUTHENTICATED_INVITATION_ACCEPT_SUFFIX)
    ):
        return True
    return False


def is_no_tenant_required(method: str, path: str) -> bool:
    """Return True if the route is reachable without an ``active_tenant`` claim."""

    return (method.upper(), _strip_api_prefix(path)) in NO_TENANT_REQUIRED


__all__ = [
    "NO_TENANT_REQUIRED",
    "UNAUTHENTICATED_EXACT",
    "UNAUTHENTICATED_INVITATION_ACCEPT_PREFIX",
    "UNAUTHENTICATED_INVITATION_ACCEPT_SUFFIX",
    "is_no_tenant_required",
    "is_unauthenticated",
]

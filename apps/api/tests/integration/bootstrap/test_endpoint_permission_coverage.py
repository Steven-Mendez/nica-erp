"""Sprint-gate test — every non-public route declares require(...) or is allowlisted."""

from __future__ import annotations

from fastapi.routing import APIRoute

from bootstrap.api import create_app
from bootstrap.dependencies import require
from contexts.identity.adapters.inbound.http.allowlist import (
    NO_AUTH_INVITATION_PREVIEW_PREFIX,
    NO_AUTH_INVITATION_PREVIEW_SUFFIX,
    NO_TENANT_REQUIRED,
    UNAUTHENTICATED_EXACT,
)

# Routes that have no permission gate by design: public auth flows, /me,
# tenant creation (chicken-and-egg: no tenant exists yet), tenant switch
# (the use case validates membership inline), the public health probes,
# and the tenant picker. The set MUST be minimal.
_ALLOWED_NO_PERMISSION_GATE: set[tuple[str, str]] = (
    {(m, p) for (m, p) in UNAUTHENTICATED_EXACT}
    | {(m, p) for (m, p) in NO_TENANT_REQUIRED}
    | {("POST", "/v1/tenants/{tenant_id}/switch")}
)


def _is_invitation_preview(method: str, path: str) -> bool:
    return (
        method == "GET"
        and path.startswith(NO_AUTH_INVITATION_PREVIEW_PREFIX)
        and path.endswith(NO_AUTH_INVITATION_PREVIEW_SUFFIX)
        and len(path)
        > len(NO_AUTH_INVITATION_PREVIEW_PREFIX) + len(NO_AUTH_INVITATION_PREVIEW_SUFFIX)
    )


def _route_uses_require(route: APIRoute) -> bool:
    """Return True if any Depends in the route's graph wraps ``require(...)``."""

    # Each ``require(*codes)`` call builds a closure named ``_check`` —
    # check the dependant tree for any callable whose __qualname__ matches.
    for dep in route.dependant.dependencies:
        if dep.call is None:
            continue
        qualname = getattr(dep.call, "__qualname__", "")
        if qualname.endswith("require.<locals>._check"):
            return True
        # Walk nested dependants
        if dep.dependencies:
            for sub in dep.dependencies:
                if sub.call is None:
                    continue
                sub_qual = getattr(sub.call, "__qualname__", "")
                if sub_qual.endswith("require.<locals>._check"):
                    return True
    return False


def test_all_endpoints_require_permission() -> None:
    app = create_app()
    failures: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or {"GET"}:
            method_u = method.upper()
            path = route.path
            key = (method_u, path)
            if key in _ALLOWED_NO_PERMISSION_GATE:
                continue
            if _is_invitation_preview(method_u, path):
                continue
            if _route_uses_require(route):
                continue
            failures.append(key)
    assert not failures, f"Routes without a permission gate and not on the allowlist: {failures}"


def test_require_is_importable() -> None:
    # Smoke check: the dependency factory itself can be called.
    dep = require("tenant:read")
    assert callable(dep)

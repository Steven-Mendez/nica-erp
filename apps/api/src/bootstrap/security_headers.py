# apps/api/src/bootstrap/security_headers.py
"""Baseline security headers for every HTTP response.

CloudFront fronts the API in AWS but carries no response-headers policy
for the `/api/*` behavior, so the origin owns these headers. They are
equally valid served directly by uvicorn in local dev.

`Cache-Control: no-store` is restricted to the auth endpoints: their
response bodies carry token material that must never land in a browser
or proxy cache, while the rest of the API keeps its default caching
semantics (CloudFront already disables caching for `/api/*`).

No Content-Security-Policy here — Swagger UI under `/docs` loads its
assets from a CDN and a strict CSP would break it. No
Strict-Transport-Security either — HSTS belongs at the TLS-terminating
edge, not an origin that also serves plain HTTP locally.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_BASELINE_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "no-referrer"),
)


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware appending security headers via ``setdefault``.

    ``setdefault`` (not overwrite) so a handler that deliberately sets
    one of these headers wins.
    """

    def __init__(self, app: ASGIApp, *, auth_path_prefix: str) -> None:
        self._app = app
        self._auth_path_prefix = auth_path_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope["path"]
        is_auth_path = path.startswith(self._auth_path_prefix)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _BASELINE_HEADERS:
                    headers.setdefault(name, value)
                if is_auth_path:
                    headers.setdefault("cache-control", "no-store")
            await send(message)

        await self._app(scope, receive, send_with_headers)


__all__ = ["SecurityHeadersMiddleware"]

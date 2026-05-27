"""HTTP inbound adapter for the identity context.

Mounts FastAPI routes for ``/v1/auth/*`` and ``/v1/me``, installs the
authentication middleware, and maps application-layer errors to RFC-7807
problem details.
"""

from __future__ import annotations

from contexts.identity.adapters.inbound.http.middleware import AuthMiddleware
from contexts.identity.adapters.inbound.http.router import router

__all__ = ["AuthMiddleware", "router"]

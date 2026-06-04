# apps/api/src/bootstrap/api.py
"""FastAPI app factory, `/healthz`, identity router + auth middleware.

CORS is needed only for local dev where the Vite server (:5173) calls the
API (:8000) across origins. In production the SPA and API share a single
origin behind CloudFront, so the middleware is a no-op there.

Route prefix: in AWS the CloudFront `/api/*` behavior forwards the full
path to the ALB without stripping the prefix, so the API mounts its routes
under `/api` when `app_env == "aws"`. Locally the routes mount at root.

Middleware order: ``AuthMiddleware`` is registered **before**
``CORSMiddleware``. Starlette runs middleware in reverse order of
addition (last-added is outermost), so the resulting stack has CORS as
the OUTER layer. That ordering ensures the 401 emitted by the auth layer
on a missing/invalid token still carries the
``access-control-allow-origin`` header the SPA needs to read the
problem body — see ``openspec/changes/add-identity-context/specs/api-bootstrap``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from bootstrap.container import (
    build_identity_provider_for_middleware,
    build_request_uow,
)
from bootstrap.db import get_uow
from bootstrap.settings import get_settings
from contexts.identity.adapters.inbound.http.allowlist import is_unauthenticated
from contexts.identity.adapters.inbound.http.errors import register_exception_handlers
from contexts.identity.adapters.inbound.http.middleware import AuthMiddleware
from contexts.identity.adapters.inbound.http.router import router as identity_router
from contexts.tenants.adapters.inbound.http.errors import (
    register_tenants_exception_handlers,
)
from contexts.tenants.adapters.inbound.http.middleware import TenantMiddleware
from contexts.tenants.adapters.inbound.http.router import (
    public_router as tenants_public_router,
)
from contexts.tenants.adapters.inbound.http.router import (
    router as tenants_router,
)
from shared_kernel.application.unit_of_work import UnitOfWork

# Rendered as Markdown in Swagger UI and ReDoc.
API_DESCRIPTION = """
**nica-erp** — multi-tenant ERP for Nicaraguan businesses.

Every endpoint requires `Authorization: Bearer <jwt>` unless explicitly
marked public.

Errors follow RFC 7807 (`application/problem+json`) with
a stable `code` field. Routes are versioned under `/v1`; breaking
changes ship under new prefixes.

Mutations that are unsafe to retry
require `Idempotency-Key: <uuid>`.
"""

# Order here is the order the tags render in Swagger UI / ReDoc.
TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "auth",
        "description": (
            "Public authentication endpoints: signup, confirm, login, refresh, "
            "password reset, change-password, logout."
        ),
    },
    {
        "name": "me",
        "description": (
            "Authenticated user profile. Reachable with a JWT that has no "
            "`custom:active_tenant` claim yet (used by the post-login picker)."
        ),
    },
    {
        "name": "system",
        "description": "Operational probes used by load balancers and oncall.",
    },
]


class HealthzResponse(BaseModel):
    """Liveness probe payload. `db` is `"ok"` only after a `SELECT 1` succeeds."""

    status: str = Field(examples=["ok"])
    version: str = Field(examples=["0.1.0"])
    git_sha: str = Field(examples=["a1b2c3d"])
    db: str = Field(examples=["ok"])
    alembic_revision: str | None = Field(default=None, examples=["0002_identity"])


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="nica-erp",
        summary="Multi-tenant Nicaraguan ERP — HTTP API",
        description=API_DESCRIPTION,
        version=settings.version,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Order matters: Starlette runs middleware in reverse order of
    # addition (last-added = outermost). Adding TenantMiddleware FIRST
    # places it INSIDE the AuthMiddleware layer, so Auth runs before
    # Tenant and populates CurrentUserContext. CORS is added last so it
    # ends up OUTERMOST and can decorate 401s with allow-origin headers.
    app.add_middleware(
        TenantMiddleware,
        uow_factory=build_request_uow,
    )
    app.add_middleware(
        AuthMiddleware,
        identity_provider=build_identity_provider_for_middleware(),
    )

    # CloudFront serves the SPA and the API from a single origin in AWS,
    # so cross-origin requests never reach the API. Skipping the middleware
    # entirely (instead of mounting it with an empty allow-list) keeps
    # responses free of misleading Vary / preflight headers.
    if settings.app_env != "aws":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            # Audit F-005: expose Retry-After (already used by the
            # lockout responses) and Set-Cookie (so the browser stores
            # the httpOnly refresh-token cookie). The SPA itself cannot
            # read Set-Cookie via JS — exposing it is necessary for
            # the browser's cookie jar to accept it on cross-origin
            # responses when credentials are enabled.
            expose_headers=["set-cookie", "retry-after"],
        )

    register_exception_handlers(app)
    register_tenants_exception_handlers(app)

    @app.exception_handler(Exception)
    async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
            },
            status_code=500,
            media_type="application/problem+json",
        )

    router = APIRouter()

    @router.get(
        "/healthz",
        response_model=HealthzResponse,
        tags=["system"],
        summary="Liveness + DB probe",
        response_description="Service is up and the database is reachable",
    )
    async def healthz(uow: UnitOfWork = Depends(get_uow)) -> dict[str, Any]:
        """Run a trivial `SELECT 1` and return the current Alembic head."""

        async with uow.begin() as session:
            await session.execute(text("SELECT 1"))
            rev = await session.execute(text("SELECT version_num FROM alembic_version"))
            revision = rev.scalar_one_or_none()
        return {
            "status": "ok",
            "version": settings.version,
            "git_sha": settings.git_sha,
            "db": "ok",
            "alembic_revision": revision,
        }

    prefix = "/api" if settings.app_env == "aws" else ""
    app.include_router(router, prefix=prefix)
    app.include_router(identity_router, prefix=prefix)
    app.include_router(tenants_router, prefix=prefix)
    app.include_router(tenants_public_router, prefix=prefix)

    _install_bearer_security(app)
    return app


def _install_bearer_security(app: FastAPI) -> None:
    """Expose the `Authorize` button in Swagger UI with a JWT bearer scheme.

    Applies `bearerAuth` globally so operations show the lock icon; clears
    `security` on routes the auth middleware allowlists as public so they
    are not gated by the picker.
    """

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )

        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {})["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste the access token issued by `/v1/auth/login`.",
        }
        schema["security"] = [{"bearerAuth": []}]

        for path, methods in schema.get("paths", {}).items():
            for method, operation in methods.items():
                if method.upper() not in {
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "HEAD",
                    "OPTIONS",
                }:
                    continue
                if is_unauthenticated(method, path):
                    operation["security"] = []

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


app = create_app()

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

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from bootstrap.container import build_identity_provider_for_middleware
from bootstrap.db import get_uow
from bootstrap.settings import get_settings
from contexts.identity.adapters.inbound.http.errors import register_exception_handlers
from contexts.identity.adapters.inbound.http.middleware import AuthMiddleware
from contexts.identity.adapters.inbound.http.router import router as identity_router
from shared_kernel.application.unit_of_work import UnitOfWork

# Rendered as Markdown in Swagger UI and ReDoc. Keep it short and link
# out to the canonical docs in the repo — the OpenAPI page is a catalogue,
# not a duplicate of `docs/`.
API_DESCRIPTION = """
HTTP API for **nica-erp**, a multi-tenant Nicaraguan ERP.

* Auth: `Authorization: Bearer <jwt>` on every request unless listed
  as public — see `docs/08-api-conventions.md`.
* Errors: RFC 7807 problem details (`application/problem+json`) with a
  stable `code` field — see [ADR-0015](https://github.com/stevenwerr/nica-erp/blob/main/docs/adr/0015-rfc7807-errors.md).
* Versioning: `/v1` prefix; breaking changes ship as `/v2` per
  [ADR-0027](https://github.com/stevenwerr/nica-erp/blob/main/docs/adr/0027-api-versioning.md).
* Idempotency: `Idempotency-Key: <uuid>` is required on dangerous-to-retry
  mutating endpoints.
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
        contact={
            "name": "nica-erp maintainers",
            "url": "https://github.com/stevenwerr/nica-erp",
        },
        license_info={
            "name": "MIT",
            "url": "https://github.com/stevenwerr/nica-erp/blob/main/LICENSE",
        },
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Order matters: register AuthMiddleware first so CORSMiddleware ends up
    # OUTERMOST (Starlette runs middleware in reverse order of addition).
    # That way the CORS layer decorates 401s emitted by the auth layer with
    # the SPA's ``access-control-allow-origin`` header.
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
        )

    register_exception_handlers(app)

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
    return app


app = create_app()

"""FastAPI app factory and /healthz endpoint.

CORS is needed only for local dev where the Vite server (:5173) calls the
API (:8000) across origins. In production the SPA and API share a single
origin behind CloudFront, so the middleware is a no-op there.

Route prefix: in AWS the CloudFront `/api/*` behavior forwards the full
path to the ALB without stripping the prefix, so the API mounts its routes
under `/api` when `app_env == "aws"`. Locally the routes mount at root.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from bootstrap.db import get_uow
from bootstrap.settings import get_settings
from shared_kernel.application.unit_of_work import UnitOfWork


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="nica-erp",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
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

    router = APIRouter()

    @router.get("/healthz")
    async def healthz(uow: UnitOfWork = Depends(get_uow)) -> dict[str, Any]:
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

    app.include_router(router, prefix="/api" if settings.app_env == "aws" else "")
    return app


app = create_app()

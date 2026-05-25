"""FastAPI app factory and /healthz endpoint.

CORS is needed only for local dev where the Vite server (:5173) calls the API
(:8000) across origins. In production the SPA and API share a single origin
behind CloudFront, so the middleware is a no-op there.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
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

    return app


app = create_app()

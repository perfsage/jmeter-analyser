"""FastAPI application factory — mounts routers, lifespan, and static files."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from perfsage.api import ai, exports, jobs, reports, uploads
from perfsage.api import settings as settings_router
from perfsage.config import get_settings
from perfsage.web.views import router as web_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Create runtime directories and perform startup/shutdown tasks."""
    cfg = get_settings()
    for sub in ("uploads", "exports", "cache", "parquet"):
        (cfg.data_dir / sub).mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    """Construct and return the FastAPI application."""
    application = FastAPI(
        title="PerfSage JMeter Analyser",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Static assets
    application.mount(
        "/static",
        StaticFiles(directory="perfsage/web/static"),
        name="static",
    )

    # API routers
    for router in (
        reports.router,
        uploads.router,
        jobs.router,
        settings_router.router,
        ai.router,
        exports.router,
    ):
        application.include_router(router, prefix="/api")

    # Server-rendered HTMX views
    application.include_router(web_router)

    @application.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

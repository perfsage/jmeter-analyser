"""FastAPI application factory — mounts routers, lifespan, and static files."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from perfsage.api import ai, exports, jobs, reports, uploads
from perfsage.api import settings as settings_router
from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import JobStatus, get_engine, get_session
from perfsage.core.storage.repos import JobRepo
from perfsage.web.views import router as web_router


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[handler],
        force=True,
    )


_ERROR_PAGE_STYLE = (
    "font-family:sans-serif;background:#F6F1E7;color:#0B1F3A;"
    "display:flex;flex-direction:column;align-items:center;"
    "justify-content:center;height:100vh;margin:0"
)

_404_HTML = f"""<html><body style="{_ERROR_PAGE_STYLE}">
    <h1 style="font-size:3rem">404</h1>
    <p>Page not found.</p>
    <a href="/" style="color:#D4A857">&#8592; Back to Dashboard</a>
</body></html>"""

_500_HTML = f"""<html><body style="{_ERROR_PAGE_STYLE}">
    <h1 style="font-size:3rem">500</h1>
    <p>Internal server error. Please try again.</p>
    <a href="/" style="color:#D4A857">&#8592; Back to Dashboard</a>
</body></html>"""


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create DB + directories, connect Redis, recover interrupted jobs."""
    cfg = get_settings()
    setup_logging(cfg.debug)

    logger = logging.getLogger(__name__)
    logger.info("PerfSage starting up", extra={"debug": cfg.debug})

    # Ensure data subdirectories exist.
    for sub in ("uploads", "exports", "cache", "parquet"):
        (cfg.data_dir / sub).mkdir(parents=True, exist_ok=True)

    # Initialise database and expose engine via app.state.
    engine = get_engine(cfg.database_url)
    application.state.engine = engine

    # Connect arq Redis pool and expose via app.state.
    from perfsage.core.jobs.queue import get_redis_pool
    from perfsage.core.storage.files import FileStore

    redis_pool = await get_redis_pool(cfg.redis_url)
    application.state.redis = redis_pool

    # Restart recovery: jobs that were RUNNING when the server last died are
    # reset to QUEUED and re-enqueued so they are not silently abandoned.
    fs = FileStore(cfg.data_dir)
    with get_session(engine) as session:
        interrupted = JobRepo(session).get_active_jobs()

    for job in interrupted:
        with get_session(engine) as session:
            from perfsage.core.storage.db import Job

            j = session.get(Job, job.id)
            if j is not None:
                j.status = JobStatus.QUEUED
                session.add(j)
                session.commit()

        upload_path = str(fs.upload_path(job.id))
        await redis_pool.enqueue_job(
            "ingest_report_task",
            job_id=job.id,
            report_id=job.report_id,
            upload_path=upload_path,
        )

    yield

    # Shutdown: close Redis pool.
    await redis_pool.aclose()
    logger.info("PerfSage shutdown complete")


def create_app() -> FastAPI:
    """Construct and return the FastAPI application."""
    application = FastAPI(
        title="PerfSage JMeter Analyser",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Static assets — only mount if the directory exists to avoid startup errors.
    static_path = Path(__file__).parent / "web" / "static"
    if static_path.is_dir():
        application.mount(
            "/static",
            StaticFiles(directory=static_path),
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

    @application.get("/healthz", tags=["ops"], response_model=dict[str, str])
    async def healthz(cfg: Settings = Depends(get_settings)) -> dict[str, str]:  # noqa: B008
        return {
            "status": "ok",
            "version": "0.1.0",
            "data_dir": str(cfg.data_dir),
        }

    @application.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse:
        return HTMLResponse(content=_404_HTML, status_code=404)

    @application.exception_handler(500)
    async def server_error_handler(request: Request, exc: Exception) -> HTMLResponse:
        return HTMLResponse(content=_500_HTML, status_code=500)

    return application


app = create_app()

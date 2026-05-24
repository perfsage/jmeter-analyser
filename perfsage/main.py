"""FastAPI application factory — mounts routers, lifespan, and static files."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from perfsage.api import ai, exports, jobs, reports, uploads
from perfsage.api import settings as settings_router
from perfsage.config import get_settings
from perfsage.core.storage.db import JobStatus, get_engine, get_session
from perfsage.core.storage.repos import JobRepo
from perfsage.web.views import router as web_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create DB + directories, connect Redis, recover interrupted jobs."""
    cfg = get_settings()

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
        # Reset to QUEUED in DB.
        with get_session(engine) as session:
            from perfsage.core.storage.db import Job

            j = session.get(Job, job.id)
            if j is not None:
                j.status = JobStatus.QUEUED
                session.add(j)
                session.commit()

        # Re-enqueue: reconstruct upload path from the convention.
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
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

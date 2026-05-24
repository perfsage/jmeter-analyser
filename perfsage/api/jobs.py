"""REST endpoints for background job status and SSE progress streaming."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from perfsage.config import Settings, get_settings
from perfsage.core.storage.db import get_session
from perfsage.core.storage.repos import JobRepo

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/events")
async def job_events_sse(
    job_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> EventSourceResponse:
    """SSE endpoint — subscribes to Redis pubsub ``job:{job_id}``.

    Streams progress events until phase is ``done`` or ``error``.
    Falls back to polling the DB every 2 s if Redis is unavailable.
    """
    engine = request.app.state.engine

    async def _event_generator() -> AsyncGenerator[dict[str, str], None]:
        # ── Try Redis pubsub first ────────────────────────────────────────
        redis_client: aioredis.Redis | None = None
        try:
            redis_client = aioredis.from_url(  # type: ignore[no-untyped-call]
                settings.redis_url, decode_responses=True
            )
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"job:{job_id}")

            while True:
                if await request.is_disconnected():
                    return

                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is not None:
                    data: str = msg["data"]
                    yield {"data": data}
                    try:
                        parsed = json.loads(data)
                        if parsed.get("phase") in ("done", "error"):
                            return
                    except json.JSONDecodeError:
                        pass

        except Exception:
            # Redis unavailable — fall through to DB polling.
            pass
        finally:
            if redis_client is not None:
                try:
                    await redis_client.aclose()
                except Exception:
                    pass

        # ── Fallback: poll DB every 2 s ───────────────────────────────────
        while True:
            if await request.is_disconnected():
                return

            with get_session(engine) as session:
                job = JobRepo(session).get(job_id)

            if job is None:
                return

            yield {
                "data": json.dumps(
                    {"pct": job.progress_pct, "phase": job.phase, "message": job.message}
                )
            }

            if job.phase in ("done", "error") or job.status.value in ("done", "failed"):
                return

            await asyncio.sleep(2)

    return EventSourceResponse(_event_generator())


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    request: Request,
) -> dict[str, object]:
    """Return the current status of a job from the database."""
    engine = request.app.state.engine

    with get_session(engine) as session:
        job = JobRepo(session).get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    return {
        "id": job.id,
        "report_id": job.report_id,
        "status": job.status.value,
        "progress_pct": job.progress_pct,
        "phase": job.phase,
        "message": job.message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        "error_text": job.error_text,
    }

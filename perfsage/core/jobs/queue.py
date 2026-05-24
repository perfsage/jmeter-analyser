"""arq worker settings and Redis pool factory."""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from perfsage.core.jobs.tasks import ingest_report_task


async def get_redis_pool(redis_url: str) -> ArqRedis:
    """Create and return an arq Redis connection pool."""
    settings = RedisSettings.from_dsn(redis_url)
    return await create_pool(settings)


async def _startup(ctx: dict[str, object]) -> None:  # noqa: RUF029
    pass


async def _shutdown(ctx: dict[str, object]) -> None:  # noqa: RUF029
    pass


class WorkerSettings:
    """arq WorkerSettings — run via ``arq perfsage.core.jobs.queue.WorkerSettings``."""

    functions = [ingest_report_task]
    on_startup = _startup
    on_shutdown = _shutdown
    max_jobs = 4
    job_timeout = 7200  # 2 hours for huge files
    health_check_interval = 30

    # redis_settings resolved lazily to avoid calling get_settings() at import time
    # (which would fail if PERFSAGE_SECRET is not set in the environment).
    @classmethod
    def build_redis_settings(cls) -> RedisSettings:
        from perfsage.config import get_settings

        return RedisSettings.from_dsn(get_settings().redis_url)

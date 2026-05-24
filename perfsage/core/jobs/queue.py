"""arq queue configuration and WorkerSettings."""

from arq.connections import RedisSettings

from perfsage.config import get_settings
from perfsage.core.jobs.tasks import parse_and_analyse


async def startup(ctx: dict[str, object]) -> None:
    """Initialise shared resources for the worker process."""
    pass


async def shutdown(ctx: dict[str, object]) -> None:
    """Clean up shared resources on worker shutdown."""
    pass


class WorkerSettings:
    """arq WorkerSettings — referenced by `arq perfsage.core.jobs.queue.WorkerSettings`."""

    functions = [parse_and_analyse]
    on_startup = startup
    on_shutdown = shutdown

    @property
    def redis_settings(self) -> RedisSettings:
        """Build RedisSettings from application config."""
        url = get_settings().redis_url
        return RedisSettings.from_dsn(url)

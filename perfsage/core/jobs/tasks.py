"""arq background task definitions for parse-and-analyse pipeline."""


async def parse_and_analyse(ctx: dict[str, object], file_path: str, report_id: int) -> None:
    """Parse the uploaded JMeter file and run the full analysis pipeline.

    Publishes progress events to Redis pubsub channel ``report:{report_id}:progress``.
    """
    raise NotImplementedError

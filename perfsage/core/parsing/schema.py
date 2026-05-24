"""Pydantic schema for a normalised JMeter sample row."""

from pydantic import BaseModel


class JMeterSample(BaseModel):
    """One row from a JMeter result file after normalisation."""

    timestamp_ms: int
    elapsed_ms: int
    label: str
    response_code: str
    success: bool
    bytes_received: int
    bytes_sent: int
    thread_name: str
    url: str | None = None
    latency_ms: int | None = None
    connect_ms: int | None = None

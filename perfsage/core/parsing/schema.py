"""Canonical internal schema for a JMeter sample row.

All loaders (CSV, XML) normalise their output to this schema before
writing Parquet.  Arrow schema is used for storage; COLUMN_ALIASES maps
every JMeter column-name variant (across versions) to the canonical name.
"""

from __future__ import annotations

import pyarrow as pa

CANONICAL_FIELDS: list[str] = [
    "timestamp_ms",
    "elapsed",
    "label",
    "response_code",
    "response_message",
    "thread_name",
    "success",
    "failure_message",
    "bytes",
    "sent_bytes",
    "grp_threads",
    "all_threads",
    "url",
    "latency",
    "idle_time",
    "connect",
]

CANONICAL_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("timestamp_ms", pa.int64()),
        pa.field("elapsed", pa.int64()),
        pa.field("label", pa.utf8()),
        pa.field("response_code", pa.utf8()),
        pa.field("response_message", pa.utf8()),
        pa.field("thread_name", pa.utf8()),
        pa.field("success", pa.bool_()),
        pa.field("failure_message", pa.utf8()),
        pa.field("bytes", pa.int64()),
        pa.field("sent_bytes", pa.int64()),
        pa.field("grp_threads", pa.int64()),
        pa.field("all_threads", pa.int64()),
        pa.field("url", pa.utf8()),
        pa.field("latency", pa.int64()),
        pa.field("idle_time", pa.int64()),
        pa.field("connect", pa.int64()),
    ]
)

# Canonical field → list of JMeter CSV column names (case-insensitive).
# Last definition for a given alias wins when building the reverse lookup.
COLUMN_ALIASES: dict[str, list[str]] = {
    "timestamp_ms": ["timeStamp", "timestamp", "ts"],
    "elapsed": ["elapsed", "Elapsed"],
    "label": ["label", "Label", "sampler_label"],
    "response_code": ["responseCode", "response_code"],
    "response_message": ["responseMessage", "response_message"],
    "thread_name": ["threadName", "thread_name"],
    "success": ["success", "Success"],
    "failure_message": ["failureMessage", "failure_message", "errorMessage"],
    "bytes": ["bytes", "Bytes"],
    "sent_bytes": ["sentBytes", "sent_bytes"],
    "grp_threads": ["grpThreads", "grp_threads"],
    "all_threads": ["allThreads", "all_threads"],
    "url": ["URL", "url", "Url"],
    "latency": ["Latency", "latency"],
    "idle_time": ["IdleTime", "idle_time", "idleTime"],
    "connect": ["Connect", "connect"],
}

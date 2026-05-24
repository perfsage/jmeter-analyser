"""Stream a JMeter XML JTL file using lxml.iterparse.

Memory-safe for huge files: each element is cleared immediately after
processing so the XML tree never grows beyond a single in-flight batch.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl
from lxml import etree

from perfsage.core.parsing.cleanup import QuarantinedRow, clean_dataframe

CHUNK_ROWS = 50_000

# JMeter XML attribute name → canonical field name.
_XML_ATTR_MAP: dict[str, str] = {
    "ts": "timestamp_ms",
    "t": "elapsed",
    "lb": "label",
    "rc": "response_code",
    "rm": "response_message",
    "tn": "thread_name",
    "s": "success",
    "by": "bytes",
    "sby": "sent_bytes",
    "ng": "grp_threads",
    "na": "all_threads",
    "lt": "latency",
    "ct": "connect",
}


def _parse_element(elem: Any) -> dict[str, Any]:
    """Extract a canonical-keyed dict from one httpSample / sample element."""
    row: dict[str, Any] = {}
    for xml_attr, canonical in _XML_ATTR_MAP.items():
        val = elem.get(xml_attr)
        if val is not None:
            row[canonical] = val
    # failure_message lives in a <failureMessage> child text node (JMeter 4+).
    fm = elem.find("failureMessage")
    if fm is not None and fm.text:
        row["failure_message"] = fm.text
    # URL may live in a <java.net.URL> child.
    url_el = elem.find("java.net.URL")
    if url_el is not None and url_el.text:
        row["url"] = url_el.text
    # idle_time is not a standard XML attribute; leave absent if missing.
    return row


def _build_chunk_df(batch: list[dict[str, Any]]) -> pl.DataFrame:
    """Convert a list of row-dicts to a Polars DataFrame with string columns."""
    if not batch:
        return pl.DataFrame()
    # Collect all keys that appear in any row.
    all_keys: set[str] = set()
    for row in batch:
        all_keys.update(row.keys())
    columns: dict[str, list[Any]] = {k: [] for k in all_keys}
    for row in batch:
        for key in all_keys:
            columns[key].append(row.get(key))
    return pl.DataFrame({k: pl.Series(v, dtype=pl.Utf8) for k, v in columns.items()})


def stream_xml(
    path: Path,
    chunk_size: int = CHUNK_ROWS,
) -> Iterator[tuple[pl.DataFrame, list[QuarantinedRow]]]:
    """Parse XML JTL using lxml.iterparse, yielding (chunk_df, quarantined).

    Handles both <httpSample> and <sample> elements.  Each element is freed
    immediately after processing to keep memory O(chunk_size).
    """
    context = etree.iterparse(
        str(path),
        events=("end",),
        tag=("httpSample", "sample"),
        recover=True,
    )
    batch: list[dict[str, Any]] = []

    for _event, elem in context:
        row = _parse_element(elem)
        batch.append(row)

        # Free the element and its preceding siblings to prevent tree growth.
        elem.clear()
        parent = elem.getparent()
        if parent is not None:
            while len(parent) > 0 and parent[0] is not elem:
                del parent[0]

        if len(batch) >= chunk_size:
            chunk_df = _build_chunk_df(batch)
            clean, quarantined = clean_dataframe(chunk_df)
            yield clean, quarantined
            batch.clear()

    # Flush remaining rows.
    if batch:
        chunk_df = _build_chunk_df(batch)
        clean, quarantined = clean_dataframe(chunk_df)
        yield clean, quarantined

    del context


def _write_quarantine_parquet(rows: list[QuarantinedRow], path: Path) -> None:
    if rows:
        pl.DataFrame(
            {
                "row_index": [r.row_index for r in rows],
                "reason": [r.reason for r in rows],
                "raw_json": [json.dumps(r.raw, default=str) for r in rows],
            }
        ).write_parquet(path)
    else:
        pl.DataFrame(
            {
                "row_index": pl.Series([], dtype=pl.Int64),
                "reason": pl.Series([], dtype=pl.Utf8),
                "raw_json": pl.Series([], dtype=pl.Utf8),
            }
        ).write_parquet(path)


def load_xml_to_parquet(
    src: Path,
    dest_parquet: Path,
    quarantine_parquet: Path,
) -> tuple[int, int]:
    """Stream XML JTL → dest_parquet (canonical) + quarantine_parquet.

    Returns (parsed_rows, error_rows).
    """
    parsed_rows = 0
    all_quarantined: list[QuarantinedRow] = []
    chunks: list[pl.DataFrame] = []

    for clean, quarantined in stream_xml(src):
        chunks.append(clean)
        parsed_rows += len(clean)
        all_quarantined.extend(quarantined)

    if chunks:
        combined = pl.concat(chunks, rechunk=True)
    else:
        combined = pl.DataFrame()

    combined.write_parquet(dest_parquet)
    _write_quarantine_parquet(all_quarantined, quarantine_parquet)

    return parsed_rows, len(all_quarantined)

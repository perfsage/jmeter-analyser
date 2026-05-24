"""Stream a JMeter CSV JTL file into Parquet, chunk by chunk.

Designed for files >> 1 GB: never loads the whole file into memory at once.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from perfsage.core.parsing.cleanup import QuarantinedRow, clean_dataframe
from perfsage.core.parsing.schema import CANONICAL_FIELDS, CANONICAL_SCHEMA, COLUMN_ALIASES

CHUNK_ROWS = 50_000


def _build_reverse_alias() -> dict[str, str]:
    """Return lowercase-alias → canonical mapping.

    When the same alias appears in multiple canonical lists the last
    definition wins (preserves dict insertion order).
    """
    reverse: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            reverse[alias.lower()] = canonical
    return reverse


_REVERSE_ALIAS: dict[str, str] = _build_reverse_alias()


def map_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Rename JMeter variant column names to canonical names.

    Columns that cannot be mapped to any canonical field are dropped.
    If two source columns would map to the same canonical the first one
    encountered (left-to-right) is kept.
    """
    # Pre-register columns that are already named with a canonical name so we
    # don't accidentally rename a second column to the same canonical and
    # produce a duplicate.
    seen_canonicals: set[str] = {c for c in df.columns if c in CANONICAL_FIELDS}

    rename_map: dict[str, str] = {}
    for col in df.columns:
        if col in seen_canonicals:
            continue  # already canonical — leave it untouched
        canonical = _REVERSE_ALIAS.get(col.lower())
        if canonical is not None and canonical not in seen_canonicals:
            rename_map[col] = canonical
            seen_canonicals.add(canonical)

    if rename_map:
        df = df.rename(rename_map)

    # Keep only columns that are recognised canonical names (deduplicated).
    seen: set[str] = set()
    keep: list[str] = []
    for c in df.columns:
        if c in CANONICAL_FIELDS and c not in seen:
            keep.append(c)
            seen.add(c)
    return df.select(keep)


def stream_csv(
    path: Path,
    delimiter: str = ",",
    chunk_size: int = CHUNK_ROWS,
) -> Iterator[tuple[pl.DataFrame, list[QuarantinedRow]]]:
    """Yield (canonical_chunk_df, quarantined_rows) for each chunk."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        reader = pl.read_csv_batched(
            path,
            separator=delimiter,
            infer_schema_length=0,  # all columns as strings first
            ignore_errors=True,
            batch_size=chunk_size,
            truncate_ragged_lines=True,
        )
    while True:
        batches = reader.next_batches(1)
        if not batches:
            break
        chunk = batches[0]
        if chunk.is_empty():
            continue
        mapped = map_columns(chunk)
        clean, quarantined = clean_dataframe(mapped)
        yield clean, quarantined


def _write_quarantine_parquet(rows: list[QuarantinedRow], path: Path) -> None:
    data: dict[str, list[object]] = {
        "row_index": [r.row_index for r in rows],
        "reason": [r.reason for r in rows],
        "raw_json": [json.dumps(r.raw, default=str) for r in rows],
    }
    if rows:
        pl.DataFrame(data).write_parquet(path)
    else:
        pl.DataFrame(
            {
                "row_index": pl.Series([], dtype=pl.Int64),
                "reason": pl.Series([], dtype=pl.Utf8),
                "raw_json": pl.Series([], dtype=pl.Utf8),
            }
        ).write_parquet(path)


def load_csv_to_parquet(
    src: Path,
    dest_parquet: Path,
    quarantine_parquet: Path,
    delimiter: str = ",",
) -> tuple[int, int]:
    """Stream src CSV → dest_parquet (canonical) + quarantine_parquet.

    Returns (parsed_rows, error_rows).
    """
    parsed_rows = 0
    all_quarantined: list[QuarantinedRow] = []

    dest_parquet.parent.mkdir(parents=True, exist_ok=True)
    quarantine_parquet.parent.mkdir(parents=True, exist_ok=True)

    writer: pq.ParquetWriter | None = None
    try:
        for clean, quarantined in stream_csv(src, delimiter=delimiter):
            parsed_rows += len(clean)
            all_quarantined.extend(quarantined)

            arrow_table = clean.to_arrow()
            present_names = set(arrow_table.schema.names)
            chunk_fields = [f for f in CANONICAL_SCHEMA if f.name in present_names]
            if chunk_fields:
                partial_schema = pa.schema(chunk_fields)
                arrow_table = arrow_table.select(
                    [f.name for f in chunk_fields]
                ).cast(partial_schema)
            if writer is None:
                writer = pq.ParquetWriter(dest_parquet, arrow_table.schema)  # type: ignore[no-untyped-call]
            writer.write_table(arrow_table)  # type: ignore[no-untyped-call]
    finally:
        if writer:
            writer.close()  # type: ignore[no-untyped-call]
        elif not dest_parquet.exists():
            pl.DataFrame().write_parquet(dest_parquet)

    _write_quarantine_parquet(all_quarantined, quarantine_parquet)

    return parsed_rows, len(all_quarantined)

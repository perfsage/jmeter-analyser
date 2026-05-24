"""Clean and validate raw JMeter DataFrames.

Bad rows are collected into a QuarantinedRow list — they are never silently
dropped.  The caller decides what to do with them (write to quarantine
Parquet, log, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import polars as pl


@dataclass
class QuarantinedRow:
    row_index: int
    raw: dict[str, Any]
    reason: str


# ─── low-level normalisation helpers ────────────────────────────────────────


def normalize_timestamp(value: str | int | float) -> int:
    """Convert epoch_ms / epoch_s / datetime string → epoch_ms int64.

    Decision boundary: value > 1e12  →  already epoch_ms.
                       value <= 1e12 →  epoch_s, multiply by 1000.
    """
    if isinstance(value, str):
        stripped = value.strip()
        try:
            numeric: float = float(stripped)
        except ValueError:
            # Try ISO / space-separated datetime strings.
            _formats = (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
            )
            for fmt in _formats:
                try:
                    dt = datetime.strptime(stripped, fmt).replace(  # noqa: DTZ007
                        tzinfo=UTC
                    )
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse timestamp: {value!r}") from None
    else:
        numeric = float(value)

    int_val = int(numeric)
    if int_val > 1_000_000_000_000:
        return int_val
    return int_val * 1000


def normalize_bool(value: str | bool) -> bool:
    """Convert 'true'/'false'/'TRUE'/'FALSE'/0/1 → bool.

    Raises ValueError for unrecognised inputs.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in ("true", "1", "yes"):
        return True
    if lowered in ("false", "0", "no"):
        return False
    raise ValueError(f"Cannot convert {value!r} to bool")


# ─── row-level validation ────────────────────────────────────────────────────


def validate_row(row: dict[str, Any], index: int) -> QuarantinedRow | None:
    """Return QuarantinedRow if the dict row is invalid, else None.

    Required fields: elapsed (present, non-negative), timestamp_ms (present).
    """
    reasons: list[str] = []

    if "elapsed" not in row or row["elapsed"] is None:
        reasons.append("missing required field: elapsed")
    else:
        try:
            e = float(row["elapsed"])
            if e < 0:
                reasons.append(f"elapsed is negative: {row['elapsed']}")
        except (TypeError, ValueError):
            reasons.append(f"elapsed is not numeric: {row['elapsed']!r}")

    if "timestamp_ms" not in row or row["timestamp_ms"] is None:
        reasons.append("missing required field: timestamp_ms")

    if reasons:
        return QuarantinedRow(row_index=index, raw=row, reason="; ".join(reasons))
    return None


# ─── DataFrame-level cleaning ────────────────────────────────────────────────


def clean_dataframe(
    df: pl.DataFrame,
) -> tuple[pl.DataFrame, list[QuarantinedRow]]:
    """Apply all cleanup rules.

    Returns (clean_df, quarantined_rows).  The clean_df has typed columns;
    bad rows (null required fields, negative elapsed) are quarantined.
    """
    # Tag each row with its original position.
    indexed = df.with_row_index("_row_idx")

    # ── timestamp_ms ──────────────────────────────────────────────────────
    if "timestamp_ms" in indexed.columns:

        def _ts(v: Any) -> int | None:
            if v is None:
                return None
            try:
                return normalize_timestamp(v)
            except (ValueError, OverflowError):
                return None

        indexed = indexed.with_columns(
            pl.col("timestamp_ms").map_elements(_ts, return_dtype=pl.Int64)
        )

    # ── success ───────────────────────────────────────────────────────────
    if "success" in indexed.columns:

        def _bool(v: Any) -> bool | None:
            if v is None:
                return None
            try:
                return normalize_bool(v)
            except ValueError:
                return None

        indexed = indexed.with_columns(
            pl.col("success").map_elements(_bool, return_dtype=pl.Boolean)
        )

    # ── elapsed → Int64 ───────────────────────────────────────────────────
    if "elapsed" in indexed.columns:
        indexed = indexed.with_columns(pl.col("elapsed").cast(pl.Int64, strict=False))

    # ── build validity mask ───────────────────────────────────────────────
    conditions: list[pl.Expr] = []
    if "elapsed" in indexed.columns:
        conditions.append(pl.col("elapsed").is_not_null() & (pl.col("elapsed") >= 0))
    if "timestamp_ms" in indexed.columns:
        conditions.append(pl.col("timestamp_ms").is_not_null())

    quarantined: list[QuarantinedRow] = []
    if conditions:
        valid_mask = conditions[0]
        for cond in conditions[1:]:
            valid_mask = valid_mask & cond

        bad_df = indexed.filter(~valid_mask)
        good_df = indexed.filter(valid_mask)

        for row in bad_df.iter_rows(named=True):
            row_idx = int(row["_row_idx"])
            reasons: list[str] = []
            elapsed_val = row.get("elapsed")
            ts_val = row.get("timestamp_ms")
            if elapsed_val is None:
                reasons.append("elapsed is null")
            elif isinstance(elapsed_val, int) and elapsed_val < 0:
                reasons.append(f"elapsed is negative: {elapsed_val}")
            if ts_val is None:
                reasons.append("timestamp_ms is null")
            if not reasons:
                reasons.append("invalid row")
            raw = {k: v for k, v in row.items() if k != "_row_idx"}
            quarantined.append(
                QuarantinedRow(row_index=row_idx, raw=raw, reason="; ".join(reasons))
            )
    else:
        good_df = indexed

    clean = good_df.drop("_row_idx")

    # ── cast remaining numeric columns ────────────────────────────────────
    int64_cols = ["bytes", "sent_bytes", "grp_threads", "all_threads", "latency", "idle_time", "connect"]
    for col in int64_cols:
        if col in clean.columns:
            clean = clean.with_columns(pl.col(col).cast(pl.Int64, strict=False))

    return clean, quarantined

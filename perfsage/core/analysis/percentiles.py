"""DuckDB-backed percentile computations over JMeter samples parquet."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


def _pct_col_name(p: float) -> str:
    if abs(p - 0.999) < 1e-6:
        return "p999"
    return f"p{int(round(p * 100))}"


def compute_percentiles(
    samples_path: Path,
    percentiles: list[float] | None = None,
    groupby_label: bool = True,
) -> pl.DataFrame:
    """Return DataFrame with columns: label (if grouped), count, mean, std, min, max, p50…p999.

    All elapsed values in ms. Uses DuckDB PERCENTILE_CONT for accuracy.
    """
    if percentiles is None:
        percentiles = [0.5, 0.75, 0.90, 0.95, 0.99, 0.999]

    pct_sql = ", ".join(
        f"PERCENTILE_CONT({p}) WITHIN GROUP (ORDER BY elapsed) AS {_pct_col_name(p)}"
        for p in percentiles
    )
    base_aggs = (
        f"COUNT(*)::BIGINT AS count, AVG(elapsed) AS mean, STDDEV_SAMP(elapsed) AS std, "
        f"MIN(elapsed)::BIGINT AS min, MAX(elapsed)::BIGINT AS max, {pct_sql}"
    )

    con = duckdb.connect()
    con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

    if groupby_label:
        sql = f"SELECT label, {base_aggs} FROM samples GROUP BY label ORDER BY label"
    else:
        sql = f"SELECT {base_aggs} FROM samples"

    return con.execute(sql).pl()


def compute_overall_percentiles(samples_path: Path) -> dict[str, float]:
    """Return dict: p50, p75, p90, p95, p99, p999 for all labels combined."""
    df = compute_percentiles(samples_path, groupby_label=False)
    return {col: float(df[col][0]) for col in ["p50", "p75", "p90", "p95", "p99", "p999"]}

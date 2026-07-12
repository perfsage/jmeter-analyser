"""SLO (Service Level Objective) evaluation and Apdex score computation."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl
from sqlmodel import Session

from perfsage.core.analysis.segmentation import get_steady_state_samples

logger = logging.getLogger(__name__)


@dataclass
class SLOConfig:
    p90_ms: float = 1000.0
    p99_ms: float = 3000.0
    error_rate_pct: float = 1.0
    apdex_t: float = 0.5


@dataclass
class SLOResult:
    label: str
    p90_ms: float
    p99_ms: float
    error_rate_pct: float
    apdex_score: float
    p90_compliant: bool
    p99_compliant: bool
    error_rate_compliant: bool
    overall_compliant: bool


def load_slo_config(session: Session) -> SLOConfig:
    """Load the persisted SLO defaults saved via POST /api/settings/slo.

    Falls back to SLOConfig() defaults if nothing has been saved yet, or if
    the stored value is malformed.
    """
    from perfsage.core.storage.repos import AppSettingsRepo

    raw = AppSettingsRepo(session).get("slo_defaults")
    if not raw:
        return SLOConfig()
    try:
        data = json.loads(raw)
        return SLOConfig(**data)
    except (ValueError, TypeError) as exc:
        logger.warning("Malformed slo_defaults setting (%s); using SLOConfig defaults", exc)
        return SLOConfig()


def compute_apdex(
    samples_path: Path,
    t_seconds: float = 0.5,
    f_multiplier: float = 4.0,
) -> pl.DataFrame:
    """Apdex score per label.

    Satisfied:  elapsed <= t_ms
    Tolerating: t_ms < elapsed <= f_ms
    Frustrated: elapsed > f_ms
    Apdex = (Satisfied + Tolerating / 2) / N

    Returns: label, satisfied, tolerating, frustrated, total, apdex_score
    """
    t_ms = t_seconds * 1000.0
    f_ms = f_multiplier * t_ms

    with duckdb.connect() as con:
        con.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")

        return con.execute(
            f"""
            SELECT label,
                   SUM(CASE WHEN elapsed <= {t_ms} THEN 1 ELSE 0 END)::BIGINT AS satisfied,
                   SUM(CASE WHEN elapsed > {t_ms} AND elapsed <= {f_ms} THEN 1 ELSE 0 END)::BIGINT
                       AS tolerating,
                   SUM(CASE WHEN elapsed > {f_ms} THEN 1 ELSE 0 END)::BIGINT AS frustrated,
                   COUNT(*)::BIGINT AS total,
                   (SUM(CASE WHEN elapsed <= {t_ms} THEN 1 ELSE 0 END)
                    + SUM(CASE WHEN elapsed > {t_ms} AND elapsed <= {f_ms} THEN 1 ELSE 0 END)
                      * 0.5) * 1.0 / COUNT(*) AS apdex_score
            FROM samples
            GROUP BY label
            ORDER BY label
            """
        ).pl()


def compute_slo_compliance(
    samples_path: Path,
    config: SLOConfig | None = None,
) -> list[SLOResult]:
    """Check SLO compliance per label using steady-state samples only."""
    if config is None:
        config = SLOConfig()

    steady_df = get_steady_state_samples(samples_path)
    if steady_df.is_empty():
        return []

    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".parquet")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        steady_df.write_parquet(tmp_path)

        with duckdb.connect() as con:
            con.execute(f"CREATE VIEW steady AS SELECT * FROM read_parquet('{tmp_path}')")

            metrics_df = con.execute(
                """
                SELECT label,
                       PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY elapsed) AS p90,
                       PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY elapsed) AS p99,
                       SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                           AS error_rate_pct
                FROM steady
                GROUP BY label
                ORDER BY label
                """
            ).pl()

        apdex_df = compute_apdex(tmp_path, t_seconds=config.apdex_t)
        apdex_map: dict[str, float] = {
            str(row["label"]): float(row["apdex_score"]) for row in apdex_df.to_dicts()
        }

        results: list[SLOResult] = []
        for row in metrics_df.to_dicts():
            label = str(row["label"])
            p90 = float(row["p90"])
            p99 = float(row["p99"])
            error_rate = float(row["error_rate_pct"])
            apdex = apdex_map.get(label, 0.0)

            p90_ok = p90 <= config.p90_ms
            p99_ok = p99 <= config.p99_ms
            error_ok = error_rate <= config.error_rate_pct

            results.append(
                SLOResult(
                    label=label,
                    p90_ms=p90,
                    p99_ms=p99,
                    error_rate_pct=error_rate,
                    apdex_score=apdex,
                    p90_compliant=p90_ok,
                    p99_compliant=p99_ok,
                    error_rate_compliant=error_ok,
                    overall_compliant=p90_ok and p99_ok and error_ok,
                )
            )
    finally:
        tmp_path.unlink(missing_ok=True)

    return results

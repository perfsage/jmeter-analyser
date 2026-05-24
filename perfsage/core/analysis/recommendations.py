"""Rule-based performance recommendations (always-on, no AI required)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import InsightSeverity

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    kind: str
    severity: InsightSeverity
    message: str
    data: dict[str, object] = field(default_factory=dict)


_SEVERITY_ORDER: dict[InsightSeverity, int] = {
    InsightSeverity.CRITICAL: 0,
    InsightSeverity.WARNING: 1,
    InsightSeverity.INFO: 2,
}


def run_all_recommendations(
    samples_path: Path,
    slo_config: SLOConfig | None = None,
) -> list[Recommendation]:
    """Run all recommendation rules. Return list in severity order (critical first).

    Rules:
    1. tail_latency_ratio: p99/p50 > 5 → WARNING; > 10 → CRITICAL
    2. saturation_knee: if knee_point detected → WARNING with RPS value
    3. error_spike: if any bucket > 10% error rate → CRITICAL
    4. slo_violation: if any label fails SLO → CRITICAL
    5. warmup_window: report auto-detected warmup duration (INFO)
    6. high_variability: if CV (std/mean) > 1.0 for any label → WARNING
    7. cold_start_detected: if first 30s error rate >> overall → INFO
    """
    from perfsage.core.analysis.anomalies import detect_knee_point
    from perfsage.core.analysis.metrics import compute_error_series
    from perfsage.core.analysis.percentiles import compute_percentiles
    from perfsage.core.analysis.segmentation import detect_warmup_window
    from perfsage.core.analysis.slo import compute_slo_compliance

    if slo_config is None:
        slo_config = SLOConfig()

    recs: list[Recommendation] = []

    # 1. Tail latency ratio (p99 / p50)
    try:
        pct_df = compute_percentiles(samples_path, groupby_label=True)
        for row in pct_df.to_dicts():
            p50 = float(row.get("p50") or 1)
            p99 = float(row.get("p99") or 0)
            ratio = p99 / max(p50, 1.0)
            label = str(row.get("label", ""))
            if ratio > 10:
                recs.append(
                    Recommendation(
                        kind="tail_latency_ratio",
                        severity=InsightSeverity.CRITICAL,
                        message=(
                            f"Label '{label}': p99/p50 ratio is {ratio:.1f}x (threshold: 10x)"
                        ),
                        data={"label": label, "ratio": ratio, "p50": p50, "p99": p99},
                    )
                )
            elif ratio > 5:
                recs.append(
                    Recommendation(
                        kind="tail_latency_ratio",
                        severity=InsightSeverity.WARNING,
                        message=(
                            f"Label '{label}': p99/p50 ratio is {ratio:.1f}x (threshold: 5x)"
                        ),
                        data={"label": label, "ratio": ratio, "p50": p50, "p99": p99},
                    )
                )
    except Exception as exc:
        logger.warning("Recommendation rule 'tail_latency_ratio' failed: %s", exc)

    # 2. Saturation knee
    try:
        knee = detect_knee_point(samples_path)
        if knee:
            recs.append(
                Recommendation(
                    kind="saturation_knee",
                    severity=InsightSeverity.WARNING,
                    message=(
                        f"Saturation knee at {knee['knee_rps']:.1f} RPS "
                        f"(p90: {knee['knee_p90_ms']:.0f} ms)"
                    ),
                    data={"knee_rps": knee["knee_rps"], "knee_p90_ms": knee["knee_p90_ms"]},
                )
            )
    except Exception as exc:
        logger.warning("Recommendation rule 'saturation_knee' failed: %s", exc)

    # 3. Error spike (any bucket > 10% error rate)
    try:
        error_df = compute_error_series(samples_path, bucket_seconds=10)
        if not error_df.is_empty():
            max_err = error_df["error_rate"].max()
            max_err_f = float(max_err) if max_err is not None else 0.0  # type: ignore[arg-type]
            if max_err_f > 0.10:
                recs.append(
                    Recommendation(
                        kind="error_spike",
                        severity=InsightSeverity.CRITICAL,
                        message=f"Error rate spike: {max_err_f * 100:.1f}% in a time bucket",
                        data={"max_error_rate": max_err_f},
                    )
                )
    except Exception as exc:
        logger.warning("Recommendation rule 'error_spike' failed: %s", exc)

    # 4. SLO violation
    try:
        slo_results = compute_slo_compliance(samples_path, slo_config)
        for r in slo_results:
            if not r.overall_compliant:
                recs.append(
                    Recommendation(
                        kind="slo_violation",
                        severity=InsightSeverity.CRITICAL,
                        message=(
                            f"Label '{r.label}' fails SLO: "
                            f"p90={r.p90_ms:.0f} ms, p99={r.p99_ms:.0f} ms, "
                            f"error={r.error_rate_pct:.2f}%"
                        ),
                        data={
                            "label": r.label,
                            "p90_ms": r.p90_ms,
                            "p99_ms": r.p99_ms,
                            "error_rate_pct": r.error_rate_pct,
                        },
                    )
                )
    except Exception as exc:
        logger.warning("Recommendation rule 'slo_violation' failed: %s", exc)

    # 5. Warmup window (INFO)
    try:
        warmup_end_ms, _test_end_ms = detect_warmup_window(samples_path)
        with duckdb.connect() as con:
            con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{samples_path}')")
            start_row = con.execute("SELECT MIN(timestamp_ms) FROM s").fetchone()
        start_ms = int(start_row[0]) if start_row and start_row[0] is not None else 0
        warmup_duration_s = (warmup_end_ms - start_ms) / 1000.0
        recs.append(
            Recommendation(
                kind="warmup_window",
                severity=InsightSeverity.INFO,
                message=(
                    f"Auto-detected warmup: {warmup_duration_s:.1f} s; "
                    f"steady state starts at {warmup_duration_s:.1f} s"
                ),
                data={"warmup_duration_s": warmup_duration_s, "warmup_end_ms": warmup_end_ms},
            )
        )
    except Exception as exc:
        logger.warning("Recommendation rule 'warmup_window' failed: %s", exc)

    # 6. High variability (CV = std / mean > 1.0)
    try:
        pct_df = compute_percentiles(samples_path, groupby_label=True)
        for row in pct_df.to_dicts():
            mean = float(row.get("mean") or 1)
            std = float(row.get("std") or 0)
            cv = std / max(mean, 1.0)
            label = str(row.get("label", ""))
            if cv > 1.0:
                recs.append(
                    Recommendation(
                        kind="high_variability",
                        severity=InsightSeverity.WARNING,
                        message=(
                            f"Label '{label}': high response time variability (CV={cv:.2f})"
                        ),
                        data={"label": label, "cv": cv, "mean": mean, "std": std},
                    )
                )
    except Exception as exc:
        logger.warning("Recommendation rule 'high_variability' failed: %s", exc)

    # 7. Cold-start detection: first 30 s error rate >> overall
    try:
        with duckdb.connect() as con2:
            con2.execute(f"CREATE VIEW samples AS SELECT * FROM read_parquet('{samples_path}')")
            row2 = con2.execute(
                """
                WITH start_ts AS (SELECT MIN(timestamp_ms) AS start FROM samples),
                first_30 AS (
                    SELECT SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS err
                    FROM samples, start_ts
                    WHERE timestamp_ms < start + 30000
                ),
                overall AS (
                    SELECT SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS err
                    FROM samples
                )
                SELECT first_30.err AS first_30_err, overall.err AS overall_err
                FROM first_30, overall
                """
            ).fetchone()
        if row2 and row2[0] is not None and row2[1] is not None:
            first_30_err = float(row2[0])
            overall_err = float(row2[1])
            if first_30_err > overall_err * 2.0 and first_30_err > 0.01:
                recs.append(
                    Recommendation(
                        kind="cold_start_detected",
                        severity=InsightSeverity.INFO,
                        message=(
                            f"Cold start: first 30 s error rate {first_30_err * 100:.1f}% "
                            f"vs overall {overall_err * 100:.1f}%"
                        ),
                        data={
                            "first_30s_error_rate": first_30_err,
                            "overall_error_rate": overall_err,
                        },
                    )
                )
    except Exception as exc:
        logger.warning("Recommendation rule 'cold_start_detected' failed: %s", exc)

    recs.sort(key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))
    return recs

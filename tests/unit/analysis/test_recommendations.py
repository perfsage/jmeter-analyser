"""Unit tests for perfsage.core.analysis.recommendations."""

from pathlib import Path

from perfsage.core.analysis.recommendations import Recommendation, run_all_recommendations
from perfsage.core.analysis.slo import SLOConfig
from perfsage.core.storage.db import InsightSeverity


def test_recommendations_returns_list(sample_parquet: Path) -> None:
    recs = run_all_recommendations(sample_parquet)
    assert isinstance(recs, list)


def test_recommendation_fields(sample_parquet: Path) -> None:
    recs = run_all_recommendations(sample_parquet)
    for r in recs:
        assert isinstance(r, Recommendation)
        assert isinstance(r.kind, str)
        assert isinstance(r.message, str)
        assert r.severity in (
            InsightSeverity.INFO,
            InsightSeverity.WARNING,
            InsightSeverity.CRITICAL,
        )


def test_recommendations_sorted_by_severity(sample_parquet: Path) -> None:
    recs = run_all_recommendations(sample_parquet)
    order = {InsightSeverity.CRITICAL: 0, InsightSeverity.WARNING: 1, InsightSeverity.INFO: 2}
    severities = [order[r.severity] for r in recs]
    assert severities == sorted(severities)


def test_high_tail_ratio_recommendation(sample_parquet_with_tail_latency: Path) -> None:
    recs = run_all_recommendations(sample_parquet_with_tail_latency)
    kinds = [r.kind for r in recs]
    assert "tail_latency_ratio" in kinds


def test_tail_ratio_severity_critical(sample_parquet_with_tail_latency: Path) -> None:
    recs = run_all_recommendations(sample_parquet_with_tail_latency)
    tail_recs = [r for r in recs if r.kind == "tail_latency_ratio"]
    # p99/p50 ≈ 3000/100 = 30x → CRITICAL
    assert any(r.severity == InsightSeverity.CRITICAL for r in tail_recs)


def test_no_critical_recommendations_for_perfect_run(sample_parquet_fast: Path) -> None:
    recs = run_all_recommendations(sample_parquet_fast)
    critical = [r for r in recs if r.severity == InsightSeverity.CRITICAL]
    assert len(critical) == 0


def test_warmup_window_always_present(sample_parquet: Path) -> None:
    recs = run_all_recommendations(sample_parquet)
    kinds = [r.kind for r in recs]
    assert "warmup_window" in kinds


def test_error_spike_recommendation(sample_parquet_with_errors: Path) -> None:
    # 20% error rate → error_spike or slo_violation should appear.
    recs = run_all_recommendations(sample_parquet_with_errors)
    kinds = [r.kind for r in recs]
    assert "error_spike" in kinds or "slo_violation" in kinds


def test_slo_violation_recommendation(sample_parquet_slow: Path) -> None:
    # All elapsed > 5000ms; default SLO p90=1000ms, p99=3000ms → violations.
    recs = run_all_recommendations(sample_parquet_slow)
    kinds = [r.kind for r in recs]
    assert "slo_violation" in kinds


def test_custom_slo_config(sample_parquet_fast: Path) -> None:
    # Very tight SLO but fast data still passes → no slo_violation.
    config = SLOConfig(p90_ms=200, p99_ms=200, error_rate_pct=100.0)
    recs = run_all_recommendations(sample_parquet_fast, slo_config=config)
    slo_violations = [r for r in recs if r.kind == "slo_violation"]
    assert len(slo_violations) == 0


def test_recommendation_data_is_dict(sample_parquet: Path) -> None:
    recs = run_all_recommendations(sample_parquet)
    for r in recs:
        assert isinstance(r.data, dict)

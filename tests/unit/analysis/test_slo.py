"""Unit tests for perfsage.core.analysis.slo."""

from pathlib import Path

from perfsage.core.analysis.slo import SLOConfig, SLOResult, compute_apdex, compute_slo_compliance

# ---------------------------------------------------------------------------
# Apdex tests
# ---------------------------------------------------------------------------


def test_apdex_perfect_score(sample_parquet_fast: Path) -> None:
    df = compute_apdex(sample_parquet_fast, t_seconds=1.0)
    assert df["apdex_score"].min() >= 0.99


def test_apdex_zero_score(sample_parquet_slow: Path) -> None:
    # t=0.1 s → t_ms=100, f_ms=400; all elapsed ≥ 5000 → all frustrated
    df = compute_apdex(sample_parquet_slow, t_seconds=0.1)
    assert df["apdex_score"].max() <= 0.01


def test_apdex_columns(sample_parquet: Path) -> None:
    df = compute_apdex(sample_parquet)
    for col in ("label", "satisfied", "tolerating", "frustrated", "total", "apdex_score"):
        assert col in df.columns, f"Missing column: {col}"


def test_apdex_totals_match_count(sample_parquet_fast: Path) -> None:
    df = compute_apdex(sample_parquet_fast)
    for row in df.to_dicts():
        assert int(row["satisfied"]) + int(row["tolerating"]) + int(row["frustrated"]) == int(
            row["total"]
        )


def test_apdex_score_range(sample_parquet: Path) -> None:
    df = compute_apdex(sample_parquet)
    assert df["apdex_score"].min() >= 0.0
    assert df["apdex_score"].max() <= 1.0


# ---------------------------------------------------------------------------
# SLO compliance tests
# ---------------------------------------------------------------------------


def test_slo_compliance_pass(sample_parquet_fast: Path) -> None:
    results = compute_slo_compliance(sample_parquet_fast, SLOConfig(p99_ms=10000))
    assert len(results) > 0
    assert all(r.overall_compliant for r in results)


def test_slo_compliance_fail(sample_parquet_slow: Path) -> None:
    results = compute_slo_compliance(sample_parquet_slow, SLOConfig(p99_ms=1))
    assert any(not r.overall_compliant for r in results)


def test_slo_compliance_error_rate_fail(sample_parquet_with_errors: Path) -> None:
    # Default error_rate_pct threshold is 1%; fixture has ~20% errors.
    results = compute_slo_compliance(sample_parquet_with_errors)
    assert any(not r.error_rate_compliant for r in results)


def test_slo_result_fields(sample_parquet: Path) -> None:
    results = compute_slo_compliance(sample_parquet)
    assert len(results) > 0
    r = results[0]
    assert isinstance(r, SLOResult)
    assert isinstance(r.label, str)
    assert isinstance(r.p90_ms, float)
    assert isinstance(r.p99_ms, float)
    assert isinstance(r.apdex_score, float)
    assert isinstance(r.overall_compliant, bool)


def test_slo_custom_thresholds(sample_parquet_fast: Path) -> None:
    # Very tight thresholds that fast data should still pass.
    cfg = SLOConfig(p90_ms=100, p99_ms=200, error_rate_pct=0.0)
    results = compute_slo_compliance(sample_parquet_fast, cfg)
    # Fast data: elapsed 20-49ms → p90 < 100, p99 < 200.
    assert all(r.p90_compliant for r in results)

"""Unit tests for AI prompt builder."""

from pathlib import Path

from perfsage.core.ai.prompts import build_analysis_prompt


def test_build_prompt_returns_string(sample_parquet: Path) -> None:
    prompt = build_analysis_prompt(sample_parquet)
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_prompt_contains_percentiles(sample_parquet: Path) -> None:
    prompt = build_analysis_prompt(sample_parquet)
    assert "P90" in prompt or "P99" in prompt


def test_prompt_handles_missing_file() -> None:
    prompt = build_analysis_prompt(Path("/nonexistent/file.parquet"))
    assert isinstance(prompt, str)


def test_prompt_has_preamble(sample_parquet: Path) -> None:
    prompt = build_analysis_prompt(sample_parquet)
    assert "JMeter" in prompt


def test_prompt_with_custom_slo(sample_parquet: Path) -> None:
    from perfsage.core.analysis.slo import SLOConfig

    slo = SLOConfig(p90_ms=500.0, p99_ms=1000.0)
    prompt = build_analysis_prompt(sample_parquet, slo_config=slo)
    assert isinstance(prompt, str)
    assert len(prompt) > 100

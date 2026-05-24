"""Tests for warmup/steady-state segmentation."""
from pathlib import Path

import polars as pl
import pytest

from perfsage.core.analysis.segmentation import detect_warmup_window, get_steady_state_samples


def test_detect_warmup_window_returns_tuple(sample_parquet: Path) -> None:
    warmup_end_ms, test_end_ms = detect_warmup_window(sample_parquet)
    assert isinstance(warmup_end_ms, int)
    assert isinstance(test_end_ms, int)
    assert warmup_end_ms < test_end_ms


def test_warmup_end_within_test_duration(sample_parquet: Path) -> None:
    warmup_end_ms, test_end_ms = detect_warmup_window(sample_parquet)
    assert warmup_end_ms >= 0
    assert test_end_ms > warmup_end_ms


def test_get_steady_state_excludes_warmup(sample_parquet: Path) -> None:
    warmup_end_ms, _ = detect_warmup_window(sample_parquet)
    steady_df = get_steady_state_samples(sample_parquet)
    assert isinstance(steady_df, pl.DataFrame)
    if len(steady_df) > 0:
        assert steady_df["timestamp_ms"].min() >= warmup_end_ms


def test_get_steady_state_returns_dataframe(sample_parquet: Path) -> None:
    df = get_steady_state_samples(sample_parquet)
    assert isinstance(df, pl.DataFrame)
    for col in ("timestamp_ms", "elapsed", "label", "success"):
        assert col in df.columns


def test_fallback_warmup_pct(sample_parquet: Path) -> None:
    warmup_end_ms, test_end_ms = detect_warmup_window(sample_parquet, warmup_pct_threshold=0.50)
    assert warmup_end_ms < test_end_ms

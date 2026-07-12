"""Tests for the per-path samples cache used by chart builders."""

from __future__ import annotations

import polars as pl
import pytest


def _write(path, elapsed):
    pl.DataFrame({"elapsed": elapsed, "label": ["A"] * len(elapsed)}).write_parquet(path)


def test_read_samples_cached_returns_equal_dataframe(tmp_path):
    from perfsage.core.viz._sample_cache import read_samples_cached

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    df = read_samples_cached(path)
    assert df["elapsed"].to_list() == [1, 2, 3]


def test_read_samples_cached_avoids_rereading_disk(tmp_path, monkeypatch):
    from perfsage.core.viz import _sample_cache

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    _sample_cache._cached_read_parquet.cache_clear()

    call_count = {"n": 0}
    real_read = pl.read_parquet

    def _counting_read(*args, **kwargs):
        call_count["n"] += 1
        return real_read(*args, **kwargs)

    monkeypatch.setattr(pl, "read_parquet", _counting_read)

    _sample_cache.read_samples_cached(path)
    _sample_cache.read_samples_cached(path)
    _sample_cache.read_samples_cached(path)

    assert call_count["n"] == 1


def test_read_samples_cached_detects_file_change(tmp_path):
    from perfsage.core.viz._sample_cache import read_samples_cached

    path = tmp_path / "s.parquet"
    _write(path, [1, 2, 3])
    first = read_samples_cached(path)
    assert first["elapsed"].to_list() == [1, 2, 3]

    _write(path, [4, 5])
    second = read_samples_cached(path)
    assert second["elapsed"].to_list() == [4, 5]

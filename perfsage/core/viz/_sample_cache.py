"""Per-path cache for samples.parquet reads.

Chart builders across viz/*.py each independently call pl.read_parquet on
the same samples.parquet during a single report render (measured: 25 full
reads per render). Since polars DataFrames are immutable by operation
(.filter()/.with_columns() return new frames, never mutate in place), it's
safe to share one cached DataFrame across every call site.

Cache key is (path, mtime_ns) so a changed file is never served stale.
Bounded maxsize keeps memory from growing unboundedly across many reports
in a single long-running worker/web process.
"""

from __future__ import annotations

import functools
from pathlib import Path

import polars as pl

_CACHE_SIZE = 8


@functools.lru_cache(maxsize=_CACHE_SIZE)
def _cached_read_parquet(path_str: str, mtime_ns: int) -> pl.DataFrame:
    return pl.read_parquet(path_str)


def read_samples_cached(path: Path) -> pl.DataFrame:
    """Read a samples parquet, reusing a cached DataFrame for the same
    (path, mtime) within the process instead of re-reading from disk."""
    stat = path.stat()
    return _cached_read_parquet(str(path), stat.st_mtime_ns)

"""Shared pytest fixtures for all test suites."""

from pathlib import Path

import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from perfsage.config import Settings, get_settings
from perfsage.main import create_app

# ---------------------------------------------------------------------------
# Helpers for analysis fixtures
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000_000  # 2023-11-14 22:13:20 UTC in ms


def _make_samples_parquet(
    tmp_path: Path,
    filename: str,
    elapsed_list: list[int],
    success_list: list[bool] | None = None,
    label_list: list[str] | None = None,
    ts_increment_ms: int = 1000,
) -> Path:
    """Write a canonical-schema parquet directly with polars and return its path."""
    n = len(elapsed_list)
    if success_list is None:
        success_list = [True] * n
    if label_list is None:
        # Alternate two labels so at least 2 labels are always present.
        label_list = ["Home" if i % 2 == 0 else "API" for i in range(n)]

    latency_list = [max(0, e - 10) for e in elapsed_list]

    df = pl.DataFrame(
        {
            "timestamp_ms": [_BASE_TS + i * ts_increment_ms for i in range(n)],
            "elapsed": elapsed_list,
            "label": label_list,
            "response_code": ["200" if s else "500" for s in success_list],
            "response_message": ["OK" if s else "Error" for s in success_list],
            "thread_name": ["Thread-1"] * n,
            "success": success_list,
            "failure_message": ["" if s else "Error" for s in success_list],
            "bytes": [1024] * n,
            "sent_bytes": [256] * n,
            "grp_threads": [10] * n,
            "all_threads": [10] * n,
            "url": ["http://example.com"] * n,
            "latency": latency_list,
            "idle_time": [0] * n,
            "connect": [10] * n,
        }
    ).with_columns(
        [
            pl.col("timestamp_ms").cast(pl.Int64),
            pl.col("elapsed").cast(pl.Int64),
            pl.col("bytes").cast(pl.Int64),
            pl.col("sent_bytes").cast(pl.Int64),
            pl.col("grp_threads").cast(pl.Int64),
            pl.col("all_threads").cast(pl.Int64),
            pl.col("latency").cast(pl.Int64),
            pl.col("idle_time").cast(pl.Int64),
            pl.col("connect").cast(pl.Int64),
        ]
    )

    path = tmp_path / filename
    df.write_parquet(path)
    return path


# ---------------------------------------------------------------------------
# Analysis parquet fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_parquet(tmp_path: Path) -> Path:
    """100 rows, 5 labels (Transaction 1-5), all success, elapsed 100–999 ms."""
    from perfsage.core.parsing.csv_loader import load_csv_to_parquet
    from tests.fixtures.generate_jtl import make_csv_jtl

    csv_content = make_csv_jtl(n_rows=100, include_errors=False)
    src = tmp_path / "test.csv"
    src.write_text(csv_content)
    dest = tmp_path / "samples.parquet"
    quarantine = tmp_path / "quar.parquet"
    load_csv_to_parquet(src, dest, quarantine, delimiter=",")
    return dest


@pytest.fixture()
def sample_parquet_fast(tmp_path: Path) -> Path:
    """200 rows, 2 labels, all elapsed 20–49 ms (fast, no errors)."""
    elapsed = [20 + (i % 30) for i in range(200)]
    return _make_samples_parquet(tmp_path, "fast.parquet", elapsed)


@pytest.fixture()
def sample_parquet_slow(tmp_path: Path) -> Path:
    """200 rows, 2 labels, all elapsed 5000–5999 ms (slow, no errors)."""
    elapsed = [5000 + (i % 1000) for i in range(200)]
    return _make_samples_parquet(tmp_path, "slow.parquet", elapsed)


@pytest.fixture()
def sample_parquet_with_errors(tmp_path: Path) -> Path:
    """200 rows, ~20% error rate (every 5th row is a failure)."""
    elapsed = [100 + (i % 400) for i in range(200)]
    success = [i % 5 != 0 for i in range(200)]
    return _make_samples_parquet(tmp_path, "errors.parquet", elapsed, success_list=success)


@pytest.fixture()
def sample_parquet_with_spike(tmp_path: Path) -> Path:
    """100 rows; rows 90-99 are in a spike bucket (elapsed=5000 ms), rest=200 ms."""
    elapsed = [200 if i < 90 else 5000 for i in range(100)]
    return _make_samples_parquet(tmp_path, "spike.parquet", elapsed)


@pytest.fixture()
def sample_parquet_with_tail_latency(tmp_path: Path) -> Path:
    """100 rows; 90 rows at 100 ms + 10 rows at 3000 ms → p99/p50 ≈ 30x."""
    elapsed = [100] * 90 + [3000] * 10
    return _make_samples_parquet(tmp_path, "tail.parquet", elapsed)


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    """Return a Settings instance suitable for testing (in-memory SQLite, tmp data dir)."""
    return Settings(
        debug=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret-32-chars-long-enough!",
        max_upload_bytes=10 * 1024 * 1024,
    )


@pytest.fixture()
def app(test_settings: Settings) -> FastAPI:
    """Return a FastAPI application configured with test settings."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: test_settings
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Return a synchronous TestClient for the FastAPI app."""
    return TestClient(app)

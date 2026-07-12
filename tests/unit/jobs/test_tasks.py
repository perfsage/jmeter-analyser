"""Unit tests for the ingest_report_task arq background job."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pyarrow.parquet as pq
import pytest

from perfsage.config import Settings
from perfsage.core.jobs.tasks import ingest_report_task
from perfsage.core.storage.db import JobStatus, ReportStatus, get_engine, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import JobRepo, ReportRepo

_SAMPLE_CSV = """\
timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect
1716556800000,100,GET /api,200,OK,Thread-1,true,1024,256,1,1,http://example.com/api,95,0,5
1716556800100,200,GET /api,200,OK,Thread-1,true,2048,256,1,1,http://example.com/api,190,0,10
1716556800200,150,GET /home,404,Not Found,Thread-2,false,512,128,1,2,http://example.com/home,140,0,10
1716556800300,300,GET /home,200,OK,Thread-2,true,1024,128,1,2,http://example.com/home,280,0,10
"""


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        debug=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path,
        redis_url="redis://localhost:6379",
        perfsage_secret="test-secret-32-chars-long-enough!",
        max_upload_bytes=10 * 1024 * 1024,
    )


@pytest.fixture()
def engine(test_settings: Settings):  # type: ignore[type-arg]
    eng = get_engine(test_settings.database_url)
    yield eng
    eng.dispose()


@pytest.mark.asyncio
async def test_ingest_task_csv(
    tmp_path: Path,
    test_settings: Settings,
    engine,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("perfsage.core.jobs.tasks.get_settings", lambda: test_settings)

    csv_file = tmp_path / "sample.jtl"
    csv_file.write_text(_SAMPLE_CSV)

    with get_session(engine) as session:
        report = ReportRepo(session).create("test", "sample.jtl", len(_SAMPLE_CSV))
        job = JobRepo(session).create(report.id)

    published: list[dict] = []

    async def _publish(channel: str, data: str) -> None:
        published.append(json.loads(data))

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(side_effect=_publish)

    ctx: dict = {"redis": mock_redis}

    await ingest_report_task(ctx, job.id, report.id, str(csv_file))

    # Parquet files must exist
    fs = FileStore(tmp_path)
    assert fs.samples_parquet(report.id).exists(), "samples.parquet not written"
    assert fs.agg_parquet(report.id, "summary").exists(), "agg_summary.parquet not written"

    # Verify sample row count
    samples_table = pq.read_table(fs.samples_parquet(report.id))
    assert samples_table.num_rows == 4

    # Verify aggregate columns
    agg_table = pq.read_table(fs.agg_parquet(report.id, "summary"))
    agg_cols = set(agg_table.schema.names)
    required_cols = {
        "label",
        "count",
        "mean_elapsed",
        "p50",
        "p90",
        "p95",
        "p99",
        "error_rate",
        "min_elapsed",
        "max_elapsed",
    }
    assert required_cols <= agg_cols, f"Missing agg columns: {required_cols - agg_cols}"

    # Job must be marked done
    with get_session(engine) as session:
        j = JobRepo(session).get(job.id)
    assert j is not None
    assert j.status == JobStatus.DONE

    # Report must be READY
    with get_session(engine) as session:
        r = ReportRepo(session).get(report.id)
    assert r is not None
    assert r.status == ReportStatus.READY
    assert r.parsed_row_count == 4

    # Progress events must cover detect → parse → aggregate → done
    phases = [e["phase"] for e in published]
    assert "detect" in phases
    assert "parse" in phases
    assert "aggregate" in phases
    assert "done" in phases
    # Final event pct must be 100
    assert published[-1]["pct"] == 100.0


@pytest.mark.asyncio
async def test_ingest_task_bad_file(
    tmp_path: Path,
    test_settings: Settings,
    engine,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("perfsage.core.jobs.tasks.get_settings", lambda: test_settings)

    bad_file = tmp_path / "bad.jtl"
    bad_file.write_bytes(b"\x00\x01\x02\x03")  # binary garbage — UNKNOWN format

    with get_session(engine) as session:
        report = ReportRepo(session).create("bad", "bad.jtl", 4)
        job = JobRepo(session).create(report.id)

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()
    ctx: dict = {"redis": mock_redis}

    with pytest.raises(ValueError, match="Unknown file format"):
        await ingest_report_task(ctx, job.id, report.id, str(bad_file))

    with get_session(engine) as session:
        j = JobRepo(session).get(job.id)
    assert j is not None
    assert j.status == JobStatus.FAILED
    assert j.error_text is not None


@pytest.mark.asyncio
async def test_ingest_all_quarantined_file_marks_report_failed(
    tmp_path: Path,
    test_settings: Settings,
    engine,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CSV where every row fails validation must not end up READY."""
    monkeypatch.setattr("perfsage.core.jobs.tasks.get_settings", lambda: test_settings)

    # Header present, but every data row has a non-numeric elapsed value —
    # every row is quarantined, zero rows parsed successfully.
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("timeStamp,elapsed,label,success\n1700000000000,notanumber,Home,true\n")

    with get_session(engine) as session:
        report = ReportRepo(session).create("bad", "bad.csv", 100)
        job = JobRepo(session).create(report.id)

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()
    ctx: dict = {"redis": mock_redis}

    with pytest.raises(ValueError, match="(?i)no valid samples|all rows"):
        await ingest_report_task(ctx, job.id, report.id, str(bad_file))

    with get_session(engine) as session:
        r = ReportRepo(session).get(report.id)
    assert r is not None
    assert r.status == ReportStatus.FAILED

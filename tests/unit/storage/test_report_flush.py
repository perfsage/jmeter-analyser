"""Unit tests for report flush (delete old reports + files)."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from perfsage.core.storage.db import ReportStatus, get_engine
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.report_cleanup import flush_reports
from perfsage.core.storage.repos import JobRepo, ReportRepo


def test_flush_keeps_recent_and_deletes_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    fs = FileStore(data_dir)
    fs.ensure_dirs()
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")

    report_ids: list[str] = []
    with Session(engine) as session:
        repo = ReportRepo(session)
        for i in range(3):
            r = repo.create(name=f"r{i}", source_filename=f"{i}.jtl", size_bytes=1)
            report_ids.append(r.id)
            job = JobRepo(session).create(r.id)
            upload = fs.upload_path(job.id)
            upload.parent.mkdir(parents=True, exist_ok=True)
            upload.write_text("sample")
            parquet_dir = fs.samples_parquet(r.id).parent
            parquet_dir.mkdir(parents=True, exist_ok=True)
            fs.samples_parquet(r.id).write_text("parquet")
            fs.export_path(r.id, "html").write_text("html")

    deleted = flush_reports(engine, data_dir, keep_recent=1)
    assert deleted == 2

    with Session(engine) as session:
        assert ReportRepo(session).count() == 1
        assert ReportRepo(session).list_page(0, 10)[0].id == report_ids[-1]

    assert not fs.samples_parquet(report_ids[0]).exists()
    assert fs.samples_parquet(report_ids[2]).exists()


def test_flush_refuses_when_processing(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with Session(engine) as session:
        repo = ReportRepo(session)
        r = repo.create(name="busy", source_filename="b.jtl", size_bytes=1)
        repo.update_status(r.id, ReportStatus.PROCESSING)

    try:
        flush_reports(engine, tmp_path / "data", keep_recent=0)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "processing" in str(exc).lower()

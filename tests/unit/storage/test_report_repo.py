"""Unit tests for ReportRepo pagination and deletion."""

from __future__ import annotations

from sqlmodel import Session

from perfsage.core.storage.db import Report, ReportStatus, get_engine
from perfsage.core.storage.repos import ReportRepo


def _make_report(session: Session, name: str) -> Report:
    return ReportRepo(session).create(name=name, source_filename=f"{name}.jtl", size_bytes=100)


def test_list_page_returns_slice_in_desc_order(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with Session(engine) as session:
        for i in range(5):
            _make_report(session, f"report-{i}")

    with Session(engine) as session:
        repo = ReportRepo(session)
        page = repo.list_page(offset=0, limit=2)
        assert len(page) == 2
        assert page[0].name == "report-4"
        assert page[1].name == "report-3"


def test_count_and_count_by_status(tmp_path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with Session(engine) as session:
        r1 = _make_report(session, "a")
        r2 = _make_report(session, "b")
        repo = ReportRepo(session)
        repo.update_status(r1.id, ReportStatus.READY)
        repo.update_status(r2.id, ReportStatus.PROCESSING)

    with Session(engine) as session:
        repo = ReportRepo(session)
        assert repo.count() == 2
        by_status = repo.count_by_status()
        assert by_status[ReportStatus.READY] == 1
        assert by_status[ReportStatus.PROCESSING] == 1

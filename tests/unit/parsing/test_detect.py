"""Unit tests for perfsage.core.parsing.detect."""

from __future__ import annotations

from pathlib import Path

import pytest

from perfsage.core.parsing.detect import (
    JTLFormat,
    detect_csv_delimiter,
    detect_format,
    detect_timestamp_format,
)
from tests.fixtures.generate_jtl import make_csv_jtl, make_xml_jtl


def test_detects_xml(tmp_path: Path) -> None:
    src = tmp_path / "test.jtl"
    src.write_text(make_xml_jtl(n_rows=5))
    assert detect_format(src) == JTLFormat.XML


def test_detects_xml_no_declaration(tmp_path: Path) -> None:
    src = tmp_path / "test.jtl"
    src.write_text('<testResults version="1.2">\n</testResults>')
    assert detect_format(src) == JTLFormat.XML


def test_detects_csv(tmp_path: Path) -> None:
    src = tmp_path / "test.csv"
    src.write_text(make_csv_jtl(n_rows=5))
    assert detect_format(src) == JTLFormat.CSV


def test_detects_tab_delimiter(tmp_path: Path) -> None:
    src = tmp_path / "test.csv"
    src.write_text(make_csv_jtl(n_rows=5, delimiter="\t"))
    assert detect_csv_delimiter(src) == "\t"


def test_detects_comma_delimiter(tmp_path: Path) -> None:
    src = tmp_path / "test.csv"
    src.write_text(make_csv_jtl(n_rows=5, delimiter=","))
    assert detect_csv_delimiter(src) == ","


def test_detects_semicolon_delimiter(tmp_path: Path) -> None:
    src = tmp_path / "test.csv"
    src.write_text(make_csv_jtl(n_rows=5, delimiter=";"))
    assert detect_csv_delimiter(src) == ";"


def test_detects_epoch_ms_timestamp() -> None:
    assert detect_timestamp_format("1700000000000") == "epoch_ms"


def test_detects_epoch_s_timestamp() -> None:
    assert detect_timestamp_format("1700000000") == "epoch_s"


def test_detects_datetime_timestamp() -> None:
    assert detect_timestamp_format("2023-11-14 22:13:20") == "datetime"


def test_detects_datetime_iso_timestamp() -> None:
    assert detect_timestamp_format("2023-11-14T22:13:20Z") == "datetime"


def test_unknown_timestamp_raises() -> None:
    with pytest.raises(ValueError):
        detect_timestamp_format("not-a-timestamp")

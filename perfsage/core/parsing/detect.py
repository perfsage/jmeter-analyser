"""Detect JTL file format, CSV delimiter, and timestamp encoding."""

from __future__ import annotations

import csv
from enum import StrEnum
from pathlib import Path


class JTLFormat(StrEnum):
    CSV = "csv"
    XML = "xml"
    UNKNOWN = "unknown"


def detect_format(path: Path) -> JTLFormat:
    """Read first 512 bytes and return JTLFormat."""
    with path.open("rb") as fh:
        header = fh.read(512)
    text = header.lstrip().decode("utf-8", errors="replace")
    first_line = text.split("\n")[0].strip()
    if text.startswith("<?xml") or text.startswith("<testResults"):
        return JTLFormat.XML
    # Treat as CSV if the first non-blank line contains a recognised delimiter.
    if any(ch in first_line for ch in (",", "\t", ";")):
        return JTLFormat.CSV
    return JTLFormat.UNKNOWN


def detect_csv_delimiter(path: Path) -> str:
    """Sniff CSV delimiter (comma, tab, semicolon) from the first 10 lines."""
    sample_lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= 10:
                break
            sample_lines.append(line)
    sample = "".join(sample_lines)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        return dialect.delimiter
    except csv.Error:
        return ","


def detect_timestamp_format(sample: str) -> str:
    """Return 'epoch_ms', 'epoch_s', or 'datetime' for a sample timestamp value.

    Raises ValueError if the value cannot be interpreted.
    """
    stripped = sample.strip()
    try:
        value = float(stripped)
        if value > 1_000_000_000_000:
            return "epoch_ms"
        if value >= 1_000_000_000:
            return "epoch_s"
        # Very small numbers treated as epoch_s (ancient timestamps / zero).
        return "epoch_s"
    except ValueError:
        pass
    # Try common datetime string formats.
    from datetime import datetime

    _formats = (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in _formats:
        try:
            datetime.strptime(stripped, fmt)  # noqa: DTZ007
            return "datetime"
        except ValueError:
            continue
    raise ValueError(f"Cannot determine timestamp format for value: {sample!r}")

"""Detect whether an uploaded file is JMeter CSV or JTL/XML format."""

from pathlib import Path


def detect_format(path: Path) -> str:
    """Return 'csv', 'xml', or raise ValueError for unknown formats.

    Reads the first few bytes to detect the file type without parsing the whole file.
    """
    raise NotImplementedError

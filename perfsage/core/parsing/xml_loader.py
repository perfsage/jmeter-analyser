"""Load JMeter JTL/XML result files into a Polars DataFrame."""

from pathlib import Path

import polars as pl


def load_xml(path: Path) -> pl.DataFrame:
    """Parse a JMeter JTL/XML result file and return a normalised DataFrame."""
    raise NotImplementedError

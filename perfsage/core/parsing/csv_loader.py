"""Load JMeter CSV result files into a Polars DataFrame."""

from pathlib import Path

import polars as pl


def load_csv(path: Path) -> pl.DataFrame:
    """Parse a JMeter CSV result file and return a normalised DataFrame."""
    raise NotImplementedError

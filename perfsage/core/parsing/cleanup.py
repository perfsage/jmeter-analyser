"""Clean and normalise raw JMeter DataFrames before analysis."""

import polars as pl


def clean(df: pl.DataFrame) -> pl.DataFrame:
    """Remove duplicates, fix timestamps, coerce types, drop corrupt rows."""
    raise NotImplementedError

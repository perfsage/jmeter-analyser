"""Segment test results by label, endpoint, time window, or thread group."""

import polars as pl


def segment_by_label(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Split the DataFrame into per-label sub-DataFrames."""
    raise NotImplementedError


def segment_by_time_window(df: pl.DataFrame, window_seconds: int = 60) -> list[pl.DataFrame]:
    """Split the DataFrame into fixed-duration time windows."""
    raise NotImplementedError

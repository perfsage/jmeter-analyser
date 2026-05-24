"""Statistical anomaly detection for JMeter time-series data."""

import polars as pl


def detect_anomalies(df: pl.DataFrame) -> pl.DataFrame:
    """Flag rows / time windows that are statistical outliers.

    Returns the input DataFrame with an additional boolean 'is_anomaly' column.
    """
    raise NotImplementedError

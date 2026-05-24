"""Unit tests for perfsage.core.parsing.cleanup."""

from __future__ import annotations

import polars as pl
import pytest

from perfsage.core.parsing.cleanup import (
    QuarantinedRow,
    clean_dataframe,
    normalize_bool,
    normalize_timestamp,
    validate_row,
)

# ─── normalize_timestamp ──────────────────────────────────────────────────────


def test_normalize_timestamp_epoch_ms() -> None:
    assert normalize_timestamp(1700000000000) == 1700000000000


def test_normalize_timestamp_epoch_s() -> None:
    assert normalize_timestamp(1700000000) == 1700000000000


def test_normalize_timestamp_epoch_ms_float() -> None:
    assert normalize_timestamp(1700000000000.0) == 1700000000000


def test_normalize_timestamp_epoch_s_string() -> None:
    assert normalize_timestamp("1700000000") == 1700000000000


def test_normalize_timestamp_epoch_ms_string() -> None:
    assert normalize_timestamp("1700000000000") == 1700000000000


def test_normalize_timestamp_datetime_string() -> None:
    result = normalize_timestamp("2023-11-14 22:13:20")
    # Should be close to 1700000000000 (within a day).
    assert abs(result - 1700000000000) < 86_400_000


def test_normalize_timestamp_invalid_string() -> None:
    with pytest.raises(ValueError):
        normalize_timestamp("not-a-timestamp")


# ─── normalize_bool ───────────────────────────────────────────────────────────


def test_normalize_bool_true_lowercase() -> None:
    assert normalize_bool("true") is True


def test_normalize_bool_false_uppercase() -> None:
    assert normalize_bool("FALSE") is False


def test_normalize_bool_bool_passthrough() -> None:
    assert normalize_bool(True) is True
    assert normalize_bool(False) is False


def test_normalize_bool_int_one() -> None:
    assert normalize_bool(1) is True  # type: ignore[arg-type]


def test_normalize_bool_int_zero() -> None:
    assert normalize_bool(0) is False  # type: ignore[arg-type]


def test_normalize_bool_garbage_raises() -> None:
    with pytest.raises(ValueError):
        normalize_bool("maybe")


# ─── validate_row ────────────────────────────────────────────────────────────


def test_validate_row_valid() -> None:
    row = {"timestamp_ms": 1700000000000, "elapsed": 200, "label": "Home"}
    assert validate_row(row, 0) is None


def test_validate_row_missing_elapsed() -> None:
    row = {"timestamp_ms": 1700000000000, "label": "Home"}
    result = validate_row(row, 0)
    assert result is not None
    assert "elapsed" in result.reason


def test_validate_row_negative_elapsed() -> None:
    row = {"timestamp_ms": 1700000000000, "elapsed": -1, "label": "Home"}
    result = validate_row(row, 0)
    assert result is not None
    assert "elapsed" in result.reason


def test_validate_row_missing_timestamp() -> None:
    row = {"elapsed": 200, "label": "Home"}
    result = validate_row(row, 5)
    assert result is not None
    assert result.row_index == 5
    assert "timestamp_ms" in result.reason


def test_validate_row_preserves_raw() -> None:
    row = {"elapsed": -1, "timestamp_ms": 1700000000000}
    result = validate_row(row, 3)
    assert result is not None
    assert result.raw == row


# ─── clean_dataframe ─────────────────────────────────────────────────────────


def test_clean_dataframe_valid_rows() -> None:
    df = pl.DataFrame(
        {
            "timestamp_ms": ["1700000000000", "1700000001000"],
            "elapsed": ["100", "200"],
            "label": ["Home", "Login"],
            "success": ["true", "false"],
        }
    )
    clean, quarantined = clean_dataframe(df)
    assert len(clean) == 2
    assert quarantined == []
    assert clean["timestamp_ms"].dtype == pl.Int64
    assert clean["elapsed"].dtype == pl.Int64
    assert clean["success"].dtype == pl.Boolean


def test_clean_dataframe_quarantines_negative_elapsed() -> None:
    df = pl.DataFrame(
        {
            "timestamp_ms": ["1700000000000", "1700000001000"],
            "elapsed": ["100", "-5"],
            "label": ["Home", "Broken"],
        }
    )
    clean, quarantined = clean_dataframe(df)
    assert len(clean) == 1
    assert len(quarantined) == 1
    assert "elapsed" in quarantined[0].reason


def test_clean_dataframe_quarantines_null_elapsed() -> None:
    df = pl.DataFrame(
        {
            "timestamp_ms": ["1700000000000"],
            "elapsed": [None],
            "label": ["Home"],
        }
    )
    clean, quarantined = clean_dataframe(df)
    assert len(clean) == 0
    assert len(quarantined) == 1


def test_clean_dataframe_no_elapsed_column() -> None:
    """DataFrame without elapsed should pass through (no validation condition)."""
    df = pl.DataFrame({"label": ["Home", "Login"]})
    clean, quarantined = clean_dataframe(df)
    assert len(clean) == 2
    assert quarantined == []


def test_clean_dataframe_returns_quarantined_row_dataclass() -> None:
    df = pl.DataFrame(
        {
            "timestamp_ms": ["1700000000000"],
            "elapsed": ["-99"],
            "label": ["Bad"],
        }
    )
    _, quarantined = clean_dataframe(df)
    assert len(quarantined) == 1
    assert isinstance(quarantined[0], QuarantinedRow)

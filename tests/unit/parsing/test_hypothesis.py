"""Property-based tests for parsing primitives using Hypothesis."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from perfsage.core.parsing.cleanup import normalize_bool, normalize_timestamp


@given(st.integers(min_value=0, max_value=1_000_000_000_000_000))
@settings(max_examples=500)
def test_normalize_timestamp_never_raises(ts: int) -> None:
    result = normalize_timestamp(ts)
    assert isinstance(result, int)
    assert result >= 0


@given(st.floats(min_value=0.0, max_value=1e15, allow_nan=False, allow_infinity=False))
@settings(max_examples=300)
def test_normalize_timestamp_float_never_raises(ts: float) -> None:
    result = normalize_timestamp(ts)
    assert isinstance(result, int)
    assert result >= 0


@given(st.text(min_size=0, max_size=100))
@settings(max_examples=500)
def test_normalize_bool_string_never_crashes(s: str) -> None:
    try:
        result = normalize_bool(s)
        assert isinstance(result, bool)
    except ValueError:
        pass  # expected for unrecognised strings


@given(st.sampled_from(["true", "false", "TRUE", "FALSE", "True", "False", "1", "0"]))
def test_normalize_bool_known_values_succeed(s: str) -> None:
    result = normalize_bool(s)
    assert isinstance(result, bool)


@given(st.booleans())
def test_normalize_bool_passthrough(b: bool) -> None:
    assert normalize_bool(b) is b

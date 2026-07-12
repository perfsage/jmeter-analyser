"""Tests for the disk-backed render cache for expensive report payloads."""

from __future__ import annotations


def test_get_or_build_json_builds_and_caches(tmp_path):
    from perfsage.core.viz.render_cache import get_or_build_json

    cache_path = tmp_path / "sub" / "cache.json"
    calls = {"n": 0}

    def _build():
        calls["n"] += 1
        return {"a": 1}

    first = get_or_build_json(cache_path, _build)
    second = get_or_build_json(cache_path, _build)

    assert first == {"a": 1}
    assert second == {"a": 1}
    assert calls["n"] == 1  # second call served from cache_path, build() not called again
    assert cache_path.exists()


def test_get_or_build_json_rebuilds_on_corrupt_cache_file(tmp_path):
    from perfsage.core.viz.render_cache import get_or_build_json

    cache_path = tmp_path / "cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not valid json")

    result = get_or_build_json(cache_path, lambda: {"b": 2})
    assert result == {"b": 2}
    assert cache_path.read_text() == '{"b": 2}'

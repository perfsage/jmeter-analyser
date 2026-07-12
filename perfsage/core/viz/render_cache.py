"""Disk-backed cache for expensive per-report render payloads (figures JSON).

A Report is immutable once READY — its samples.parquet never changes after
ingest — so the JSON built for a given figure-set is safe to cache
indefinitely and reuse across every subsequent page view of that report.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def get_or_build_json(cache_path: Path, build: Callable[[], Any]) -> Any:
    """Return the JSON-decoded contents of cache_path if present and valid,
    otherwise call build(), write its JSON-encoded result to cache_path, and
    return it. Never raises on cache I/O failure — falls back to build()."""
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except (OSError, ValueError):
            logger.warning("Render cache at %s is unreadable; rebuilding", cache_path)

    result = build()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result))
    except OSError:
        logger.warning("Could not write render cache at %s", cache_path)
    return result

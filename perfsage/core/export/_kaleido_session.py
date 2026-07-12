"""Serialize and reuse a single Kaleido/Chromium session for chart PNG export.

Plotly's ``fig.write_image()`` starts and stops a headless browser on every call
(~2–3 s each). For 29 charts that is ~75 s per PDF and multiple concurrent
pytest processes can deadlock fighting over Chromium. This module keeps one
browser alive for a batch render and uses a file lock so only one process uses
Kaleido at a time.
"""

from __future__ import annotations

import fcntl
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCK_PATH = Path(tempfile.gettempdir()) / "perfsage-kaleido.lock"


def kaleido_server_running() -> bool:
    from kaleido._sync_server import GlobalKaleidoServer

    return GlobalKaleidoServer().is_running()


@contextmanager
def kaleido_process_lock() -> Iterator[None]:
    """Block until this process holds the cross-process Kaleido lock."""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_PATH.open("w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def managed_kaleido_server() -> Iterator[None]:
    """Start Kaleido sync server if needed; stop only when this context opened it."""
    import kaleido

    owned = not kaleido_server_running()
    if owned:
        kaleido.start_sync_server(silence_warnings=True)
    try:
        yield
    finally:
        if owned:
            kaleido.stop_sync_server(silence_warnings=True)

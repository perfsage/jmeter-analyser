#!/usr/bin/env python
"""Local benchmark: time report-page figure building for a given samples parquet.

Usage:
    python scripts/bench_report.py path/to/samples.parquet

Not wired into CI — for local before/after comparisons when touching
perfsage/core/viz/ or perfsage/core/analysis/.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    samples_path = Path(sys.argv[1])
    if not samples_path.exists():
        print(f"File not found: {samples_path}")
        sys.exit(1)

    from perfsage.core.analysis.slo import SLOConfig
    from perfsage.core.viz.registry import EXPORT_FIGURES, build_figures_json

    slo_config = SLOConfig()

    print(f"Benchmarking {samples_path} ({samples_path.stat().st_size / 1e6:.1f} MB)")

    start = time.perf_counter()
    figures = build_figures_json(samples_path, slo_config)
    elapsed = time.perf_counter() - start

    import json

    payload_bytes = len(json.dumps(figures))
    built = sum(1 for v in figures.values() if v is not None)

    print(
        f"build_figures_json: {elapsed:.2f}s, {built}/{len(EXPORT_FIGURES)} figures built, "
        f"payload {payload_bytes / 1e6:.2f} MB"
    )


if __name__ == "__main__":
    main()

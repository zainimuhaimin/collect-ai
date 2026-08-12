"""Profiling `daily_scoring.py` (post-presentation-review-tasks.md TASK-P2).

Jalankan pada rung yang CUKUP BESAR untuk mewakili (mis. 50-100 rb customer,
lihat faker/bulk_clone.py) — hotspot di dataset kecil (2 rb) didominasi
overhead startup (import, koneksi DB) dan menyesatkan prioritas TASK-P5.

Pemakaian:
    cd app/machine-learning
    python ../../perf/profile_scoring.py [--top 25] [--strict-qc-off]

Output: perf/results/daily_scoring_<timestamp>.pstats (bisa dibuka
`snakeviz`/`gprof2dot`) + ringkasan top-N cumulative time langsung di stdout,
disalin ke performance-report.md secara manual.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import os
import pstats
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ML_ROOT = os.path.join(_ROOT, "app", "machine-learning")
sys.path.insert(0, _ML_ROOT)

from pipelines.daily_scoring import run_daily_scoring  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--strict-qc-off", action="store_true",
                         help="strict_qc=False — data sintetis bulk-clone biasa gagal soft-check distribusi")
    args = parser.parse_args(argv)

    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    profiler = cProfile.Profile()
    profiler.enable()
    run_daily_scoring(strict_qc=(False if args.strict_qc_off else None))
    profiler.disable()

    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pstats_path = os.path.join(results_dir, f"daily_scoring_{stamp}.pstats")
    profiler.dump_stats(pstats_path)

    buf = io.StringIO()
    stats = pstats.Stats(profiler, stream=buf).sort_stats("cumulative")
    stats.print_stats(args.top)
    print(buf.getvalue())
    print(f"\n[profile_scoring] .pstats tersimpan: {pstats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

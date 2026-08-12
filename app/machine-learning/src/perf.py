"""Instrumentasi timing & memori untuk pipeline ML (post-presentation-review-tasks.md
TASK-P1). Sebelum ini: nol timing di seluruh repo — hanya print().

Pemakaian:

    from src.perf import stage_timer, new_run_id

    run_id = new_run_id()
    with stage_timer(run_id, "load_contract", n_customers=n) as t:
        df = pd.read_sql(...)
        t.rows = len(df)

Tiap ``with`` block menutup satu baris ke logs/perf_runs.csv. run_id sama
dipakai lintas beberapa stage dalam satu eksekusi pipeline supaya baris-baris
itu bisa dikelompokkan kembali saat dianalisis.
"""
from __future__ import annotations

import csv
import os
import resource
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LOGS_DIR  # noqa: E402

PERF_LOG_PATH = os.path.join(LOGS_DIR, "perf_runs.csv")
_FIELDS = ["run_id", "n_customers", "stage", "duration_s", "peak_rss_mb", "rows", "started_at"]


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def _peak_rss_mb() -> float:
    """ru_maxrss: bytes di macOS (Darwin), KB di Linux — normalisasi wajib,
    beda platform yang salah dibaca akan meleset 1000x."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return raw / divisor


@dataclass
class _StageResult:
    rows: int | None = None


@contextmanager
def stage_timer(run_id: str, stage: str, n_customers: int | None = None):
    """Context manager: catat durasi + peak RSS + jumlah baris satu stage.

    ``n_customers`` opsional (mis. saat stage tidak berkorelasi langsung
    dengan volume customer). Set ``t.rows = len(df)`` di dalam block untuk
    mencatat jumlah baris yang diproses stage ini.
    """
    result = _StageResult()
    started_at = datetime.now()
    t0 = time.perf_counter()
    try:
        yield result
    finally:
        duration_s = time.perf_counter() - t0
        _append_row({
            "run_id": run_id,
            "n_customers": n_customers if n_customers is not None else "",
            "stage": stage,
            "duration_s": round(duration_s, 4),
            "peak_rss_mb": round(_peak_rss_mb(), 2),
            "rows": result.rows if result.rows is not None else "",
            "started_at": started_at.isoformat(),
        })


def _append_row(row: dict):
    os.makedirs(os.path.dirname(PERF_LOG_PATH), exist_ok=True)
    write_header = not os.path.exists(PERF_LOG_PATH)
    with open(PERF_LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

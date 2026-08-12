"""Sweep volume 5K -> sejauh hardware/waktu sesi sanggup (post-presentation-
review-tasks.md TASK-P4). Per rung: reset DB, muat data (simulator asli untuk
rung kecil, faker/bulk_clone.py untuk rung besar), 4 train_*.py (timing WAJIB
sebelum scoring — reset-demo.sh menghapus champion, daily_scoring.py:151
`_resolve_champion_path()` raise kalau tidak ada), lalu daily_scoring.py.
Timing per-stage TIDAK diukur ulang di sini — semua pipeline sudah
terinstrumentasi (TASK-P1, src/perf.py -> logs/perf_runs.csv); skrip ini
membaca baris BARU di file itu setelah tiap subprocess untuk merangkumnya ke
perf/results/scale_sweep.csv, plus rows/pg_total_relation_size per tabel.

Stop rule: --max-stage-seconds (subprocess timeout -> kill, dicatat sebagai
titik patah), --max-rss-gb (cek POST-HOC dari perf_runs.csv setelah tiap
subprocess selesai — bukan watchdog live, lihat catatan di bawah),
--min-free-disk-gb (cek SEBELUM tiap rung, ladder dihentikan kalau sisa disk
di bawah ambang). Begitu satu rung melewati salah satu budget, ladder
berhenti dan titik patahnya dicatat di scale_sweep.csv (kolom `status`).

⚠️ Keterbatasan yang jujur: --max-rss-gb dicek SETELAH subprocess selesai
(dari peak_rss_mb yang subprocess itu sendiri catat via resource.getrusage),
BUKAN watchdog live yang mem-SIGKILL proses begitu RSS menyentuh ambang di
tengah jalan. Kalau satu stage benar-benar OOM sebelum sempat menulis baris
perf_runs.csv, prosesnya mati sendiri (subprocess non-zero exit / SIGKILL
dari OS) dan ladder berhenti lewat jalur error, bukan jalur --max-rss-gb yang
rapi. Ini cukup untuk mendeteksi "mendekati budget" sebelum benar-benar OOM
di rung berikutnya, tapi bukan pengganti watchdog live sungguhan.

Pemakaian:
    python perf/benchmark_scale.py --rungs 5000,10000,25000,50000 \\
        --max-stage-seconds 600 --max-rss-gb 12 --min-free-disk-gb 3
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ML_DIR = os.path.join(_ROOT, "app", "machine-learning")
_FAKER_DIR = os.path.join(_ROOT, "faker")
_RESULTS_DIR = os.path.join(_ROOT, "perf", "results")
_PERF_LOG = os.path.join(_ML_DIR, "logs", "perf_runs.csv")
_SCALE_SWEEP_CSV = os.path.join(_RESULTS_DIR, "scale_sweep.csv")

# Rung >= ini dimuat lewat bulk_clone.py (benih REAL_SEED_CUSTOMERS + replikasi
# berperturbasi); di bawah ini lewat simulator asli — lihat TASK-P3.
BULK_CLONE_THRESHOLD = 30_000
REAL_SEED_CUSTOMERS = 20_000

TABLES = ["customer_master", "contract_snapshot", "payment_history", "lkp_interaction"]

_SCALE_SWEEP_FIELDS = [
    "rung", "n_customers", "loader", "status", "break_stage", "break_reason",
    "generate_s", "train_initial_s", "train_self_cure_s", "train_roll_forward_s",
    "train_ptp_success_s", "daily_scoring_s",
    "peak_rss_generate_mb", "peak_rss_train_mb", "peak_rss_score_mb",
    "rows_customer", "rows_contract", "rows_payment", "rows_lkp",
    "db_size_bytes", "bytes_per_row", "started_at",
]


def _sh(cmd, cwd, timeout):
    """Jalankan subprocess dengan batas waktu — TimeoutExpired ditangkap
    caller sebagai titik patah stop rule, bukan crash skrip ini."""
    print(f"    $ {' '.join(cmd)}")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if result.returncode != 0:
        raise RuntimeError(
            f"Command gagal (exit {result.returncode}) setelah {dt:.1f}s: {' '.join(cmd)}\n"
            f"stderr tail:\n{result.stderr[-2000:]}"
        )
    return dt


def _perf_log_line_count():
    if not os.path.exists(_PERF_LOG):
        return 0
    with open(_PERF_LOG) as f:
        return sum(1 for _ in f)


def _read_new_perf_rows(since_line_count):
    """Baris perf_runs.csv yang ditambahkan SEJAK checkpoint `since_line_count`
    — dipakai untuk atribusi durasi+RSS ke rung ini tanpa perlu subprocess
    mem-passing run_id balik ke proses parent."""
    if not os.path.exists(_PERF_LOG):
        return []
    with open(_PERF_LOG) as f:
        rows = list(csv.DictReader(f))
    return rows[max(0, since_line_count - 1):]  # -1: baris pertama adalah header


def _table_stats(db_url):
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    rows = {}
    with engine.connect() as conn:
        for t in TABLES:
            rows[t] = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
        db_size = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
    return rows, db_size


def _free_disk_gb(path="/"):
    return shutil.disk_usage(path).free / (1024 ** 3)


def run_rung(n_customers, seed, as_of, max_stage_seconds, db_url):
    result = {f: "" for f in _SCALE_SWEEP_FIELDS}
    result["n_customers"] = n_customers
    result["started_at"] = datetime.now().isoformat()

    print(f"\n=== Rung {n_customers:,} customer ===")
    print("  [1/3] reset DB...")
    subprocess.run([os.path.join(_ROOT, "scripts", "reset-demo.sh"), "--yes"],
                    cwd=_ROOT, check=True, capture_output=True, text=True)

    checkpoint = _perf_log_line_count()
    t0 = time.perf_counter()
    if n_customers >= BULK_CLONE_THRESHOLD:
        result["loader"] = "bulk_clone"
        print(f"  [2/3] load data via bulk_clone.py (seed={REAL_SEED_CUSTOMERS:,})...")
        _sh([sys.executable, "bulk_clone.py",
             "--target-customers", str(n_customers),
             "--seed-customers", str(min(REAL_SEED_CUSTOMERS, n_customers)),
             "--seed", str(seed)],
            cwd=_FAKER_DIR, timeout=max_stage_seconds)
    else:
        result["loader"] = "faker_asli"
        print("  [2/3] load data via generate-faker-realistic.py (simulator asli)...")
        _sh([sys.executable, "generate-faker-realistic.py",
             "--customers", str(n_customers), "--seed", str(seed),
             "--as-of", as_of, "--no-excel", "--dump-latents"],
            cwd=_FAKER_DIR, timeout=max_stage_seconds)
    result["generate_s"] = round(time.perf_counter() - t0, 2)

    print("  [3/3] train (WAJIB sebelum score — reset menghapus champion) + score...")
    train_scripts = [
        ("train_initial_model", "train_initial_s"),
        ("train_self_cure", "train_self_cure_s"),
        ("train_roll_forward", "train_roll_forward_s"),
        ("train_ptp_success", "train_ptp_success_s"),
    ]
    for script, field in train_scripts:
        dt = _sh([sys.executable, f"pipelines/{script}.py"], cwd=_ML_DIR, timeout=max_stage_seconds)
        result[field] = round(dt, 2)

    dt = _sh([sys.executable, "pipelines/daily_scoring.py"], cwd=_ML_DIR, timeout=max_stage_seconds)
    result["daily_scoring_s"] = round(dt, 2)

    new_rows = _read_new_perf_rows(checkpoint)
    train_rss = [float(r["peak_rss_mb"]) for r in new_rows if r["stage"].startswith("train_") and r["peak_rss_mb"]]
    score_rss = [float(r["peak_rss_mb"]) for r in new_rows
                 if not r["stage"].startswith("train_") and r["peak_rss_mb"]]
    if train_rss:
        result["peak_rss_train_mb"] = round(max(train_rss), 1)
    if score_rss:
        result["peak_rss_score_mb"] = round(max(score_rss), 1)

    rows, db_size = _table_stats(db_url)
    result["rows_customer"] = rows.get("customer_master")
    result["rows_contract"] = rows.get("contract_snapshot")
    result["rows_payment"] = rows.get("payment_history")
    result["rows_lkp"] = rows.get("lkp_interaction")
    result["db_size_bytes"] = db_size
    total_rows = sum(rows.values())
    result["bytes_per_row"] = round(db_size / total_rows, 1) if total_rows else ""

    result["status"] = "OK"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rungs", type=str, required=True, help="Daftar N customer dipisah koma, mis. 5000,10000,25000")
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--as-of", type=str, default=None)
    parser.add_argument("--max-stage-seconds", type=int, default=900)
    parser.add_argument("--max-rss-gb", type=float, default=12.0)
    parser.add_argument("--min-free-disk-gb", type=float, default=3.0)
    args = parser.parse_args(argv)

    sys.path.insert(0, _ML_DIR)
    from config.settings import DB_URL

    from datetime import date
    as_of = args.as_of or date.today().isoformat()

    os.makedirs(_RESULTS_DIR, exist_ok=True)
    write_header = not os.path.exists(_SCALE_SWEEP_CSV)
    f = open(_SCALE_SWEEP_CSV, "a", newline="")
    writer = csv.DictWriter(f, fieldnames=_SCALE_SWEEP_FIELDS)
    if write_header:
        writer.writeheader()

    rungs = [int(x) for x in args.rungs.split(",")]
    for i, n in enumerate(rungs):
        free_gb = _free_disk_gb()
        if free_gb < args.min_free_disk_gb:
            print(f"\n[STOP] Sisa disk {free_gb:.1f} GB < ambang {args.min_free_disk_gb} GB — "
                  f"ladder dihentikan SEBELUM rung {n:,}.")
            writer.writerow({**{k: "" for k in _SCALE_SWEEP_FIELDS}, "rung": i, "n_customers": n,
                              "status": "STOPPED_DISK", "break_reason": f"free_disk_gb={free_gb:.1f}"})
            f.flush()
            break

        try:
            result = run_rung(n, args.seed + i, as_of, args.max_stage_seconds, DB_URL)
            result["rung"] = i
            for train_field in ("peak_rss_train_mb",):
                val = result.get(train_field)
                if isinstance(val, (int, float)) and val / 1024.0 > args.max_rss_gb:
                    result["status"] = "OK_OVER_RSS_BUDGET"
                    result["break_reason"] = f"peak_rss_train_mb={val} > {args.max_rss_gb} GB"
                    writer.writerow(result)
                    f.flush()
                    print(f"\n[STOP] Rung {n:,} melewati budget RSS ({val / 1024:.1f} GB > "
                          f"{args.max_rss_gb} GB) — ladder dihentikan SETELAH rung ini selesai.")
                    f.close()
                    return 0
            writer.writerow(result)
            f.flush()
            print(f"  -> OK: generate={result['generate_s']}s train_total="
                  f"{sum(result[k] for k in ('train_initial_s','train_self_cure_s','train_roll_forward_s','train_ptp_success_s'))}s "
                  f"score={result['daily_scoring_s']}s")
        except subprocess.TimeoutExpired as exc:
            print(f"\n[STOP] Rung {n:,} timeout ({args.max_stage_seconds}s) di: {' '.join(exc.cmd)}")
            writer.writerow({**{k: "" for k in _SCALE_SWEEP_FIELDS}, "rung": i, "n_customers": n,
                              "status": "STOPPED_TIMEOUT", "break_stage": ' '.join(exc.cmd),
                              "break_reason": f"exceeded max_stage_seconds={args.max_stage_seconds}"})
            f.flush()
            break
        except RuntimeError as exc:
            print(f"\n[STOP] Rung {n:,} error: {exc}")
            writer.writerow({**{k: "" for k in _SCALE_SWEEP_FIELDS}, "rung": i, "n_customers": n,
                              "status": "STOPPED_ERROR", "break_reason": str(exc)[:500]})
            f.flush()
            break

    f.close()
    print(f"\nHasil: {_SCALE_SWEEP_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

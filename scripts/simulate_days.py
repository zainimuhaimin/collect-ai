#!/usr/bin/env python3
"""TASK-S2 — Staging -> replay bertahap ke tabel live + rescoring asli.

Simulasikan arus data harian yang SUNGGUHAN: pembayaran/interaksi baru
"masuk" hari demi hari, status kontrak terpengaruh, `daily_scoring.py` ASLI
(tidak dimodifikasi) jalan ulang, dan aplikasi (Dashboard, Customer Detail,
Contract Detail) otomatis menunjukkan hasilnya — tanpa script swap-tampilan
terpisah. Lihat TASK-S2 di post-presentation-review-tasks.md untuk desain
lengkap dan alasannya (kenapa BUKAN memanggil faker berulang dengan --as-of
berbeda — itu terbukti gagal di TASK-S1: --as-of menggeser SELURUH kalender
secara seragam, jadi dpd/cycle/OTS tidak pernah berubah).

⚠️ RISIKO — skrip ini menulis ke tabel LIVE yang dibaca aplikasi. Baris yang
ditulis bisa bertanggal simulasi (bisa di masa depan relatif hari nyata).
JANGAN jalankan di database yang sedang dipakai untuk keperluan lain secara
bersamaan. Setelah sesi demo/capture selesai, jalankan ulang
`scripts/reset-demo.sh` lalu generate data present-day biasa.

⚠️ BATAS HORIZON — jadwal cicilan (`--dump-schedule`) hanya mencakup due date
historis (<= as_of - 30 hari) PLUS SATU angsuran tambahan yang jatuh di
jendela label 30 hari (lihat `_due_date()` di faker/generate-faker-
realistic.py). Simulasi hari-per-hari HANYA valid dalam jendela 30 hari itu
— pilih tanggal terakhir ladder <= D0+30. Melebihi itu, kontrak tidak punya
jadwal lagi dan overdue count-nya akan diam (tidak salah, hanya tidak
lengkap) — dicatat sebagai keterbatasan yang diketahui, bukan bug tersembunyi.

TIGA MODE PAKAI:

**Mode A — sekali jalan, semua tanggal** (untuk menghasilkan laporan
pergerakan dalam satu perintah):

    python scripts/simulate_days.py --dates 2026-08-01,2026-08-08,2026-08-31 \\
        --customers 500 --seed 20260101

**Mode B + C — bertahap, supaya perubahan skor bisa DILIHAT DI APLIKASI di
antara langkah** (aplikasi membaca `ai_intelligence_output`, yang ditulis ulang
tiap tanggal — jadi refresh browser setelah tiap langkah akan menampilkan skor
tanggal itu):

    # B. siapkan D0 saja, lalu berhenti. --horizon = tanggal terakhir yang
    #    NANTI akan dituju (staging digenerate s/d situ; default D0+30).
    python scripts/simulate_days.py --dates 2026-08-01 --bootstrap-only \\
        --horizon 2026-08-31 --customers 500 --seed 20260101
    #    -> buka aplikasi, catat skor satu kontrak

    # C. majukan tanggal, sebanyak yang diinginkan, kapan saja.
    python scripts/simulate_days.py --dates 2026-08-08 --continue
    #    -> refresh aplikasi, skor kontrak yang sama sudah berubah
    python scripts/simulate_days.py --dates 2026-08-31 --continue

Mode C membaca tanggal terakhir yang sudah tersimulasi dari `scoring_history`,
jadi tidak perlu mengingat/mengetik ulang tanggal sebelumnya dan tidak bisa
salah sinkron dengan isi DB. Mode C TIDAK reset dan TIDAK training ulang.

Bootstrap D0 dilakukan sekali (Mode A tanggal pertama, atau Mode B): TRUNCATE
tabel live + derivatif ML, muat staging s/d D0, latih ke-4 model, jalankan
`daily_scoring.py --date D0`. Tanggal berikutnya HANYA menyuap data baru +
rescoring — TIDAK ada training ulang (champion dari D0 dibekukan sepanjang
simulasi, dibuktikan lewat `models/registry.json` tidak berubah).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(ROOT, "app", "machine-learning")
FAKER_DIR = os.path.join(ROOT, "faker")
sys.path.insert(0, ML_DIR)

from config.settings import DB_URL  # noqa: E402
from src.contract_state import derive_contract_terms, recompute_contract_state  # noqa: E402
from src.db_write import copy_dataframe  # noqa: E402
from src.cbs_builder import update_cbs  # noqa: E402

# Tabel ML derivatif — dihapus di bootstrap D0 supaya tidak mencampur ID dari
# populasi/sesi simulasi sebelumnya (sama alasannya dengan
# faker/helpers/database.py::DERIVED_ML_TABLES, tapi TIDAK termasuk
# ai_intelligence_output di sini — itu ditangani terpisah lewat arsip
# scoring_history sebelum truncate, bukan dihapus polos).
_DERIVED_ML_TABLES_BOOTSTRAP = [
    "customer_behavioral_standing", "scoring_feature_snapshot", "scoring_labels",
    "shadow_scores", "model_monitoring_log",
    "restructuring_recommendation_output", "restructuring_group_map",
    "restructuring_history", "restructuring_approval_log",
]


def _run(cmd, cwd=None):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def _generate_staging(as_of: str, seed: int, customers: int):
    print(f"\n=== [staging] generate SEKALI, as_of={as_of}, seed={seed}, customers={customers} ===")
    _run(
        [
            sys.executable, "generate-faker-realistic.py",
            "--seed", str(seed), "--customers", str(customers),
            "--as-of", as_of, "--reset", "--no-excel",
            "--dump-latents", "--dump-schedule", "--table-prefix", "stg_",
        ],
        cwd=FAKER_DIR,
    )


def _recompute_and_update_contracts(engine, as_of_date: str):
    with engine.connect() as conn:
        df_contract = pd.read_sql(
            text("SELECT contract_no, loan_amount, installment_amount, interest_rate FROM contract_snapshot"),
            conn,
        )
        df_schedule = pd.read_sql(
            text("SELECT contract_no, installment_no, due_date, installment_amount FROM stg_installment_schedule"),
            conn,
        )
        df_payment = pd.read_sql(
            text("SELECT contract_no, due_date, actual_pay_date, payment_amount, pay_status FROM payment_history"),
            conn,
        )

    terms = derive_contract_terms(df_contract)
    state = recompute_contract_state(as_of_date, df_schedule, df_payment, terms)
    if state.empty:
        print(f"  [contract_state] tidak ada kontrak dengan jadwal <= {as_of_date} — dilewati")
        return

    state = state[[
        "contract_no", "dpd_current", "cycle", "overdue_installment_count", "prnc_ots", "intr_ots",
    ]].copy()
    state["dpd_current"] = state["dpd_current"].astype(int)
    state["overdue_installment_count"] = state["overdue_installment_count"].astype(int)

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TEMP TABLE _contract_state_update ("
            "contract_no VARCHAR(30), dpd_current INT, cycle VARCHAR(20), "
            "overdue_installment_count INT, prnc_ots NUMERIC(15,2), intr_ots NUMERIC(15,2)"
            ") ON COMMIT DROP"
        ))
        copy_dataframe(conn, "_contract_state_update", state)
        result = conn.execute(text(
            "UPDATE contract_snapshot cs SET "
            "dpd_current = u.dpd_current, cycle = u.cycle, "
            "overdue_installment_count = u.overdue_installment_count, "
            "prnc_ots = u.prnc_ots, intr_ots = u.intr_ots "
            "FROM _contract_state_update u WHERE cs.contract_no = u.contract_no"
        ))
    print(f"  [contract_state] {result.rowcount:,} kontrak diperbarui (as_of={as_of_date})")


def _archive_current_ai_output(engine):
    with engine.begin() as conn:
        result = conn.execute(text(
            "INSERT INTO scoring_history "
            "(snapshot_date, contract_no, cust_id, risk_segment, recovery_score, "
            " self_cure_probability, roll_forward_risk, ptp_success_probability, "
            " nba_recommendation, nba_trigger, priority_level, dpd_current, total_ots) "
            "SELECT ai.scoring_date, ai.contract_no, ai.cust_id, ai.risk_segment, ai.recovery_score, "
            "       ai.self_cure_probability, ai.roll_forward_risk, ai.ptp_success_probability, "
            "       ai.nba_recommendation, ai.nba_trigger, ai.priority_level, cs.dpd_current, "
            "       COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0) "
            "FROM ai_intelligence_output ai LEFT JOIN contract_snapshot cs ON cs.contract_no = ai.contract_no "
            "ON CONFLICT (contract_no, snapshot_date) DO NOTHING"
        ))
    print(f"  [scoring_history] {result.rowcount:,} baris diarsipkan")


def _simulated_date_range(engine) -> tuple[str | None, str | None]:
    """(D0, tanggal terakhir) yang sudah tersimulasi, dibaca dari
    `scoring_history` — satu-satunya tabel yang menumpuk per tanggal, jadi ia
    yang jadi sumber kebenaran "sudah sampai mana simulasinya". Dipakai mode
    `--continue` supaya tidak perlu user mengingat/mengetik ulang tanggal
    sebelumnya (dan tidak bisa salah ketik jadi tidak sinkron dengan DB)."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MIN(snapshot_date), MAX(snapshot_date) FROM scoring_history")
        ).fetchone()
    if not row or row[1] is None:
        return None, None
    return str(row[0]), str(row[1])


def _warn_if_beyond_horizon(d0: str, target: str):
    span = (pd.Timestamp(target) - pd.Timestamp(d0)).days
    if span > 30:
        print(
            f"⚠️  PERINGATAN: {target} adalah {span} hari setelah D0 ({d0}), melebihi "
            f"jendela 30 hari yang dicakup jadwal cicilan. Kontrak akan berhenti "
            f"bertambah overdue setelah hari ke-30 — lihat docstring modul ini.",
            file=sys.stderr,
        )


def _ingest_window(engine, prev_date: str | None, this_date: str):
    with engine.begin() as conn:
        pay_filter = "actual_pay_date > :prev AND actual_pay_date <= :this" if prev_date else "actual_pay_date <= :this"
        df_pay = pd.read_sql(
            text(f"SELECT * FROM stg_payment_history WHERE {pay_filter}"),
            conn, params={"prev": prev_date, "this": this_date} if prev_date else {"this": this_date},
        )
        if not df_pay.empty:
            copy_dataframe(conn, "payment_history", df_pay)

        lkp_filter = "action_date > :prev AND action_date <= :this" if prev_date else "action_date <= :this"
        df_lkp = pd.read_sql(
            text(f"SELECT * FROM stg_lkp_interaction WHERE {lkp_filter}"),
            conn, params={"prev": prev_date, "this": this_date} if prev_date else {"this": this_date},
        )
        if not df_lkp.empty:
            copy_dataframe(conn, "lkp_interaction", df_lkp)
    print(f"  [ingest] +{len(df_pay):,} payment_history, +{len(df_lkp):,} lkp_interaction "
          f"(jendela ({prev_date or '-inf'}, {this_date}])")


def _bootstrap_d0(engine, d0: str):
    print(f"\n=== [bootstrap D0={d0}] TRUNCATE tabel live + derivatif ML ===")
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE customer_master, contract_snapshot, payment_history, lkp_interaction, "
            "ai_intelligence_output, scoring_history, "
            + ", ".join(_DERIVED_ML_TABLES_BOOTSTRAP) + " CASCADE"
        ))

        df_cust = pd.read_sql(text("SELECT * FROM stg_customer_master"), conn)
        copy_dataframe(conn, "customer_master", df_cust)

        df_contract = pd.read_sql(text("SELECT * FROM stg_contract_snapshot"), conn)
        copy_dataframe(conn, "contract_snapshot", df_contract)
    print(f"  customer_master: {len(df_cust):,} baris, contract_snapshot: {len(df_contract):,} baris")

    _ingest_window(engine, None, d0)
    _recompute_and_update_contracts(engine, d0)
    update_cbs(engine, reference_date=d0)

    print(f"\n=== [bootstrap D0={d0}] latih ke-4 model dari state D0 (SEKALI) ===")
    for script in [
        "train_initial_model.py", "train_self_cure.py",
        "train_roll_forward.py", "train_ptp_success.py",
    ]:
        _run([sys.executable, os.path.join("pipelines", script)], cwd=ML_DIR)

    print(f"\n=== [bootstrap D0={d0}] daily_scoring.py --date {d0} (ASLI, tidak dimodifikasi) ===")
    _run([sys.executable, os.path.join("pipelines", "daily_scoring.py"), "--date", d0], cwd=ML_DIR)
    _archive_current_ai_output(engine)


def _simulate_next_day(engine, prev_date: str, this_date: str):
    """Urutan WAJIB: ingest -> recompute -> CBS -> TRUNCATE -> score -> ARSIPKAN.
    Arsip dilakukan SETELAH scoring hari ini (bukan sebelum truncate di
    iterasi berikutnya) — supaya hari TERAKHIR ladder juga ikut terarsip,
    bukan hanya D0..D(n-1)."""
    print(f"\n=== [{this_date}] hari berikutnya (D0+{(pd.Timestamp(this_date) - pd.Timestamp(prev_date)).days}) ===")
    _ingest_window(engine, prev_date, this_date)
    _recompute_and_update_contracts(engine, this_date)
    update_cbs(engine, reference_date=this_date)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ai_intelligence_output"))
    print(f"  [scoring] daily_scoring.py --date {this_date} (ASLI, TANPA training ulang)")
    _run([sys.executable, os.path.join("pipelines", "daily_scoring.py"), "--date", this_date], cwd=ML_DIR)
    _archive_current_ai_output(engine)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dates", required=True, help="Tanggal simulasi, dipisah koma, urut naik.")
    parser.add_argument("--customers", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument(
        "--bootstrap-only", action="store_true",
        help="Mode B: hanya generate staging + bootstrap D0, lalu BERHENTI "
             "(supaya bisa dilihat di aplikasi dulu). --dates harus 1 tanggal. "
             "Lanjutkan dengan --continue.",
    )
    parser.add_argument(
        "--horizon", default=None,
        help="Hanya untuk --bootstrap-only: tanggal TERAKHIR yang nanti akan "
             "dituju. Staging digenerate s/d tanggal ini supaya transaksi masa "
             "depan tersedia untuk --continue. Default: D0 + 30 hari.",
    )
    parser.add_argument(
        "--continue", dest="continue_mode", action="store_true",
        help="Mode C: majukan simulasi dari state yang SUDAH ADA di DB (tidak "
             "reset, tidak training ulang). Tanggal sebelumnya dibaca otomatis "
             "dari scoring_history.",
    )
    args = parser.parse_args()

    if args.bootstrap_only and args.continue_mode:
        print("--bootstrap-only dan --continue tidak bisa dipakai bersamaan.", file=sys.stderr)
        sys.exit(1)

    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    if not dates:
        print("--dates kosong.", file=sys.stderr)
        sys.exit(1)
    if sorted(dates) != dates:
        print(f"--dates harus urut naik, dapat: {dates}", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(DB_URL)

    # ── Mode B: bootstrap saja, lalu berhenti ────────────────────────────
    if args.bootstrap_only:
        if len(dates) != 1:
            print("--bootstrap-only butuh TEPAT 1 tanggal di --dates (yaitu D0).", file=sys.stderr)
            sys.exit(1)
        d0 = dates[0]
        horizon = args.horizon or str((pd.Timestamp(d0) + pd.Timedelta(days=30)).date())
        if pd.Timestamp(horizon) < pd.Timestamp(d0):
            print(f"--horizon ({horizon}) tidak boleh sebelum D0 ({d0}).", file=sys.stderr)
            sys.exit(1)
        _warn_if_beyond_horizon(d0, horizon)
        _generate_staging(as_of=horizon, seed=args.seed, customers=args.customers)
        _bootstrap_d0(engine, d0)
        print(f"\n=== Bootstrap D0={d0} selesai (staging s/d {horizon}) ===")
        print("Buka aplikasi sekarang — skor yang tampil adalah keadaan D0.")
        print(f"Majukan tanggal dengan:\n"
              f"  python scripts/simulate_days.py --dates <tanggal-berikutnya> --continue")
        return

    # ── Mode C: lanjutkan dari state yang sudah ada ──────────────────────
    if args.continue_mode:
        d0_existing, prev = _simulated_date_range(engine)
        if prev is None:
            print(
                "Tidak ada tanggal tersimulasi di scoring_history — belum ada state "
                "untuk dilanjutkan. Jalankan bootstrap dulu:\n"
                "  python scripts/simulate_days.py --dates <D0> --bootstrap-only --horizon <tanggal-akhir>",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"=== [continue] state DB saat ini: D0={d0_existing}, terakhir={prev} ===")
        for d in dates:
            if pd.Timestamp(d) <= pd.Timestamp(prev):
                print(
                    f"Tanggal {d} tidak lebih baru dari tanggal terakhir yang sudah "
                    f"tersimulasi ({prev}) — simulasi hanya bisa maju.",
                    file=sys.stderr,
                )
                sys.exit(1)
            _warn_if_beyond_horizon(d0_existing, d)
            _simulate_next_day(engine, prev, d)
            prev = d
        print(f"\n=== Selesai. Sekarang di tanggal {prev} ===")
        print("Refresh aplikasi — skor yang tampil sudah keadaan tanggal ini.")
        print("Bandingkan seluruh tanggal: python scripts/movement_report.py")
        return

    # ── Mode A (default): semua tanggal sekaligus ───────────────────────
    if len(dates) < 2:
        print(
            "Butuh minimal 2 tanggal (D0 + minimal 1 hari berikutnya).\n"
            "Kalau memang hanya ingin menyiapkan D0 dulu, pakai --bootstrap-only.",
            file=sys.stderr,
        )
        sys.exit(1)
    d0, horizon = dates[0], dates[-1]
    _warn_if_beyond_horizon(d0, horizon)

    _generate_staging(as_of=horizon, seed=args.seed, customers=args.customers)
    _bootstrap_d0(engine, d0)

    prev = d0
    for d in dates[1:]:
        _simulate_next_day(engine, prev, d)
        prev = d

    print(f"\n=== Selesai. {len(dates)} tanggal disimulasikan: {dates} ===")
    print("Buka aplikasi langsung — tabel live sudah menunjukkan keadaan tanggal terakhir.")
    print(f"Laporan pergerakan: python scripts/movement_report.py")


if __name__ == "__main__":
    main()

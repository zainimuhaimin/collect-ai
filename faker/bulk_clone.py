"""Jalur data cepat KHUSUS uji performa (post-presentation-review-tasks.md
TASK-P3). Bukan pengganti generate-faker-realistic.py untuk apa pun selain
sweep volume (P4/P6) — lihat KARANTINA di bawah.

Kenapa ini perlu: simulator asli men-generate tiap contract path lewat loop
Python row-by-row (`simulate_contract_paths`, ~beberapa ratus baris logika
per kontrak). Itu bagus untuk realisme statistik di rung kecil (5K-50K), tapi
generate 1 juta+ customer lewat jalur itu bisa makan puluhan jam. bulk_clone.py
men-generate SATU populasi benih yang benar (lewat simulator asli, fungsi yang
sama persis dipakai generate-faker-realistic.py — bukan reimplementasi), lalu
mereplikasinya dengan perturbasi (offset ID, jitter tanggal & nominal) sampai
volume target, ditulis per blok lewat COPY (src TASK-P3) supaya RAM tetap
konstan terhadap jumlah blok.

⚠️ KARANTINA — dampak nyata, bukan sekadar peringatan.
Setiap baris yang ditulis script ini (TERMASUK populasi benihnya) diberi
prefiks ID `PCxxxx-` (xxxx = nomor blok) — lihat _remap_ids(). Prefiks ini
membuat baris hasil script ini SELALU bisa dibedakan dari data asli
generate-faker-realistic.py murni tanpa perlu tabel/kolom tambahan. Data
ini TIDAK BOLEH dipakai untuk:
  - evaluasi akurasi Area 3 (Tier 4 latent oracle) — replikasi merusak
    korespondensi latents<->baris, `w`/`c` blok ke-2 dst TIDAK LAGI benar
    untuk baris yang sudah di-remap ID-nya
  - melatih model yang angkanya dilaporkan
Skrip ini SENGAJA tidak pernah memanggil kode `--dump-latents`, dan
menginvalidasi (rename) `_audit_latents.parquet/csv` yang ada di direktori
ini kalau ditemukan, supaya join yang salah (menggabungkan latents lama
dengan data clone baru) jadi mustahil dilakukan tanpa sadar, bukan hanya
tidak dianjurkan.

Pemakaian:
    python bulk_clone.py --target-customers 250000 --seed-customers 20000 --reset
"""
from __future__ import annotations

import argparse
import glob
import gc
import importlib.util
import math
import os
import random
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

_FAKER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _FAKER_DIR)

from helpers.database import append_dataframes_to_postgres, reset_tables  # noqa: E402


def _load_generator_module():
    """generate-faker-realistic.py punya tanda hubung di nama file — tidak
    bisa di-`import` biasa, jadi dimuat lewat importlib. Ini memuat modul
    yang SAMA persis (bukan salinan/reimplementasi) supaya populasi benih
    dijamin lewat simulator asli, bukan pendekatan yang berbeda."""
    path = os.path.join(_FAKER_DIR, "generate-faker-realistic.py")
    spec = importlib.util.spec_from_file_location("_gfr_bulk_clone", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Kolom tanggal & nominal per tabel — dipakai _jitter_block() (lihat
# docstring modul: jitter per-blok, BUKAN per-baris, supaya delta internal
# seperti DELAY_DAYS/amortisasi tidak rusak — sama prinsipnya dengan temuan
# TASK-S1 soal whole-calendar shift faker sendiri).
_DATE_COLS = {
    "contract": ["MATURITY_DATE"],
    "payment": ["DUE_DATE", "ACTUAL_PAY_DATE"],
    "lkp": ["ACTION_DATE", "PROMISE_DATE"],
}
_AMOUNT_COLS = {
    "contract": ["PRNC_OTS", "INTR_OTS", "AMBC", "LOAN_AMOUNT", "INSTALLMENT_AMOUNT", "LATE_FEE_AMOUNT"],
    "payment": ["PAYMENT_AMOUNT"],
    "lkp": ["PTP_AMOUNT"],
}
_ID_COLS = {
    "customer": ["CUST_ID"],
    "contract": ["CONTRACT_NO", "CUST_ID"],
    "payment": ["PAYMENT_ID", "CONTRACT_NO"],
    "lkp": ["LKP_ID", "CONTRACT_NO"],
}


def _remap_ids(df: pd.DataFrame, kind: str, block_tag: str) -> pd.DataFrame:
    """Prefiks SEMUA kolom ID dengan block_tag (mis. 'PC0003-'). Menjamin
    keunikan lintas blok DAN menandai karantina — lihat docstring modul.
    Prepending (bukan mengganti angka) otomatis menjaga relasi
    cust_id/contract_no antar 4 tabel dalam blok yang sama, karena semua
    kemunculan ID yang sama di-prefiks dengan tag yang sama persis."""
    out = df.copy()
    for col in _ID_COLS.get(kind, []):
        if col in out.columns:
            out[col] = block_tag + out[col].astype(str)
    return out


def _jitter_block(df: pd.DataFrame, kind: str, rng: random.Random, jitter_days: int, jitter_amount_pct: float) -> pd.DataFrame:
    """Satu offset hari (bukan per-baris) untuk semua kolom tanggal, dan
    satu faktor pengali untuk semua kolom nominal — dipilih supaya blok
    tidak identik byte-per-byte dengan blok lain, tanpa merusak konsistensi
    internal (delay_days, rasio ots/loan, dst tidak dihitung ulang dari
    tanggal/nominal ini di manapun downstream, jadi shift/scale seragam
    aman)."""
    out = df.copy()
    day_shift = timedelta(days=rng.randint(-jitter_days, jitter_days)) if jitter_days else timedelta(0)
    for col in _DATE_COLS.get(kind, []):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce") + day_shift
            out[col] = out[col].dt.date

    factor = 1.0 + rng.uniform(-jitter_amount_pct, jitter_amount_pct) if jitter_amount_pct else 1.0
    for col in _AMOUNT_COLS.get(kind, []):
        if col in out.columns:
            out[col] = (pd.to_numeric(out[col], errors="coerce") * factor).round(2)
    return out


def _invalidate_stale_latents():
    for path in glob.glob(os.path.join(_FAKER_DIR, "_audit_latents.*")):
        if path.endswith(".INVALIDATED"):
            continue
        target = path + ".INVALIDATED"
        os.rename(path, target)
        print(f"[bulk_clone] Latents lama diinvalidasi (bukan dari clone, tapi berisiko di-join salah): {target}")


def generate_seed_population(seed_customers: int, seed: int, as_of: date):
    """Generate SATU populasi benih lewat fungsi simulator ASLI
    (generate-faker-realistic.py) — bukan reimplementasi. Tidak pernah
    memanggil jalur --dump-latents (lihat KARANTINA di docstring modul)."""
    gfr = _load_generator_module()
    gfr.set_seeds(seed)

    t_cut = as_of - timedelta(days=gfr.LABEL_WINDOW_DAYS)

    df_customer, latents = gfr.generate_customer_master(seed_customers)
    df_terms = gfr.build_contract_terms(df_customer, latents, as_of)
    paths, _mu_label = gfr.simulate_contract_paths(df_terms, t_cut, as_of)
    df_lkp = gfr.generate_lkp_history(df_terms, paths, t_cut, as_of)

    lkp_lookup, interactions_by_contract = {}, {}
    if not df_lkp.empty:
        for contract_no, grp in df_lkp.sort_values("ACTION_DATE").groupby("CONTRACT_NO"):
            dates = [d.date() for d in pd.to_datetime(grp["ACTION_DATE"])]
            lkp_lookup[contract_no] = list(zip(dates, grp["TREATMENT_TYPE"]))
            interactions_by_contract[contract_no] = dates

    df_payment = gfr.generate_payment_history(df_terms, paths, lkp_lookup, interactions_by_contract)
    df_contract = gfr.assemble_contract_snapshot(df_terms, paths, "cutoff")

    return df_customer, df_contract, df_payment, df_lkp


def run_bulk_clone(target_customers: int, seed_customers: int, seed: int, as_of: date,
                    jitter_days: int, jitter_amount_pct: float, do_reset: bool):
    if seed_customers > target_customers:
        seed_customers = target_customers

    print(f"[bulk_clone] Generating seed population lewat simulator asli: {seed_customers:,} customers...")
    df_customer, df_contract, df_payment, df_lkp = generate_seed_population(seed_customers, seed, as_of)
    print(f"[bulk_clone] Seed: {len(df_customer):,} customer / {len(df_contract):,} contract / "
          f"{len(df_payment):,} payment / {len(df_lkp):,} lkp")

    _invalidate_stale_latents()

    if do_reset:
        print("[bulk_clone] Resetting target tables...")
        reset_tables(["customer_master", "contract_snapshot", "payment_history", "lkp_interaction"],
                     include_derived=True)

    num_blocks = math.ceil(target_customers / seed_customers)
    rng = random.Random(seed)
    total_written = 0

    for b in range(num_blocks):
        block_tag = f"PC{b:04d}-"
        n_this_block = min(seed_customers, target_customers - b * seed_customers)

        cust_block = _remap_ids(df_customer.iloc[:n_this_block].copy(), "customer", block_tag)
        keep_custs = set(cust_block["CUST_ID"].str[len(block_tag):])
        # contract/payment/lkp difilter ke customer yang masuk block ini
        # DULU (kalau n_this_block < seed_customers, blok terakhir parsial),
        # baru di-remap — urutan sebaliknya akan me-remap baris yang lalu
        # dibuang, sia-sia.
        contract_block = df_contract[df_contract["CUST_ID"].isin(keep_custs)].copy()
        kept_contracts = set(contract_block["CONTRACT_NO"])
        payment_block = df_payment[df_payment["CONTRACT_NO"].isin(kept_contracts)].copy()
        lkp_block = df_lkp[df_lkp["CONTRACT_NO"].isin(kept_contracts)].copy()

        contract_block = _remap_ids(contract_block, "contract", block_tag)
        payment_block = _remap_ids(payment_block, "payment", block_tag)
        lkp_block = _remap_ids(lkp_block, "lkp", block_tag)

        if b > 0:  # blok 0 = populasi benih apa adanya (masih di-prefiks PC0000-, tapi tanpa jitter)
            contract_block = _jitter_block(contract_block, "contract", rng, jitter_days, jitter_amount_pct)
            payment_block = _jitter_block(payment_block, "payment", rng, jitter_days, jitter_amount_pct)
            lkp_block = _jitter_block(lkp_block, "lkp", rng, jitter_days, jitter_amount_pct)

        append_dataframes_to_postgres(
            {
                "customer_master": cust_block,
                "contract_snapshot": contract_block,
                "payment_history": payment_block,
                "lkp_interaction": lkp_block,
            },
            require_empty=False,
        )
        total_written += len(cust_block)
        print(f"[bulk_clone] Blok {b + 1}/{num_blocks} ({block_tag.rstrip('-')}): "
              f"{len(cust_block):,} customer tertulis (total {total_written:,}/{target_customers:,})")

        del cust_block, contract_block, payment_block, lkp_block
        gc.collect()

    print(f"[bulk_clone] Selesai: {total_written:,} customer (perfclone, {num_blocks} blok).")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-customers", type=int, required=True)
    parser.add_argument("--seed-customers", type=int, default=20000,
                         help="Ukuran populasi benih yang di-generate lewat simulator asli (default 20000)")
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--as-of", type=str, default=None, help="YYYY-MM-DD (default: hari ini)")
    parser.add_argument("--jitter-days", type=int, default=5)
    parser.add_argument("--jitter-amount-pct", type=float, default=0.05)
    parser.add_argument("--reset", action="store_true", help="TRUNCATE tabel target sebelum menulis")
    args = parser.parse_args(argv)

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()

    run_bulk_clone(
        target_customers=args.target_customers,
        seed_customers=args.seed_customers,
        seed=args.seed,
        as_of=as_of,
        jitter_days=args.jitter_days,
        jitter_amount_pct=args.jitter_amount_pct,
        do_reset=args.reset,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

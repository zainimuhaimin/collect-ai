"""Chunked, memory-bounded feature computation (post-presentation-review-
tasks.md TASK-P5 item 1 — "chunked read + agregasi SQL", sebelumnya SENGAJA
ditunda karena dianggap "pekerjaan multi-hari", dikerjakan di sesi lanjutan
setelah user eksplisit meminta menyelesaikan temuan yang memakan waktu.
Lihat performance-report.md §3d/§6 untuk histori keputusan penundaan itu).

`compute_contract_features()`/`compute_customer_features()`
(`src/feature_engineering.py`) **TIDAK DIUBAH SAMA SEKALI** — kontrak fungsi
(input dataframe mentah, 57 test di `tests/test_features.py`) tetap seperti
semula. Modul ini murni ORKESTRASI: alih-alih memuat SELURUH
`payment_history`/`lkp_interaction` ke pandas sekaligus (dinding RAM
sebenarnya di N besar, lihat performance-report.md §4c — training di 100rb
customer memuat ~360rb baris gabungan dan itu SEBELUM dikali 50x ke 5 juta),
data dipecah per BATCH `cust_id` dan fungsi ASLI dipanggil pada tiap batch,
hasilnya digabung.

Kebenaran pendekatan ini bertumpu pada SATU invarian yang harus tetap benar
selama `compute_contract_features()`/`compute_customer_features()` tidak
diubah: SETIAP agregasi di kedua fungsi itu (mode `recovery_source`,
`delay_trend` OLS per bulan, PTP-kept windowed join, `channel_effectiveness`,
lineage restrukturisasi) murni dalam lingkup SATU `cust_id` — tidak ada satu
pun yang menyilang customer. Mempartisi berdasarkan `cust_id` dan
menggabungkan hasil per-batch karena itu identik secara matematis dengan
memanggil fungsi yang sama pada dataset penuh sekali jalan — dibuktikan lewat
parity test (`tests/test_features_chunked.py`), bukan diasumsikan benar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.feature_engineering import compute_contract_features, compute_customer_features


def _batched(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def compute_features_chunked_from_loader(
    df_contract: pd.DataFrame,
    df_customer: pd.DataFrame,
    load_batch_fn,
    reference_date=None,
    feature_cutoff_date=None,
    batch_size: int = 5000,
    payment_globally_nonempty: bool = True,
    need_customer_features: bool = True,
    pass_customer_to_contract_features: bool = True,
):
    """Inti orkestrasi, TANPA dependency DB — ``load_batch_fn(contract_nos:
    list) -> (df_payment_batch, df_lkp_batch)`` disuntik oleh caller. Dipisah
    dari `compute_features_chunked()` (wrapper DB nyata di bawah) supaya
    logika pemecahan-batch-dan-gabung bisa ditest dengan loader palsu
    (filter in-memory), TANPA butuh Postgres sama sekali — pola sama seperti
    `build_payload()` di AI Reasoning (fungsi murni, I/O disuntik dari luar).

    Kembalikan ``(df_contract_features, df_customer_features)`` — bentuk SAMA
    seperti memanggil ``compute_contract_features()``/``compute_customer_
    features()`` langsung pada payment_history/lkp_interaction PENUH.

    Batch key HARUS `cust_id` (bukan `contract_no`) — `compute_customer_
    features()` mengagregasi LINTAS kontrak milik satu customer (delay_trend,
    channel_effectiveness, ptp_reliability_index, dst), jadi satu customer
    dan SELURUH kontraknya wajib berada di batch yang sama.

    ``payment_globally_nonempty`` (default True, cocok untuk produksi —
    payment_history praktis TIDAK PERNAH kosong total): `compute_contract_
    features()` punya SATU cabang yang bergantung pada keadaan GLOBAL, bukan
    per-kontrak — kalau dataframe payment yang diberikan (`p`) kosong TOTAL,
    ia mengisi `recovery_source_encoded=0` secara eksplisit; kalau `p` TIDAK
    kosong tapi satu kontrak tertentu memang tidak punya baris payment, hasil
    merge meninggalkan NaN (BUKAN 0) untuk kontrak itu — dua kode jalur yang
    sengaja berbeda di fungsi aslinya. Chunking bisa membuat SATU BATCH
    kebetulan tidak punya payment sama sekali (meski tabel penuh TIDAK
    kosong), yang tanpa koreksi ini akan salah mengambil cabang "kosong
    total" untuk kontrak yang seharusnya NaN. Dikoreksi di sini (bukan di
    `feature_engineering.py`) supaya fungsi aslinya TIDAK disentuh sama
    sekali — lihat `tests/test_features_chunked.py` untuk pembuktian.

    ``need_customer_features`` (default True): `daily_scoring.py` hanya
    butuh `df_customer_features` saat bootstrap CBS pertama kali
    (`customer_behavioral_standing` masih kosong) — di luar itu, menghitung
    customer_features tiap hari CUMA-CUMA (tidak dipakai) padahal masih
    butuh kerja groupby per batch. Set `False` untuk skip komputasi itu dan
    kembalikan `df_customer_features=None`.

    ``pass_customer_to_contract_features`` — ⚠️ WAJIB disamakan dengan
    caller aslinya, BUKAN default yang aman ditebak: `train_*.py` MEMANGGIL
    `compute_contract_features(..., df_customer=df_customer)` (memengaruhi
    `installment_to_income_ratio` — pakai income level customer ASLI), tapi
    `daily_scoring.py` memanggilnya TANPA `df_customer` sama sekali
    (`installment_to_income_ratio` selalu pakai fallback flat 5.000.000) —
    dua caller yang SUDAH berbeda perilaku SEBELUM chunking ada (train/serve
    skew pre-existing, ditemukan lewat parity gate sesi ini, lihat
    performance-report.md §3f). Chunked path HARUS meniru perilaku caller
    yang sedang dipanggil, bukan "memperbaiki" skew ini diam-diam.
    """
    cust_col = "cust_id" if "cust_id" in df_contract.columns else "CUST_ID"
    contract_no_col = "contract_no" if "contract_no" in df_contract.columns else "CONTRACT_NO"
    cust_col_customer = "cust_id" if "cust_id" in df_customer.columns else "CUST_ID"

    all_cust_ids = sorted(df_contract[cust_col].dropna().unique().tolist())

    contract_chunks = []
    customer_chunks = []
    for batch in _batched(all_cust_ids, batch_size):
        c_batch = df_contract[df_contract[cust_col].isin(batch)].copy()
        if c_batch.empty:
            continue
        contract_nos = c_batch[contract_no_col].tolist()
        cust_batch = df_customer[df_customer[cust_col_customer].isin(batch)].copy()

        p_batch, l_batch = load_batch_fn(contract_nos)

        cf_batch = compute_contract_features(
            c_batch, p_batch, l_batch, reference_date,
            df_customer=(cust_batch if pass_customer_to_contract_features else None),
            feature_cutoff_date=feature_cutoff_date,
        )
        if p_batch.empty and payment_globally_nonempty and "recovery_source_encoded" in cf_batch.columns:
            cf_batch = cf_batch.copy()
            cf_batch["recovery_source_encoded"] = np.nan
        contract_chunks.append(cf_batch)

        if need_customer_features:
            custf_batch = compute_customer_features(
                c_batch, p_batch, l_batch, cust_batch,
                df_contract_features=cf_batch, feature_cutoff_date=feature_cutoff_date,
                reference_date=reference_date,
            )
            customer_chunks.append(custf_batch)
        del p_batch, l_batch

    if not contract_chunks:
        empty_c = pd.DataFrame(columns=["contract_no", "cust_id"])
        empty_cf = compute_contract_features(empty_c, pd.DataFrame(), pd.DataFrame(), reference_date)
        empty_custf = (
            compute_customer_features(empty_c, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(columns=["cust_id"]))
            if need_customer_features else None
        )
        return empty_cf, empty_custf

    df_cf = pd.concat(contract_chunks, ignore_index=True)
    df_custf = pd.concat(customer_chunks, ignore_index=True) if need_customer_features else None
    return df_cf, df_custf


def compute_features_chunked(
    engine,
    df_contract: pd.DataFrame,
    df_customer: pd.DataFrame,
    reference_date=None,
    feature_cutoff_date=None,
    batch_size: int = 5000,
    need_customer_features: bool = True,
    pass_customer_to_contract_features: bool = True,
):
    """Wrapper DB nyata dari `compute_features_chunked_from_loader()` — satu
    batch `cust_id` (default 5.000 customer) sekaligus, dilepas (`del`)
    sebelum batch berikutnya dimuat, TANPA PERNAH memuat seluruh
    `payment_history`/`lkp_interaction` ke memori sekaligus.

    ``df_contract``/``df_customer`` TETAP dimuat penuh oleh caller — keduanya
    jauh lebih kecil (1 baris per kontrak/customer, bukan per event
    payment/interaksi) dan BUKAN kontributor dinding RAM (lihat
    performance-report.md §4c: peak RSS training di 100rb customer hanya
    3,3 GB; rasio baris tabel event:kontrak terukur TASK-P4 ~30-60:1).
    """
    def _load_batch(contract_nos):
        # ORDER BY payment_id/lkp_id (PK, sekuensial sesuai urutan generate/
        # insert asli) — BUKAN kosmetik. compute_contract_features() punya
        # tie-break yang bergantung urutan baris (mis. last_result_code =
        # result_code pada action_date TERBARU; kalau ada 2+ baris di
        # action_date yang SAMA, yang "terakhir" menurut posisi baris
        # menang). `SELECT * FROM ... WHERE contract_no = ANY(...)` bisa
        # dilayani lewat index scan idx_lkp_contract_action_date (urutan
        # BEDA dari physical/insertion order yang dipakai SELECT * tanpa
        # WHERE) — tanpa ORDER BY eksplisit ini, hasil tie-break bisa
        # berbeda dari jalur non-chunked, ditemukan lewat parity gate nyata
        # (bukan diasumsikan aman).
        with engine.connect() as conn:
            p_batch = pd.read_sql(
                text("SELECT * FROM payment_history WHERE contract_no = ANY(:cns) ORDER BY payment_id"),
                conn, params={"cns": contract_nos},
            )
            l_batch = pd.read_sql(
                text("SELECT * FROM lkp_interaction WHERE contract_no = ANY(:cns) ORDER BY lkp_id"),
                conn, params={"cns": contract_nos},
            )
        return p_batch, l_batch

    # Cek murah (EXISTS ... LIMIT 1, TIDAK memuat tabel) — lihat docstring
    # compute_features_chunked_from_loader() soal kenapa ini perlu.
    with engine.connect() as conn:
        payment_globally_nonempty = bool(
            conn.execute(text("SELECT EXISTS(SELECT 1 FROM payment_history LIMIT 1)")).scalar()
        )

    return compute_features_chunked_from_loader(
        df_contract, df_customer, _load_batch,
        reference_date=reference_date, feature_cutoff_date=feature_cutoff_date, batch_size=batch_size,
        payment_globally_nonempty=payment_globally_nonempty,
        need_customer_features=need_customer_features,
        pass_customer_to_contract_features=pass_customer_to_contract_features,
    )

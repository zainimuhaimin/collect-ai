"""Customer Behavioral Standing builder.

Apply business rules dari System Rules Bagian 4 ke customer features.
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    GRADE_A_THRESHOLD, GRADE_B_THRESHOLD, GRADE_C_THRESHOLD,
    BROKEN_PTP_BLACKLIST, HISTORICAL_DEFAULT_BLACKLIST,
    PTP_RELIABILITY_BLACKLIST, MIN_PTP_MADE_FOR_BLACKLIST,
)


SEGMENT_DEFAULT_CHANNEL = {
    "Low Risk": "WA",
    "Medium Risk": "Deskcoll",
    "High Risk": "Visit",
}


def _grade_from_score(score: float) -> str:
    if pd.isna(score):
        return "C"
    if score >= GRADE_A_THRESHOLD:
        return "A"
    if score >= GRADE_B_THRESHOLD:
        return "B"
    if score >= GRADE_C_THRESHOLD:
        return "C"
    return "D"


def build_cbs(
    df_customer_features: pd.DataFrame,
    df_restructure_stats: pd.DataFrame | None = None,
    reference_date=None,
) -> pd.DataFrame:
    """Apply CBS business rules.

    Input: output dari compute_customer_features().
    ``df_restructure_stats`` (opsional, kolom: cust_id, restructure_count,
    last_restructure_date): dari _compute_restructure_stats() di update_cbs().
    DIHITUNG ULANG dari sumber kebenaran (contract_snapshot.closed_via_restructure
    + restructuring_recommendation_output.response_date) setiap kali CBS
    rebuild — bukan counter yang di-increment manual, supaya tidak ada risiko
    double-count/idempotency kalau job dijalankan berkali-kali. Default 0/NULL
    kalau tidak disediakan (supaya build_cbs() tetap testable tanpa DB).
    ``reference_date`` (opsional): dipakai untuk ``update_timestamp`` alih-alih
    jam dinding, supaya simulasi hari-per-hari (TASK-S2) tidak membocorkan
    tanggal nyata ke kolom yang seharusnya mengikuti tanggal simulasi
    (TASK-S3). Default ``datetime.now()`` kalau tidak diberikan (perilaku lama,
    dipakai call-site yang tidak simulasi tanggal, mis. `train_*.py`).
    Output: DataFrame siap insert ke customer_behavioral_standing.
    """
    df = df_customer_features.copy()

    # ── BEHAVIORAL_GRADE ─────────────────────────────────────────
    df["behavioral_grade"] = df["composite_behavioral_score"].apply(_grade_from_score)

    # 1. Override Grade ke C jika self_cure_rate rendah
    if "self_cure_rate" in df.columns:
        low_cure = (df["self_cure_rate"] < 0.20) & (df["behavioral_grade"].isin(["A", "B"]))
        df.loc[low_cure, "behavioral_grade"] = "C"

    # Override paksa ke D
    force_d = (
        (df["broken_ptp_count"] >= BROKEN_PTP_BLACKLIST)
        | (df["historical_default_count"] >= HISTORICAL_DEFAULT_BLACKLIST)
        | (
            (df["ptp_reliability_index"] < PTP_RELIABILITY_BLACKLIST)
            & (df["sum_ptp_made"] >= MIN_PTP_MADE_FOR_BLACKLIST)
        )
    )
    df.loc[force_d, "behavioral_grade"] = "D"

    # ── B_LIST_STATUS ────────────────────────────────────────────
    # B-List juga mencakup jika customer sering mengingkari PTP berturut-turut
    # (asumsi broken_ptp_count >= 3) atau rpc_rate sangat rendah
    is_blacklist = (
        (df["behavioral_grade"] == "D")
        | (df["broken_ptp_count"] >= 3)  # Updated rule from TASK-36
        | (df["historical_default_count"] >= HISTORICAL_DEFAULT_BLACKLIST)
        | (
            (df["ptp_reliability_index"] < PTP_RELIABILITY_BLACKLIST)
            & (df["sum_ptp_made"] >= MIN_PTP_MADE_FOR_BLACKLIST)
        )
    )
    if "rpc_rate" in df.columns:
        from config.settings import RPC_RATE_LOW_THRESHOLD
        is_blacklist = is_blacklist | (df["rpc_rate"] < RPC_RATE_LOW_THRESHOLD)
        
    df["b_list_status"] = np.where(is_blacklist, "Y", "N")

    # ── RECOVERY_EFFORT_LEVEL ────────────────────────────────────
    def _effort(row):
        if row["behavioral_grade"] == "D" or row["b_list_status"] == "Y" \
           or row["active_contract_count"] >= 3:
            return "High"
        if row["behavioral_grade"] == "A":
            return "Low"
        return "Mid"

    df["recovery_effort_level"] = df.apply(_effort, axis=1)

    # ── COLLECTION_SENSITIVITY ───────────────────────────────────
    df["collection_sensitivity"] = df["channel_effectiveness"]
    fallback = df["cust_segment"].map(SEGMENT_DEFAULT_CHANNEL).fillna("Deskcoll")
    df["collection_sensitivity"] = df["collection_sensitivity"].fillna(fallback)

    # ── PTP_RELIABILITY_INDEX: NULL jika belum pernah PTP ────────
    # (sudah NaN dari customer features jika sum_ptp_made = 0)

    df["update_timestamp"] = pd.Timestamp(reference_date) if reference_date is not None else datetime.now()

    # ── RESTRUCTURE_COUNT / LAST_RESTRUCTURE_DATE (derived) ──────
    if df_restructure_stats is not None and not df_restructure_stats.empty:
        stats = df_restructure_stats.copy()
        stats.columns = [c.lower() for c in stats.columns]
        df = df.merge(stats[["cust_id", "restructure_count", "last_restructure_date"]], on="cust_id", how="left")
    if "restructure_count" not in df.columns:
        df["restructure_count"] = 0
    if "last_restructure_date" not in df.columns:
        df["last_restructure_date"] = pd.NaT
    df["restructure_count"] = df["restructure_count"].fillna(0).astype(int)

    out_cols = [
        "cust_id", "active_contract_count", "total_active_ots",
        "behavioral_grade", "recovery_effort_level",
        "ptp_reliability_index", "collection_sensitivity",
        "b_list_status", "update_timestamp",
        "restructure_count", "last_restructure_date",
        # historical_default_count/income_debt_ratio SUDAH dihitung benar oleh
        # compute_customer_features() dan ada di df sejak awal fungsi ini —
        # sebelumnya dibuang di sini, sehingga daily_scoring.py selalu memaksa
        # 0.0 untuk keduanya dan cabang NBA "Pickup" tidak pernah bisa terpicu.
        "historical_default_count", "income_debt_ratio",
    ]
    return df[out_cols].copy()


def _compute_restructure_stats(engine) -> pd.DataFrame:
    """Derived dari sumber kebenaran (bukan counter manual): restructure_count
    = jumlah kontrak yang sudah closed_via_restructure per cust_id;
    last_restructure_date = response_date ACCEPTED terbaru per cust_id.
    Return DataFrame kosong kalau tabelnya belum ada (mis. schema lama)."""
    try:
        counts = pd.read_sql(
            "SELECT cust_id, COUNT(*) AS restructure_count "
            "FROM contract_snapshot WHERE closed_via_restructure = TRUE "
            "GROUP BY cust_id",
            engine,
        )
        dates = pd.read_sql(
            "SELECT cust_id, MAX(response_date) AS last_restructure_date "
            "FROM restructuring_recommendation_output "
            "WHERE offer_status = 'ACCEPTED' AND response_date IS NOT NULL "
            "GROUP BY cust_id",
            engine,
        )
    except Exception:
        return pd.DataFrame()

    counts.columns = [c.lower() for c in counts.columns]
    dates.columns = [c.lower() for c in dates.columns]
    return counts.merge(dates, on="cust_id", how="outer")


def update_cbs(engine, reference_date=None):
    """Load data dari DB, hitung CBS, UPSERT ke customer_behavioral_standing.

    Preserve B_LIST_STATUS='Y' yang sudah ada.
    """
    from sqlalchemy import text
    from .chunked_features import compute_features_chunked
    from config.settings import FEATURE_CHUNK_BATCH_SIZE

    df_contract = pd.read_sql("SELECT * FROM contract_snapshot", engine)
    df_customer = pd.read_sql("SELECT * FROM customer_master", engine)

    # TASK-P5 item 1: dipecah per batch cust_id (src/chunked_features.py)
    # alih-alih memuat SELURUH payment_history/lkp_interaction. pass_customer_
    # to_contract_features=False: SAMA seperti call asli di sini (TANPA
    # df_customer) — beda dari train_*.py yang MEMANG mengirim df_customer.
    cf, custf = compute_features_chunked(
        engine, df_contract, df_customer, reference_date,
        batch_size=FEATURE_CHUNK_BATCH_SIZE, need_customer_features=True,
        pass_customer_to_contract_features=False,
    )
    restructure_stats = _compute_restructure_stats(engine)
    cbs_new = build_cbs(custf, restructure_stats, reference_date=reference_date)

    # Preserve B_LIST=Y
    try:
        existing = pd.read_sql(
            "SELECT cust_id, b_list_status FROM customer_behavioral_standing",
            engine,
        )
        existing_y = set(existing[existing["b_list_status"] == "Y"]["cust_id"])
        cbs_new.loc[cbs_new["cust_id"].isin(existing_y), "b_list_status"] = "Y"
    except Exception:
        pass

    # DELETE + COPY (TASK-P3) — fallback ke to_sql kalau bukan PostgreSQL
    # (lihat src/db_write.py::copy_dataframe)
    from .db_write import copy_dataframe

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM customer_behavioral_standing"))
        copy_dataframe(conn, "customer_behavioral_standing", cbs_new)

    print(f"[CBS] Updated {len(cbs_new):,} customer profiles")
    return cbs_new

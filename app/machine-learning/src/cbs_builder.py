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


def build_cbs(df_customer_features: pd.DataFrame) -> pd.DataFrame:
    """Apply CBS business rules.

    Input: output dari compute_customer_features().
    Output: DataFrame siap insert ke customer_behavioral_standing.
    """
    df = df_customer_features.copy()

    # ── BEHAVIORAL_GRADE ─────────────────────────────────────────
    df["behavioral_grade"] = df["composite_behavioral_score"].apply(_grade_from_score)

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
    is_blacklist = (
        (df["behavioral_grade"] == "D")
        | (df["broken_ptp_count"] >= BROKEN_PTP_BLACKLIST)
        | (df["historical_default_count"] >= HISTORICAL_DEFAULT_BLACKLIST)
        | (
            (df["ptp_reliability_index"] < PTP_RELIABILITY_BLACKLIST)
            & (df["sum_ptp_made"] >= MIN_PTP_MADE_FOR_BLACKLIST)
        )
    )
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

    df["update_timestamp"] = datetime.now()

    out_cols = [
        "cust_id", "active_contract_count", "total_active_ots",
        "behavioral_grade", "recovery_effort_level",
        "ptp_reliability_index", "collection_sensitivity",
        "b_list_status", "update_timestamp",
    ]
    return df[out_cols].copy()


def update_cbs(engine, reference_date=None):
    """Load data dari DB, hitung CBS, UPSERT ke customer_behavioral_standing.

    Preserve B_LIST_STATUS='Y' yang sudah ada.
    """
    from sqlalchemy import text
    from .feature_engineering import compute_contract_features, compute_customer_features

    df_contract = pd.read_sql("SELECT * FROM contract_snapshot", engine)
    df_payment = pd.read_sql("SELECT * FROM payment_history", engine)
    df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", engine)
    df_customer = pd.read_sql("SELECT * FROM customer_master", engine)

    cf = compute_contract_features(df_contract, df_payment, df_lkp, reference_date)
    custf = compute_customer_features(df_contract, df_payment, df_lkp, df_customer, cf)
    cbs_new = build_cbs(custf)

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

    # UPSERT row-by-row (kompatibel dengan PostgreSQL & SQLite)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM customer_behavioral_standing"))
        cbs_new.to_sql(
            "customer_behavioral_standing", conn,
            if_exists="append", index=False,
        )

    print(f"[CBS] Updated {len(cbs_new):,} customer profiles")
    return cbs_new

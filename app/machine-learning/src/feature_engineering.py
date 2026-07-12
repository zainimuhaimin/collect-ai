"""Feature engineering untuk CollectAI ML.

Tiga fungsi utama:
- compute_contract_features: agregat per CONTRACT_NO (13 fitur)
- compute_customer_features: agregat per CUST_ID lintas kontrak
- enrich_with_cbs: gabungkan contract features + CBS untuk scoring
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    PTP_DAYS_WINDOW,
    DELAY_TREND_WINDOW_MONTHS,
    INCOME_PROXY,
    CYCLE_MAP,
    RESULT_CODE_MAP,
    BEHAVIORAL_GRADE_MAP,
    WEIGHT_PAYMENT_RATE,
    WEIGHT_PTP_RELIABILITY,
    WEIGHT_INTERACTION,
    WEIGHT_DELAY_SCORE,
)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    return df


def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _safe_div(num, den):
    den = np.where(den == 0, np.nan, den)
    return num / den


def _pick_col(df: pd.DataFrame, *candidates: str, default=None):
    for col in candidates:
        if col in df.columns:
            return df[col]
    if default is None:
        return pd.Series([np.nan] * len(df), index=df.index)
    return pd.Series([default] * len(df), index=df.index)


# ────────────────────────────────────────────────────────────────────
# Contract-level features (System Rules 2.1)
# ────────────────────────────────────────────────────────────────────

def compute_contract_features(
    df_contract: pd.DataFrame,
    df_payment: pd.DataFrame,
    df_lkp: pd.DataFrame,
    reference_date=None,
) -> pd.DataFrame:
    """Hitung 13 fitur per CONTRACT_NO.

    Output kolom: contract_no, cust_id, dpd_current, cycle_encoded, total_ots,
    payment_rate, partial_rate, avg_delay_days, days_since_last_pay,
    total_ptp_made, total_ptp_kept, ptp_fulfillment_rate,
    avg_interaction_score, last_result_code_encoded,
    treatment_count, rejection_count, payment_count.
    """
    if reference_date is None:
        reference_date = pd.Timestamp.today().normalize()
    else:
        reference_date = pd.Timestamp(reference_date).normalize()

    c = _lower_cols(df_contract)
    p = _lower_cols(df_payment) if df_payment is not None else pd.DataFrame()
    l = _lower_cols(df_lkp) if df_lkp is not None else pd.DataFrame()

    # Base: kontrak
    cycle_src = _pick_col(c, "cycle", "cycle_akhir")
    dpd_src = _pick_col(c, "dpd_current")
    prnc_src = _pick_col(c, "prnc_ots")
    intr_src = _pick_col(c, "intr_ots")
    out = pd.DataFrame({
        "contract_no": c["contract_no"],
        "cust_id": c["cust_id"],
        "dpd_current": dpd_src.fillna(0).astype(int),
        "cycle_encoded": cycle_src.map(CYCLE_MAP).fillna(0).astype(int),
        "total_ots": (prnc_src.fillna(0) + intr_src.fillna(0)).astype(float),
    })

    # ── Payment aggregates ────────────────────────────────────────
    if not p.empty and "contract_no" in p.columns:
        p["actual_pay_date"] = _to_dt(p.get("actual_pay_date"))
        p["pay_status"] = p["pay_status"].astype(str)

        payment_id_col = "payment_id" if "payment_id" in p.columns else "contract_no"
        pay_agg = (
            p.groupby("contract_no").agg(
                payment_count=(payment_id_col, "count"),
                full_count=("pay_status", lambda s: (s == "Full").sum()),
                partial_count=("pay_status", lambda s: (s == "Partial").sum()),
                avg_delay_days=("delay_days", "mean"),
                last_pay_date=("actual_pay_date", "max"),
            ).reset_index()
        )
        pay_agg["payment_rate"] = _safe_div(pay_agg["full_count"], pay_agg["payment_count"])
        pay_agg["partial_rate"] = _safe_div(pay_agg["partial_count"], pay_agg["payment_count"])
        pay_agg["days_since_last_pay"] = (
            (reference_date - pay_agg["last_pay_date"]).dt.days
        )
        pay_agg = pay_agg[[
            "contract_no", "payment_count", "payment_rate", "partial_rate",
            "avg_delay_days", "days_since_last_pay",
        ]]
        out = out.merge(pay_agg, on="contract_no", how="left")
    else:
        for col in ["payment_count", "payment_rate", "partial_rate",
                    "avg_delay_days", "days_since_last_pay"]:
            out[col] = np.nan
        out["payment_count"] = out["payment_count"].fillna(0).astype(int)

    out["payment_count"] = out["payment_count"].fillna(0).astype(int)
    out["payment_rate"] = out["payment_rate"].fillna(0.0)
    out["partial_rate"] = out["partial_rate"].fillna(0.0)

    # ── LKP aggregates ────────────────────────────────────────────
    if not l.empty and "contract_no" in l.columns:
        l["action_date"] = _to_dt(l.get("action_date"))
        l["promise_date"] = _to_dt(l.get("promise_date"))
        l["result_code"] = l["result_code"].astype(str)

        lkp_id_col = "lkp_id" if "lkp_id" in l.columns else "contract_no"

        lkp_agg = (
            l.groupby("contract_no").agg(
                treatment_count=(lkp_id_col, "count"),
                avg_interaction_score=("interaction_score", "mean"),
                rejection_count=("result_code", lambda s: s.isin(
                    ["Menolak", "Tidak Bisa Dihubungi", "Tidak Bisa"]
                ).sum()),
                total_ptp_made=("result_code", lambda s: (s == "PTP").sum()),
            ).reset_index()
        )

        # last_result_code: result code dari action_date terbaru per kontrak
        l_sorted = l.dropna(subset=["action_date"]).sort_values("action_date")
        last_res = (
            l_sorted.groupby("contract_no")["result_code"].last().reset_index()
            .rename(columns={"result_code": "last_result_code"})
        )
        lkp_agg = lkp_agg.merge(last_res, on="contract_no", how="left")

        # PTP kept: untuk setiap LKP dengan PTP, cek apakah ada payment
        # (Full atau Partial) dalam PTP_DAYS_WINDOW hari setelah promise_date
        ptp_rows = l[l["result_code"] == "PTP"][
            ["contract_no", "promise_date"]
        ].dropna(subset=["promise_date"]).copy()

        if not ptp_rows.empty and not p.empty:
            valid_pay = p[p["pay_status"].isin(["Full", "Partial"])][
                ["contract_no", "actual_pay_date"]
            ].dropna(subset=["actual_pay_date"])
            merged = ptp_rows.merge(valid_pay, on="contract_no", how="left")
            merged["kept"] = (
                (merged["actual_pay_date"] >= merged["promise_date"]) &
                (merged["actual_pay_date"] <=
                 merged["promise_date"] + pd.Timedelta(days=PTP_DAYS_WINDOW))
            )
            kept_per_ptp = merged.groupby(
                ["contract_no", "promise_date"]
            )["kept"].any().reset_index()
            kept_agg = (
                kept_per_ptp.groupby("contract_no")["kept"].sum().reset_index()
                .rename(columns={"kept": "total_ptp_kept"})
            )
            kept_agg["total_ptp_kept"] = kept_agg["total_ptp_kept"].astype(int)
            lkp_agg = lkp_agg.merge(kept_agg, on="contract_no", how="left")
        else:
            lkp_agg["total_ptp_kept"] = 0

        lkp_agg["total_ptp_kept"] = lkp_agg["total_ptp_kept"].fillna(0).astype(int)
        lkp_agg["ptp_fulfillment_rate"] = np.where(
            lkp_agg["total_ptp_made"] > 0,
            lkp_agg["total_ptp_kept"] / lkp_agg["total_ptp_made"].replace(0, np.nan),
            np.nan,
        )

        out = out.merge(lkp_agg, on="contract_no", how="left")
    else:
        out["treatment_count"] = 0
        out["avg_interaction_score"] = np.nan
        out["rejection_count"] = 0
        out["total_ptp_made"] = 0
        out["total_ptp_kept"] = 0
        out["ptp_fulfillment_rate"] = np.nan
        out["last_result_code"] = np.nan

    # Fill defaults
    out["treatment_count"] = out["treatment_count"].fillna(0).astype(int)
    out["rejection_count"] = out["rejection_count"].fillna(0).astype(int)
    out["total_ptp_made"] = out["total_ptp_made"].fillna(0).astype(int)
    out["total_ptp_kept"] = out["total_ptp_kept"].fillna(0).astype(int)

    # Encode last result code (NULL → -1 sentinel, fitur model akan handle)
    out["last_result_code_encoded"] = (
        out["last_result_code"].map(RESULT_CODE_MAP).fillna(-1).astype(int)
    )

    return out


# ────────────────────────────────────────────────────────────────────
# Customer-level features (System Rules 2.2)
# ────────────────────────────────────────────────────────────────────

def _compute_delay_trend(payment_df: pd.DataFrame, window_months: int) -> float:
    """Slope linear dari avg(delay_days) per bulan dalam window terakhir.

    Return 0.0 jika data tidak cukup (< 2 bulan).
    """
    if payment_df.empty or "actual_pay_date" not in payment_df.columns:
        return 0.0
    df = payment_df.dropna(subset=["actual_pay_date", "delay_days"]).copy()
    if df.empty:
        return 0.0
    df["actual_pay_date"] = _to_dt(df["actual_pay_date"])
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=window_months)
    df = df[df["actual_pay_date"] >= cutoff]
    if df.empty:
        return 0.0
    df["ym"] = df["actual_pay_date"].dt.to_period("M")
    monthly = df.groupby("ym")["delay_days"].mean().reset_index()
    if len(monthly) < 2:
        return 0.0
    x = np.arange(len(monthly), dtype=float)
    y = monthly["delay_days"].astype(float).values
    slope = np.polyfit(x, y, 1)[0]
    return float(slope)


def compute_customer_features(
    df_contract: pd.DataFrame,
    df_payment: pd.DataFrame,
    df_lkp: pd.DataFrame,
    df_customer: pd.DataFrame,
    df_contract_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Agregat per CUST_ID lintas semua kontrak.

    Jika df_contract_features sudah dihitung, di-reuse untuk efisiensi.
    """
    c = _lower_cols(df_contract)
    p = _lower_cols(df_payment) if df_payment is not None else pd.DataFrame()
    l = _lower_cols(df_lkp) if df_lkp is not None else pd.DataFrame()
    cust = _lower_cols(df_customer)

    if df_contract_features is None:
        cf = compute_contract_features(c, p, l)
    else:
        cf = df_contract_features.copy()

    status_col = _pick_col(c, "status", default="aktif").astype(str).str.lower()
    active_contracts = set(c.loc[status_col == "aktif", "contract_no"])
    if not active_contracts:
        active_contracts = set(c["contract_no"])
    cf["is_active"] = cf["contract_no"].isin(active_contracts).astype(int)
    cf["active_ots"] = np.where(cf["is_active"] == 1, cf["total_ots"], 0.0)

    agg = cf.groupby("cust_id").agg(
        active_contract_count=("is_active", "sum"),
        total_active_ots=("active_ots", "sum"),
        sum_ptp_made=("total_ptp_made", "sum"),
        sum_ptp_kept=("total_ptp_kept", "sum"),
        avg_payment_rate=("payment_rate", "mean"),
        avg_delay_days_cust=("avg_delay_days", "mean"),
        avg_interaction_score_cust=("avg_interaction_score", "mean"),
        max_cycle_encoded=("cycle_encoded", "max"),
    ).reset_index()

    agg["ptp_reliability_index"] = np.where(
        agg["sum_ptp_made"] > 0,
        agg["sum_ptp_kept"] / agg["sum_ptp_made"].replace(0, np.nan),
        np.nan,
    )
    agg["broken_ptp_count"] = (agg["sum_ptp_made"] - agg["sum_ptp_kept"]).astype(int)

    # historical_default_count: kontrak yang max cycle >= 3 (C3+)
    # Pendekatan: gunakan cycle saat ini sebagai proxy historis
    hist_default = (
        cf[cf["cycle_encoded"] >= 3].groupby("cust_id")["contract_no"]
        .nunique().reset_index().rename(columns={"contract_no": "historical_default_count"})
    )
    agg = agg.merge(hist_default, on="cust_id", how="left")
    agg["historical_default_count"] = agg["historical_default_count"].fillna(0).astype(int)

    # channel_effectiveness: treatment_type yang paling sering hasilkan Bayar
    if not l.empty:
        bayar_lkp = l[l["result_code"] == "Bayar"].merge(
            cf[["contract_no", "cust_id"]], on="contract_no", how="left"
        )
        if not bayar_lkp.empty:
            ch = (
                bayar_lkp.groupby(["cust_id", "treatment_type"]).size()
                .reset_index(name="n")
            )
            channel_rank = {"WA": 1, "Deskcoll": 2, "Visit": 3, "Somasi": 4, "Pickup": 5}
            ch["rank"] = ch["treatment_type"].map(channel_rank).fillna(99)
            ch_top = ch.sort_values(["cust_id", "n", "rank"], ascending=[True, False, True])
            ch_top = ch_top.groupby("cust_id").first().reset_index()
            ch_top = ch_top[["cust_id", "treatment_type"]].rename(
                columns={"treatment_type": "channel_effectiveness"}
            )
            agg = agg.merge(ch_top, on="cust_id", how="left")
        else:
            agg["channel_effectiveness"] = np.nan
    else:
        agg["channel_effectiveness"] = np.nan

    # delay_trend per customer
    if not p.empty:
        p2 = p.merge(cf[["contract_no", "cust_id"]], on="contract_no", how="left")
        p2 = p2[["cust_id", "actual_pay_date", "delay_days"]].copy()
        trend_rows = []
        for cust_id, grp in p2.groupby("cust_id"):
            trend_rows.append({
                "cust_id": cust_id,
                "delay_trend": _compute_delay_trend(grp, DELAY_TREND_WINDOW_MONTHS),
            })
        trends = pd.DataFrame(trend_rows)
        agg = agg.merge(trends, on="cust_id", how="left")
    else:
        agg["delay_trend"] = 0.0
    agg["delay_trend"] = agg["delay_trend"].fillna(0.0)

    # Income proxy & ratio
    cust_min = cust[["cust_id", "cust_income_level", "cust_segment"]].drop_duplicates("cust_id")
    agg = agg.merge(cust_min, on="cust_id", how="left")
    agg["income_proxy"] = agg["cust_income_level"].map(INCOME_PROXY).fillna(8_000_000)
    agg["income_debt_ratio"] = (agg["total_active_ots"] / agg["income_proxy"]).astype(float)

    # composite_behavioral_score
    payment_rate_w = agg["avg_payment_rate"].fillna(0.0)
    ptp_rel = agg["ptp_reliability_index"].fillna(0.0)
    inter_norm = ((agg["avg_interaction_score_cust"].fillna(1.0) - 1.0) / 4.0).clip(0, 1)
    delay_score = (1.0 - (agg["avg_delay_days_cust"].fillna(0.0) / 90.0)).clip(0, 1)

    agg["composite_behavioral_score"] = (
        payment_rate_w * WEIGHT_PAYMENT_RATE
        + ptp_rel * WEIGHT_PTP_RELIABILITY
        + inter_norm * WEIGHT_INTERACTION
        + delay_score * WEIGHT_DELAY_SCORE
    ).clip(0, 1)

    return agg


# ────────────────────────────────────────────────────────────────────
# Enrichment: gabungkan contract features + CBS untuk scoring
# ────────────────────────────────────────────────────────────────────

def enrich_with_cbs(df_contract_features: pd.DataFrame, df_cbs: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan contract features dengan CBS per CUST_ID.

    df_cbs harus punya kolom: cust_id, ptp_reliability_index, delay_trend,
    historical_default_count, income_debt_ratio, active_contract_count,
    total_active_ots, behavioral_grade, b_list_status.
    """
    cbs = _lower_cols(df_cbs)
    cf = df_contract_features.copy()

    keep = [
        "cust_id",
        "ptp_reliability_index", "delay_trend", "historical_default_count",
        "income_debt_ratio", "active_contract_count", "total_active_ots",
        "behavioral_grade", "b_list_status",
    ]
    cbs_sub = cbs[[k for k in keep if k in cbs.columns]].copy()

    cbs_sub["behavioral_grade_encoded"] = (
        cbs_sub["behavioral_grade"].map(BEHAVIORAL_GRADE_MAP)
        if "behavioral_grade" in cbs_sub.columns else np.nan
    )
    cbs_sub["b_list_flag"] = (
        (cbs_sub["b_list_status"] == "Y").astype(int)
        if "b_list_status" in cbs_sub.columns else 0
    )

    merged = cf.merge(cbs_sub, on="cust_id", how="left")
    return merged.drop_duplicates(subset=["contract_no"]).copy()

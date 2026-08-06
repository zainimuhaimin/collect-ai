"""Business rules untuk segmentasi risiko, NBA, dan prioritas."""
from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SCORE_THRESHOLD_WONT_PAY,
    SCORE_THRESHOLD_CANNOT_PAY,
    SCORE_THRESHOLD_SELF_CURE,
    REJECTION_COUNT_THRESHOLD,
    MAX_DPD_FOR_SELFCURE,
    MIN_PAYMENT_RATE_SELFCURE,
    MAX_INCOME_DEBT_RATIO,
    OTS_TIER_RENDAH,
    OTS_TIER_TINGGI,
    SELF_CURE_PROB_THRESHOLD,
    ROLL_FORWARD_HIGH_RISK,
    RPC_RATE_LOW_THRESHOLD,
    DAYS_TO_MATURITY_SHORT,
)


CHANNEL_RANK = {"WA": 1, "Deskcoll": 2, "Visit": 3, "Somasi": 4, "Pickup": 5}


def apply_risk_segment(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    score = pd.to_numeric(out.get("recovery_score"), errors="coerce").fillna(0.0)
    rej = pd.to_numeric(out.get("rejection_count", 0), errors="coerce").fillna(0)
    last_result = pd.to_numeric(out.get("last_result_code_encoded", -1), errors="coerce").fillna(-1)
    broken_ptp = pd.to_numeric(out.get("broken_ptp_count", 0), errors="coerce").fillna(0)
    idr = pd.to_numeric(out.get("income_debt_ratio", 0), errors="coerce").fillna(0)
    dpd = pd.to_numeric(out.get("dpd_current", 0), errors="coerce").fillna(0)
    pay_rate = pd.to_numeric(out.get("payment_rate", 0), errors="coerce").fillna(0)

    cond_wont = (
        (score < SCORE_THRESHOLD_WONT_PAY)
        & ((rej >= REJECTION_COUNT_THRESHOLD) | (last_result <= 1))
    )
    cond_cannot = (
        (score >= SCORE_THRESHOLD_WONT_PAY)
        & (score < SCORE_THRESHOLD_CANNOT_PAY)
        & ((broken_ptp > 0) | (idr > MAX_INCOME_DEBT_RATIO))
    )
    # cond_self_cure: recovery >= 0.70 AND dpd <= 7 AND payment_rate >= 0.80 AND self_cure_probability >= 0.70
    if "self_cure_probability" in out.columns:
        prob_sc = pd.to_numeric(out["self_cure_probability"], errors="coerce").fillna(0)
    else:
        prob_sc = pd.Series(0.0, index=out.index)
    cond_self = (
        (score >= SCORE_THRESHOLD_SELF_CURE)
        & (dpd <= MAX_DPD_FOR_SELFCURE)
        & (pay_rate >= MIN_PAYMENT_RATE_SELFCURE)
        & (prob_sc >= SELF_CURE_PROB_THRESHOLD)
    )

    out["risk_segment"] = np.select(
        [cond_wont, cond_cannot, cond_self],
        ["Won't Pay", "Cannot Pay", "Self-cure"],
        default="Can Pay",
    )
    return out


def apply_nba(df: pd.DataFrame, df_cbs: pd.DataFrame | None = None) -> pd.DataFrame:
    out = df.copy()

    if df_cbs is not None and len(df_cbs) > 0:
        cbs = df_cbs.copy()
        cbs.columns = [c.lower() for c in cbs.columns]
        if "cust_id" in cbs.columns and "collection_sensitivity" in cbs.columns:
            out = out.merge(
                cbs[["cust_id", "collection_sensitivity"]].drop_duplicates("cust_id"),
                on="cust_id",
                how="left",
                suffixes=("", "_cbs"),
            )
            if "collection_sensitivity_cbs" in out.columns:
                out["collection_sensitivity"] = out["collection_sensitivity"].fillna(
                    out["collection_sensitivity_cbs"]
                )
                out = out.drop(columns=["collection_sensitivity_cbs"])

    seg = out["risk_segment"].astype(str)
    cycle = pd.to_numeric(out.get("cycle_encoded", 0), errors="coerce").fillna(0)
    ots = pd.to_numeric(out.get("total_ots", 0), errors="coerce").fillna(0)
    hist_default = pd.to_numeric(out.get("historical_default_count", 0), errors="coerce").fillna(0)

    out["nba_recommendation"] = "Deskcoll"
    # nba_trigger: label singkat cabang TERAKHIR yang menulis nba_recommendation.
    # apply_nba() menimpa nilainya lewat assignment .loc berurutan (last-write-
    # wins) — tanpa kolom ini, tidak ada cara mengetahui ALASAN rekomendasi
    # tanpa merekonstruksi ulang seluruh urutan 8+ assignment dari luar fungsi
    # ini (dipakai fitur AI Reasoning untuk menilai apakah alasannya masih
    # berlaku di level debitur — lihat ai-reasoning-api-upgrade-tasks.md §1.1).
    out["nba_trigger"] = "base:default_deskcoll"

    out.loc[seg == "Self-cure", ["nba_recommendation", "nba_trigger"]] = ["WA", "base:self_cure"]
    out.loc[(seg == "Can Pay") & (cycle <= 1), ["nba_recommendation", "nba_trigger"]] = ["WA", "base:can_pay_low_cycle"]
    out.loc[(seg == "Can Pay") & (cycle >= 2), ["nba_recommendation", "nba_trigger"]] = ["Deskcoll", "base:can_pay_high_cycle"]
    out.loc[(seg == "Cannot Pay") & (cycle <= 1), ["nba_recommendation", "nba_trigger"]] = ["Deskcoll", "base:cannot_pay_low_cycle"]
    out.loc[(seg == "Cannot Pay") & (cycle >= 2), ["nba_recommendation", "nba_trigger"]] = ["Visit", "base:cannot_pay_high_cycle"]

    out.loc[(seg == "Won't Pay") & (ots < OTS_TIER_RENDAH), ["nba_recommendation", "nba_trigger"]] = ["Visit", "base:wont_pay_low_ots"]
    out.loc[(seg == "Won't Pay") & (ots >= OTS_TIER_RENDAH), ["nba_recommendation", "nba_trigger"]] = ["Somasi", "base:wont_pay_mid_ots"]
    out.loc[
        (seg == "Won't Pay") & (ots >= OTS_TIER_TINGGI) & (hist_default >= 2),
        ["nba_recommendation", "nba_trigger"],
    ] = ["Pickup", "base:wont_pay_high_ots_repeat_default"]

    # CBS sensitivity override: hanya upgrade, tidak boleh downgrade
    if "collection_sensitivity" in out.columns:
        sens = out["collection_sensitivity"].astype(str)
        nba_rank = out["nba_recommendation"].map(CHANNEL_RANK).fillna(0)
        sens_rank = sens.map(CHANNEL_RANK).fillna(0)
        do_override = sens_rank > nba_rank
        out.loc[do_override, "nba_recommendation"] = sens[do_override]
        out.loc[do_override, "nba_trigger"] = "override:collection_sensitivity"

    # Override baru 1: nasabah self-cure tinggi → WA saja
    if "self_cure_probability" in out.columns:
        sc_high = out["self_cure_probability"] >= SELF_CURE_PROB_THRESHOLD
        out.loc[sc_high, "nba_recommendation"] = "WA"
        out.loc[sc_high, "nba_trigger"] = "override:self_cure_high"

    # Override baru 2: RPC rate sangat rendah → Visit untuk verify alamat
    if "rpc_rate" in out.columns:
        rpc_low = out["rpc_rate"] < RPC_RATE_LOW_THRESHOLD

        # apply only if current rank < Visit (which is 3)
        nba_r = out["nba_recommendation"].map(CHANNEL_RANK).fillna(0)
        to_visit = rpc_low & (nba_r < 3)
        out.loc[to_visit, "nba_recommendation"] = "Visit"
        out.loc[to_visit, "nba_trigger"] = "override:rpc_rate_low"

    # Override baru 3: near-maturity + saldo kecil → WA cukup
    if "days_to_maturity" in out.columns and "ambc" in out.columns and "installment_amount" in out.columns:
        near_mat = (out["days_to_maturity"] < DAYS_TO_MATURITY_SHORT) & (out["ambc"] < out["installment_amount"] * 2)
        out.loc[near_mat, "nba_recommendation"] = "WA"
        out.loc[near_mat, "nba_trigger"] = "override:near_maturity_small_balance"

    return out


def apply_priority(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _ots_tier(v):
        if v < OTS_TIER_RENDAH:
            return "low"
        if v < OTS_TIER_TINGGI:
            return "mid"
        return "high"

    matrix = {
        ("Won't Pay", "low"): "High",
        ("Won't Pay", "mid"): "Critical",
        ("Won't Pay", "high"): "Critical",
        ("Cannot Pay", "low"): "Medium",
        ("Cannot Pay", "mid"): "High",
        ("Cannot Pay", "high"): "Critical",
        ("Can Pay", "low"): "Low",
        ("Can Pay", "mid"): "Medium",
        ("Can Pay", "high"): "High",
        ("Self-cure", "low"): "Low",
        ("Self-cure", "mid"): "Low",
        ("Self-cure", "high"): "Medium",
    }

    ots = pd.to_numeric(out.get("total_ots", 0), errors="coerce").fillna(0)
    tier = ots.apply(_ots_tier)
    base_priorities = [
        matrix.get((seg, t), "Medium")
        for seg, t in zip(out["risk_segment"].astype(str), tier)
    ]
    out["priority_level"] = base_priorities

    if "roll_forward_risk" in out.columns:
        rfr_high = out["roll_forward_risk"] >= ROLL_FORWARD_HIGH_RISK
        escalation_map = {
            "Low": "Medium",
            "Medium": "High",
            "High": "Critical",
            "Critical": "Critical",
        }
        # escalate priority if high roll forward risk
        out.loc[rfr_high, "priority_level"] = out.loc[rfr_high, "priority_level"].map(escalation_map).fillna(out["priority_level"])

    return out

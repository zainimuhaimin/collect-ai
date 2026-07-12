"""Scoring engine untuk CollectAI."""
from __future__ import annotations

import os
import joblib
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import FEATURE_COLS


CONF_KEY_FEATURES = [
    "avg_delay_days",
    "payment_rate",
    "ptp_fulfillment_rate",
    "avg_interaction_score",
    "ptp_reliability_index",
]


def _prepare_features(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in feature_cols:
        if col not in out.columns:
            out[col] = 0.0
    return out[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)


def score_contracts(df_features_enriched: pd.DataFrame, model_path: str) -> pd.DataFrame:
    artifact = joblib.load(model_path)
    if isinstance(artifact, dict):
        model = artifact.get("model")
        feature_cols = artifact.get("feature_cols", FEATURE_COLS)
    else:
        model = artifact
        feature_cols = FEATURE_COLS

    if model is None:
        raise ValueError("Model artifact tidak valid: kunci 'model' tidak ditemukan")

    X = _prepare_features(df_features_enriched, feature_cols)
    pred = model.predict_proba(X)[:, 1]

    out = df_features_enriched.copy()
    out["recovery_score"] = np.clip(np.round(pred, 4), 0.0, 1.0)
    if out["recovery_score"].isna().any():
        raise ValueError("Terdapat NULL pada recovery_score")
    return out


def compute_confidence_level(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # A - Data completeness
    for c in CONF_KEY_FEATURES:
        if c not in out.columns:
            out[c] = np.nan
    out["conf_data_completeness"] = out[CONF_KEY_FEATURES].notna().sum(axis=1) / len(CONF_KEY_FEATURES)

    # B - History depth
    pay_norm = (pd.to_numeric(out.get("payment_count", 0), errors="coerce").fillna(0).clip(0, 10) / 10.0)
    trt_norm = (pd.to_numeric(out.get("treatment_count", 0), errors="coerce").fillna(0).clip(0, 5) / 5.0)
    out["conf_history_depth"] = (pay_norm * 0.6 + trt_norm * 0.4).clip(0, 1)

    # C - Model certainty
    score = pd.to_numeric(out.get("recovery_score"), errors="coerce").fillna(0.5)
    out["conf_model_certainty"] = (2.0 * np.abs(score - 0.5)).clip(0, 1)

    out["confidence_level"] = (
        out["conf_data_completeness"] * 0.40
        + out["conf_history_depth"] * 0.35
        + out["conf_model_certainty"] * 0.25
    ).clip(0, 1)

    out["confidence_category"] = np.select(
        [out["confidence_level"] >= 0.75, out["confidence_level"] >= 0.50],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )
    return out


def run_quality_check(df_output: pd.DataFrame):
    df = df_output.copy()
    checks = []
    is_small_batch = len(df) < 200

    # Range checks
    range_ok = (
        df["recovery_score"].between(0, 1, inclusive="both").all()
        and df["confidence_level"].between(0, 1, inclusive="both").all()
    )
    checks.append(("range_score_confidence", bool(range_ok), "hard"))

    # Null checks
    required = [
        "contract_no", "cust_id", "recovery_score", "confidence_level",
        "risk_segment", "nba_recommendation", "priority_level",
    ]
    missing_required = [c for c in required if c not in df.columns]
    null_ok = (not missing_required) and (not df[required].isna().any().any())
    checks.append(("null_required", bool(null_ok), "hard"))

    # Duplicate check
    dup_ok = not df["contract_no"].duplicated().any()
    checks.append(("duplicate_contract_no", bool(dup_ok), "hard"))

    # Distribution checks
    total = max(len(df), 1)
    wont_pct = float((df["risk_segment"] == "Won't Pay").sum() / total)
    self_pct = float((df["risk_segment"] == "Self-cure").sum() / total)
    critical_pct = float((df["priority_level"] == "Critical").sum() / total)

    dist_severity = "soft" if is_small_batch else "hard"
    checks.append(("wont_pay_pct<=30%", wont_pct <= 0.30, dist_severity))
    checks.append(("self_cure_pct>=5%", self_pct >= 0.05, dist_severity))
    checks.append(("critical_pct<=20%", critical_pct <= 0.20, dist_severity))

    # Consistency soft check
    if "cbs_exists" in df.columns:
        consistency_ok = bool(df["cbs_exists"].fillna(False).all())
    else:
        consistency_ok = True
    checks.append(("cust_exists_in_cbs", consistency_ok, "soft"))

    print("\n[QC] Summary")
    hard_failed = []
    for name, passed, severity in checks:
        flag = "PASS" if passed else "FAIL"
        print(f"  - {name:<24} [{severity}] {flag}")
        if (not passed) and severity == "hard":
            hard_failed.append(name)
        if (not passed) and severity == "soft":
            print("    warning: cek konsistensi gagal")

    if hard_failed:
        raise ValueError("QC hard-fail: " + ", ".join(hard_failed))

    return {
        "status": "pass",
        "wont_pay_pct": round(wont_pct, 4),
        "self_cure_pct": round(self_pct, 4),
        "critical_pct": round(critical_pct, 4),
    }

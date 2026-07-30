"""Scoring engine untuk CollectAI."""
from __future__ import annotations

import os
import joblib
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    FEATURE_COLS,
    QC_WONT_PAY_MAX_PCT,
    QC_SELF_CURE_MIN_PCT,
    QC_CRITICAL_MAX_PCT,
    STRICT_QC,
)


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


def score_contracts(df_features_enriched: pd.DataFrame, champion_path: str = None) -> pd.DataFrame:
    from config.settings import (
        CHAMPION_MODEL_PATH, SELF_CURE_MODEL_PATH,
        ROLL_FORWARD_MODEL_PATH, PTP_SUCCESS_MODEL_PATH
    )
    if champion_path is None:
        champion_path = CHAMPION_MODEL_PATH

    out = df_features_enriched.copy()

    def _score_model(path, col_name, invert=False):
        if not os.path.exists(path):
            out[col_name] = np.nan
            return
        artifact = joblib.load(path)
        if isinstance(artifact, dict):
            model = artifact.get("model")
            feature_cols = artifact.get("feature_cols", FEATURE_COLS)
        else:
            model = artifact
            feature_cols = FEATURE_COLS

        if model is None:
            out[col_name] = np.nan
            return

        X = _prepare_features(df_features_enriched, feature_cols)
        pred = model.predict_proba(X)[:, 1]
        if invert:
            pred = 1.0 - pred
        out[col_name] = np.clip(np.round(pred, 4), 0.0, 1.0)

    # 1. Recovery Score (Champion)
    _score_model(champion_path, "recovery_score")
    if out["recovery_score"].isna().any():
        raise ValueError("Terdapat NULL pada recovery_score")

    # 2. Self Cure Score
    # Path sub-model TIDAK di-resolve lewat registry (berbeda dari recovery) —
    # promote_challenger()/rollback_to_previous() untuk model_type ini selalu
    # menulis ke path tetap SELF_CURE_MODEL_PATH ini juga, jadi hasilnya sama;
    # dipertahankan langsung dari settings agar tetap mudah di-mock di test
    # (lihat tests/test_scoring.py::test_missing_submodel_graceful).
    _score_model(SELF_CURE_MODEL_PATH, "self_cure_probability")

    # 3. Roll Forward Score
    # Model roll_forward ditraining untuk memprediksi P(actual_paid=1) pada
    # populasi cycle>=1 (lihat train_roll_forward.py). ROLL_FORWARD_RISK harus
    # merepresentasikan risiko MEMBURUK (tidak bayar), jadi hasilnya di-invert:
    # P(tidak bayar) = 1 - P(bayar).
    _score_model(ROLL_FORWARD_MODEL_PATH, "roll_forward_risk", invert=True)

    # 4. PTP Success Score
    _score_model(PTP_SUCCESS_MODEL_PATH, "ptp_success_probability")

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


def run_quality_check(df_output: pd.DataFrame, strict: bool | None = None):
    """
    ``strict`` (default None = ambil dari config.settings.STRICT_QC, yang
    sekarang default False): kalau False, cek DISTRIBUSI (wont_pay/
    self_cure/critical %) diturunkan jadi soft-warning, bukan hard-fail.
    Batas QC_*_PCT itu asumsi komposisi portfolio, bukan invariant kebenaran
    pipeline — kalau mix portfolio bergeser, menggagalkan seluruh run berarti
    nol skor tersimpan, jauh lebih merusak daripada skor dengan komposisi tak
    terduga. Pelanggaran tetap tercetak sebagai warning beserta nilainya.

    Cek integritas data (range, null, duplikat) TETAP hard di kedua mode —
    itu bug nyata di kode/data, bukan soal kalibrasi bisnis.
    """
    if strict is None:
        strict = STRICT_QC
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

    dist_severity = "soft" if (is_small_batch or not strict) else "hard"
    observed = {}
    for name, passed, value in (
        (f"wont_pay_pct<={QC_WONT_PAY_MAX_PCT:.0%}", wont_pct <= QC_WONT_PAY_MAX_PCT, wont_pct),
        (f"self_cure_pct>={QC_SELF_CURE_MIN_PCT:.0%}", self_pct >= QC_SELF_CURE_MIN_PCT, self_pct),
        (f"critical_pct<={QC_CRITICAL_MAX_PCT:.0%}", critical_pct <= QC_CRITICAL_MAX_PCT, critical_pct),
    ):
        checks.append((name, passed, dist_severity))
        observed[name] = value

    # Consistency soft check
    if "cbs_exists" in df.columns:
        consistency_ok = bool(df["cbs_exists"].fillna(False).all())
    else:
        consistency_ok = True
    checks.append(("cust_exists_in_cbs", consistency_ok, "soft"))

    # Range check untuk score baru
    for col in ['self_cure_probability', 'roll_forward_risk', 'ptp_success_probability']:
        if col in df.columns and df[col].notna().any():
            range_ok_sub = bool(df[col].dropna().between(0, 1).all())
            checks.append((f"range_{col}", range_ok_sub, "hard"))

    # Konsistensi check: Self-cure harus punya self_cure_probability tinggi
    selfcure_rows = df[df['risk_segment'] == 'Self-cure']
    if len(selfcure_rows) > 0 and 'self_cure_probability' in df.columns:
        avg_sc_prob = selfcure_rows['self_cure_probability'].mean()
        checks.append(("self_cure_segment_prob>=0.5", bool(avg_sc_prob >= 0.50), "soft"))

    # Roll forward: Won't Pay harus punya roll_forward_risk rata-rata lebih tinggi dari Self-cure
    if 'roll_forward_risk' in df.columns and len(selfcure_rows) > 0:
        wont_pay_rows = df[df['risk_segment'] == "Won't Pay"]
        if len(wont_pay_rows) > 0:
            wont_pay_rfr = wont_pay_rows['roll_forward_risk'].mean()
            selfcure_rfr = selfcure_rows['roll_forward_risk'].mean()
            checks.append(("wont_pay_rfr>self_cure_rfr", bool(wont_pay_rfr >= selfcure_rfr), "soft"))

    print(f"\n[QC] Summary (strict_qc={strict})")
    hard_failed = []
    for name, passed, severity in checks:
        flag = "PASS" if passed else "FAIL"
        print(f"  - {name:<24} [{severity}] {flag}")
        if (not passed) and severity == "hard":
            hard_failed.append(name)
        if (not passed) and severity == "soft":
            if name in observed:
                print(f"    warning: distribusi di luar batas — nilai aktual {observed[name]:.1%}")
            else:
                print("    warning: cek konsistensi gagal")

    if hard_failed:
        raise ValueError("QC hard-fail: " + ", ".join(hard_failed))

    return {
        "status": "pass",
        "wont_pay_pct": round(wont_pct, 4),
        "self_cure_pct": round(self_pct, 4),
        "critical_pct": round(critical_pct, 4),
    }

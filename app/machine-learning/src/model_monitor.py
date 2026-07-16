"""Model monitoring utilities for CollectAI MLOps."""
from __future__ import annotations

import os
import sys
from datetime import date
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import N_CRITICAL_DRIFT_TRIGGER, N_WARNING_DRIFT_TRIGGER  # noqa: E402


def compute_model_performance(df_labeled: pd.DataFrame, window_days: int = 30) -> dict:
    """Hitung AUC, log_loss, dan calibration gap pada window terbaru."""
    if df_labeled is None or df_labeled.empty:
        return {"status": "insufficient_data", "message": "No labeled records available"}

    df = df_labeled.copy()
    df.columns = [c.lower() for c in df.columns]
    if "scoring_date" not in df.columns:
        return {"status": "insufficient_data", "message": "Missing scoring_date column"}

    df["scoring_date"] = pd.to_datetime(df["scoring_date"], errors="coerce")
    df = df.dropna(subset=["scoring_date", "actual_paid", "recovery_score"])
    if df.empty:
        return {"status": "insufficient_data", "message": "No valid labeled rows"}

    recent_cutoff = df["scoring_date"].max() - pd.Timedelta(days=window_days)
    recent = df[df["scoring_date"] >= recent_cutoff].copy()

    if len(recent) < 100 or recent["actual_paid"].nunique() < 2:
        return {
            "status": "insufficient_data",
            "message": f"Not enough labeled data for evaluation: {len(recent)} rows",
        }

    y_true = pd.to_numeric(recent["actual_paid"], errors="coerce").fillna(0).astype(int)
    y_score = pd.to_numeric(recent["recovery_score"], errors="coerce").fillna(0.0)
    y_score = y_score.clip(0, 1)

    auc = float(roc_auc_score(y_true, y_score))
    ll = float(log_loss(y_true, y_score.clip(1e-6, 1 - 1e-6)))
    avg_score = float(y_score.mean())
    actual_rate = float(y_true.mean())
    calibration_gap = abs(avg_score - actual_rate)

    segment_perf = {}
    if "risk_segment" in recent.columns:
        for seg, grp in recent.groupby("risk_segment"):
            if len(grp) < 10 or grp["actual_paid"].nunique() < 2:
                continue
            grp_y = pd.to_numeric(grp["actual_paid"], errors="coerce").fillna(0).astype(int)
            grp_s = pd.to_numeric(grp["recovery_score"], errors="coerce").fillna(0.0).clip(0, 1)
            segment_perf[str(seg)] = {
                "auc": float(roc_auc_score(grp_y, grp_s)),
                "n": int(len(grp)),
                "actual_rate": float(grp_y.mean()),
                "avg_score": float(grp_s.mean()),
            }

    return {
        "status": "ok",
        "n_samples": int(len(recent)),
        "auc": round(auc, 4),
        "log_loss": round(ll, 4),
        "avg_score": round(avg_score, 4),
        "actual_rate": round(actual_rate, 4),
        "calibration_gap": round(calibration_gap, 4),
        "segment_breakdown": segment_perf,
    }


def compute_psi(reference_series, current_series, n_bins: int = 10):
    """Population Stability Index."""
    ref = pd.Series(reference_series).dropna().astype(float)
    cur = pd.Series(current_series).dropna().astype(float)

    if len(ref) == 0 or len(cur) == 0:
        return None

    if np.isclose(ref.nunique(), 1) and np.isclose(cur.nunique(), 1) and np.isclose(ref.iloc[0], cur.iloc[0]):
        return 0.0

    _, bin_edges = np.histogram(ref, bins=n_bins)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    ref_counts, _ = np.histogram(ref, bins=bin_edges)
    cur_counts, _ = np.histogram(cur, bins=bin_edges)

    ref_pct = np.where(ref_counts == 0, 0.0001, ref_counts / len(ref))
    cur_pct = np.where(cur_counts == 0, 0.0001, cur_counts / len(cur))

    psi_value = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return round(float(psi_value), 4)


def run_drift_detection(df_train_snapshot: pd.DataFrame, df_current_features: pd.DataFrame, feature_cols: list[str]):
    """Hitung PSI tiap fitur dan tentukan apakah perlu retrain."""
    results = {}

    if df_train_snapshot is None or df_train_snapshot.empty:
        return {}, False
    if df_current_features is None or df_current_features.empty:
        return {}, False

    train = df_train_snapshot.copy()
    current = df_current_features.copy()
    train.columns = [c.lower() for c in train.columns]
    current.columns = [c.lower() for c in current.columns]

    for col in feature_cols:
        col_l = col.lower()
        if col_l not in train.columns or col_l not in current.columns:
            results[col] = {"psi": None, "status": "missing"}
            continue

        psi = compute_psi(train[col_l], current[col_l])
        if psi is None:
            status = "missing"
        elif psi > 0.25:
            status = "critical"
        elif psi > 0.10:
            status = "warning"
        else:
            status = "stable"
        results[col] = {"psi": psi, "status": status}

    n_critical = sum(1 for v in results.values() if v["status"] == "critical")
    n_warning = sum(1 for v in results.values() if v["status"] == "warning")
    n_stable = sum(1 for v in results.values() if v["status"] == "stable")

    print("\n[Drift Detection] Summary")
    print(f"  Stable   (PSI < 0.10) : {n_stable} features")
    print(f"  Warning  (PSI < 0.25) : {n_warning} features")
    print(f"  Critical (PSI > 0.25) : {n_critical} features")

    needs_retrain = n_critical >= N_CRITICAL_DRIFT_TRIGGER or n_warning >= N_WARNING_DRIFT_TRIGGER
    return results, needs_retrain


def log_monitoring_run(
    engine,
    run_date: "date | None" = None,
    perf: dict | None = None,
    drift_results: dict | None = None,
    retrain_triggered: bool = False,
    champion_version: str | None = None,
    notes: str | None = None,
) -> None:
    """Catat hasil weekly MLOps run ke tabel model_monitoring_log.

    Parameters
    ----------
    engine            : SQLAlchemy engine
    run_date          : tanggal run (default: hari ini)
    perf              : dict hasil compute_model_performance()
    drift_results     : dict hasil run_drift_detection()
    retrain_triggered : apakah retraining dilakukan
    champion_version  : version string dari model champion aktif
    notes             : catatan tambahan (misal: alasan retrain)
    """
    if engine is None:
        return

    today = run_date or date.today()
    perf = perf or {}
    drift_results = drift_results or {}

    n_critical = sum(1 for v in drift_results.values() if isinstance(v, dict) and v.get("status") == "critical")
    n_warning = sum(1 for v in drift_results.values() if isinstance(v, dict) and v.get("status") == "warning")

    row = {
        "run_date": str(today),
        "auc": perf.get("auc") if perf.get("status") == "ok" else None,
        "calibration_gap": perf.get("calibration_gap") if perf.get("status") == "ok" else None,
        "n_samples": perf.get("n_samples"),
        "n_critical_drift": n_critical,
        "n_warning_drift": n_warning,
        "retrain_triggered": retrain_triggered,
        "champion_version": champion_version,
        "notes": notes,
    }

    try:
        pd.DataFrame([row]).to_sql(
            "model_monitoring_log",
            engine,
            if_exists="append",
            index=False,
        )
        print(f"[Monitor] Run log saved to model_monitoring_log for {today}")
    except Exception as exc:
        print(f"[Monitor] Failed to write model_monitoring_log: {exc}")

"""Champion-Challenger workflow untuk CollectAI MLOps.

Generik untuk ke-4 model_type (recovery, self_cure, roll_forward,
ptp_success) — setiap fungsi menerima parameter ``model_type`` supaya shadow
scoring, evaluasi, dan promotion tercatat terpisah per model_type di
registry dan di tabel shadow_scores (kolom ``model_type``).
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ARCHIVE_DIR, MIN_AUC_IMPROVEMENT, MIN_SAMPLES_FOR_EVAL  # noqa: E402
from src.model_registry import _load_registry, _save_registry, DEFAULT_MODEL_TYPE  # noqa: E402


def _load_artifact(path: str):
    artifact = joblib.load(path)
    if isinstance(artifact, dict):
        model = artifact.get("model")
        feature_cols = artifact.get("feature_cols")
    else:
        model = artifact
        feature_cols = None
    if model is None:
        raise ValueError(f"Artifact invalid: {path}")
    return artifact, model, feature_cols


def _score(model, feature_cols, df: pd.DataFrame):
    if not feature_cols:
        feature_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df.copy()
    for col in feature_cols:
        if col not in X.columns:
            X[col] = 0.0
    X = X[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return model.predict_proba(X)[:, 1]


def run_shadow_scoring(
    df_features_enriched: pd.DataFrame,
    feature_cols: list[str],
    champion_path: str,
    challenger_path: str,
    engine=None,
    model_type: str = DEFAULT_MODEL_TYPE,
) -> pd.DataFrame:
    """Score dataset dengan champion dan challenger secara paralel."""
    champ_artifact, champ_model, champ_cols = _load_artifact(champion_path)
    chal_artifact, chal_model, chal_cols = _load_artifact(challenger_path)

    champ_cols = champ_cols or feature_cols
    chal_cols = chal_cols or feature_cols

    df = df_features_enriched.copy()
    df["champion_score"] = np.round(_score(champ_model, champ_cols, df), 4)
    df["challenger_score"] = np.round(_score(chal_model, chal_cols, df), 4)

    out = df[["contract_no", "cust_id", "champion_score", "challenger_score"]].copy()
    out["score_delta"] = (out["challenger_score"] - out["champion_score"]).round(4)
    out["snapshot_date"] = datetime.today().date()
    out["model_type"] = model_type

    print(f"[Shadow Scoring:{model_type}] {len(out):,} contracts")
    print(f"  Champion avg score   : {out['champion_score'].mean():.4f}")
    print(f"  Challenger avg score : {out['challenger_score'].mean():.4f}")
    print(f"  Avg delta            : {out['score_delta'].mean():+.4f}")

    if engine is not None:
        try:
            out.to_sql("shadow_scores", engine, if_exists="append", index=False)
        except Exception as exc:
            print(f"[Shadow Scoring:{model_type}] append shadow_scores skipped: {exc}")

    return out


def evaluate_champion_vs_challenger(
    df_labeled: pd.DataFrame,
    df_shadow_scores: pd.DataFrame,
    min_samples: int = MIN_SAMPLES_FOR_EVAL,
    min_auc_improvement: float = MIN_AUC_IMPROVEMENT,
    target_col: str = "actual_paid",
):
    """Bandingkan champion dan challenger berdasarkan actual outcome.

    ``target_col`` dipilih sesuai model_type yang dievaluasi (mis.
    ``actual_self_cure`` untuk model_type='self_cure'), lihat
    config.settings.MODEL_TYPE_TARGET_COL.
    """
    if df_labeled is None or df_labeled.empty or df_shadow_scores is None or df_shadow_scores.empty:
        return {"decision": "NO_EVALUATION", "reason": "missing_data"}

    labeled = df_labeled.copy()
    labeled.columns = [c.lower() for c in labeled.columns]
    shadow = df_shadow_scores.copy()
    shadow.columns = [c.lower() for c in shadow.columns]

    target_col = target_col.lower()
    if "contract_no" not in labeled.columns or target_col not in labeled.columns:
        return {"decision": "NO_EVALUATION", "reason": f"missing_required_columns ({target_col})"}

    grouped_shadow = (
        shadow.sort_values("snapshot_date")
        .groupby("contract_no", as_index=False)
        .last()[["contract_no", "champion_score", "challenger_score"]]
    )

    eval_df = labeled.merge(grouped_shadow, on="contract_no", how="inner")
    eval_df = eval_df.dropna(subset=[target_col, "champion_score", "challenger_score"])

    n = len(eval_df)
    if n < min_samples:
        return {"decision": "INSUFFICIENT_DATA", "n_samples": n}
    if eval_df[target_col].nunique() < 2:
        return {"decision": "INSUFFICIENT_LABEL_VARIANCE", "n_samples": n}

    y_true = pd.to_numeric(eval_df[target_col], errors="coerce").fillna(0).astype(int)
    champ_auc = roc_auc_score(y_true, pd.to_numeric(eval_df["champion_score"], errors="coerce").fillna(0.0))
    chal_auc = roc_auc_score(y_true, pd.to_numeric(eval_df["challenger_score"], errors="coerce").fillna(0.0))
    delta = chal_auc - champ_auc

    actual_rate = float(y_true.mean())
    champ_calib = abs(float(eval_df["champion_score"].mean()) - actual_rate)
    chal_calib = abs(float(eval_df["challenger_score"].mean()) - actual_rate)

    print("\n[Champion vs Challenger]")
    print(f"  n_samples       : {n:,}")
    print(f"  Actual rate     : {actual_rate:.1%}")
    print(f"  Champion AUC    : {champ_auc:.4f} (calibration gap: {champ_calib:.4f})")
    print(f"  Challenger AUC  : {chal_auc:.4f} (calibration gap: {chal_calib:.4f})")
    print(f"  AUC Delta       : {delta:+.4f}")

    if delta >= min_auc_improvement:
        decision = "PROMOTE_CHALLENGER"
    elif delta <= -min_auc_improvement:
        decision = "KEEP_CHAMPION"
    else:
        decision = "NO_SIGNIFICANT_DIFF"

    return {
        "decision": decision,
        "n_samples": n,
        "champion_auc": round(float(champ_auc), 4),
        "challenger_auc": round(float(chal_auc), 4),
        "auc_delta": round(float(delta), 4),
        "champion_calibration_gap": round(float(champ_calib), 4),
        "challenger_calibration_gap": round(float(chal_calib), 4),
        "evaluated_at": datetime.now().isoformat(),
    }


def promote_challenger(
    champion_path: str,
    challenger_path: str,
    backup_dir: str = ARCHIVE_DIR,
    model_type: str = DEFAULT_MODEL_TYPE,
):
    """Promote challenger menjadi champion baru dan arsipkan champion lama.

    Registry di-update per model_type supaya versioning masing-masing model
    tidak saling tercampur.
    """
    os.makedirs(backup_dir, exist_ok=True)
    if not os.path.exists(champion_path):
        raise FileNotFoundError(f"Champion model tidak ditemukan: {champion_path}")
    if not os.path.exists(challenger_path):
        raise FileNotFoundError(f"Challenger model tidak ditemukan: {challenger_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{model_type}_model_champion_{timestamp}.pkl")
    shutil.copy2(champion_path, backup_path)
    shutil.copy2(challenger_path, champion_path)

    registry = _load_registry()
    bucket = registry.setdefault("model_types", {}).setdefault(
        model_type, {"current_champion": None, "current_challenger": None, "history": []}
    )
    challenger_entry = bucket.get("current_challenger")
    if challenger_entry:
        bucket["current_champion"] = {
            **challenger_entry,
            "role": "champion",
            "registered": datetime.now().isoformat(),
        }
    bucket["current_challenger"] = None
    _save_registry(registry)

    print(f"[Promotion:{model_type}] Champion lama diarsipkan: {backup_path}")
    print(f"[Promotion:{model_type}] Challenger dipromote ke champion: {champion_path}")
    return backup_path

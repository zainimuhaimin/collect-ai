"""Training sub-model PTP Success untuk CollectAI."""
from __future__ import annotations

from datetime import datetime
import os
import sys
import joblib
import pandas as pd
from sqlalchemy import create_engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import (  # noqa: E402
    DB_URL,
    PTP_SUCCESS_MODEL_PATH,
    PTP_SUCCESS_CHALLENGER_MODEL_PATH,
    PTP_SUCCESS_FEATURE_COLS,
    TARGET_COL,
    RETRAIN_DECAY_RATE,
    LABEL_WINDOW_DAYS,
)
from src.feature_engineering import compute_contract_features, compute_customer_features, enrich_with_cbs  # noqa: E402
from src.cbs_builder import build_cbs  # noqa: E402
from src.outcome_labeler import build_target_variable  # noqa: E402
from src.retrain_strategies import strategy_recency_weighted  # noqa: E402
from src.model_registry import register_model, get_champion_path  # noqa: E402

MODEL_TYPE = "ptp_success"


def _load_source_data(engine):
    df_contract = pd.read_sql("SELECT * FROM contract_snapshot", engine)
    df_payment = pd.read_sql("SELECT * FROM payment_history", engine)
    df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", engine)
    df_customer = pd.read_sql("SELECT * FROM customer_master", engine)
    return df_contract, df_payment, df_lkp, df_customer


def run_train_ptp_success(reference_date=None):
    reference_date = pd.Timestamp(reference_date).normalize() if reference_date else pd.Timestamp.today().normalize()
    engine = create_engine(DB_URL)

    df_contract, df_payment, df_lkp, df_customer = _load_source_data(engine)

    # Anti-leakage: fitur dihitung dari histori SEBELUM window label.
    feature_cutoff = reference_date - pd.Timedelta(days=LABEL_WINDOW_DAYS)

    contract_features = compute_contract_features(
        df_contract, df_payment, df_lkp, reference_date,
        df_customer=df_customer, feature_cutoff_date=feature_cutoff,
    )
    customer_features = compute_customer_features(
        df_contract, df_payment, df_lkp, df_customer, contract_features,
        feature_cutoff_date=feature_cutoff,
    )
    cbs_df = build_cbs(customer_features)
    enriched = enrich_with_cbs(contract_features, cbs_df)

    # Filter untuk PTP Success: Populasi yang pernah membuat PTP
    enriched = enriched[enriched["total_ptp_made"] > 0].copy()
    if len(enriched) < 50:
        print("[Train PTP Success] Data terlalu sedikit (<50 baris), dibatalkan.")
        return None, None

    for c in PTP_SUCCESS_FEATURE_COLS:
        if c not in enriched.columns:
            enriched[c] = 0
    enriched[PTP_SUCCESS_FEATURE_COLS] = enriched[PTP_SUCCESS_FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # Target: whether they paid (1) or didn't pay (0). 
    # Karena populasinya adalah pembuat PTP, maka actual_paid = PTP kept (berhasil ditepati).
    train_df = build_target_variable(
        enriched,
        df_payment,
        scoring_date=reference_date,
        n_days=LABEL_WINDOW_DAYS,
    )

    paid_rate = float(train_df[TARGET_COL].mean()) if len(train_df) else 0.0
    print(f"[Train PTP Success] Label paid rate (PTP kept rate): {paid_rate:.1%}")

    model, metadata = strategy_recency_weighted(
        train_df,
        PTP_SUCCESS_FEATURE_COLS,
        target_col=TARGET_COL,
        decay_rate=RETRAIN_DECAY_RATE,
    )

    artifact = {
        "model": model,
        "feature_cols": PTP_SUCCESS_FEATURE_COLS,
        "target_col": TARGET_COL,
        "trained_at": datetime.now().isoformat(),
        "metadata": metadata,
        "training_features_sample": train_df[PTP_SUCCESS_FEATURE_COLS].sample(
            n=min(1000, len(train_df)), random_state=42
        ).reset_index(drop=True),
    }

    try:
        get_champion_path(model_type=MODEL_TYPE)
        target_path, role = PTP_SUCCESS_CHALLENGER_MODEL_PATH, "challenger"
    except FileNotFoundError:
        target_path, role = PTP_SUCCESS_MODEL_PATH, "champion"

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    joblib.dump(artifact, target_path)
    version = register_model(target_path, metadata, role=role, model_type=MODEL_TYPE)

    print(f"[Train PTP Success] Model saved ({role}): {target_path}")
    print(f"[Train PTP Success] Registry version: {version}")
    print(f"[Train PTP Success] AUC: {metadata.get('auc')}")

    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        imp_df = pd.DataFrame({"feature": PTP_SUCCESS_FEATURE_COLS, "importance": importances})
        imp_df = imp_df.sort_values("importance", ascending=False).head(5)
        print("[Train PTP Success] Top-5 feature importance")
        print(imp_df.to_string(index=False))

    return target_path, metadata

if __name__ == "__main__":
    run_train_ptp_success()

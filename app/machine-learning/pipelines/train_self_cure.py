"""Training sub-model Self-Cure untuk CollectAI."""
from __future__ import annotations

from datetime import datetime
import os
import sys
import joblib
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import (  # noqa: E402
    DB_URL,
    SELF_CURE_MODEL_PATH,
    SELF_CURE_CHALLENGER_MODEL_PATH,
    SELF_CURE_FEATURE_COLS,
    TARGET_COL,
    RETRAIN_DECAY_RATE,
    LABEL_WINDOW_DAYS,
    FEATURE_CHUNK_BATCH_SIZE,
)
from src.feature_engineering import enrich_with_cbs, filter_restructured_for_training  # noqa: E402
from src.chunked_features import compute_features_chunked  # noqa: E402
from src.cbs_builder import build_cbs  # noqa: E402
from src.outcome_labeler import build_target_variable  # noqa: E402
from src.retrain_strategies import strategy_recency_weighted  # noqa: E402
from src.model_registry import register_model, get_champion_path  # noqa: E402
from src.perf import stage_timer, new_run_id  # noqa: E402

MODEL_TYPE = "self_cure"


def _load_source_data(engine):
    df_contract = pd.read_sql("SELECT * FROM contract_snapshot", engine)
    df_customer = pd.read_sql("SELECT * FROM customer_master", engine)
    return df_contract, df_customer


def _load_label_payments(engine, start, end):
    """Payment_history dipersempit ke jendela label `[start, end]` SAJA —
    build_target_variable() sendiri memfilter ulang ke jendela yang PERSIS
    sama (src/outcome_labeler.py), jadi ini superset-safe (TASK-P5 item 1)."""
    return pd.read_sql(
        text("SELECT * FROM payment_history WHERE actual_pay_date >= :start AND actual_pay_date <= :end"),
        engine, params={"start": pd.Timestamp(start).date(), "end": pd.Timestamp(end).date()},
    )


def run_train_self_cure(reference_date=None):
    reference_date = pd.Timestamp(reference_date).normalize() if reference_date else pd.Timestamp.today().normalize()
    engine = create_engine(DB_URL)
    run_id = new_run_id()

    with stage_timer(run_id, "train_self_cure:load") as t:
        df_contract, df_customer = _load_source_data(engine)
        t.rows = len(df_contract)
    n = df_customer["cust_id"].nunique() if "cust_id" in df_customer.columns else None

    # Anti-leakage: fitur dihitung dari histori SEBELUM window label.
    feature_cutoff = reference_date - pd.Timedelta(days=LABEL_WINDOW_DAYS)

    # TASK-P5 item 1: dipecah per batch cust_id (src/chunked_features.py).
    with stage_timer(run_id, "train_self_cure:feature", n_customers=n) as t:
        contract_features, customer_features = compute_features_chunked(
            engine, df_contract, df_customer, reference_date,
            feature_cutoff_date=feature_cutoff, batch_size=FEATURE_CHUNK_BATCH_SIZE,
            pass_customer_to_contract_features=True,
        )
        cbs_df = build_cbs(customer_features)
        enriched = enrich_with_cbs(contract_features, cbs_df)
        enriched = filter_restructured_for_training(enriched)

        # Filter untuk Self-Cure: Cycle awal (C0/C1)
        enriched = enriched[enriched["cycle_encoded"] <= 1].copy()
        if len(enriched) < 50:
            print("[Train Self-Cure] Data terlalu sedikit (<50 baris), dibatalkan.")
            return None, None

        for c in SELF_CURE_FEATURE_COLS:
            if c not in enriched.columns:
                enriched[c] = 0
        enriched[SELF_CURE_FEATURE_COLS] = enriched[SELF_CURE_FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        t.rows = len(enriched)

    with stage_timer(run_id, "train_self_cure:train", n_customers=n) as t:
        df_payment_label_window = _load_label_payments(engine, feature_cutoff, reference_date)
        train_df = build_target_variable(
            enriched,
            df_payment_label_window,
            scoring_date=reference_date,
            n_days=LABEL_WINDOW_DAYS,
        )

        paid_rate = float(train_df[TARGET_COL].mean()) if len(train_df) else 0.0
        print(f"[Train Self-Cure] Label paid rate: {paid_rate:.1%}")

        model, metadata = strategy_recency_weighted(
            train_df,
            SELF_CURE_FEATURE_COLS,
            target_col=TARGET_COL,
            decay_rate=RETRAIN_DECAY_RATE,
        )
        t.rows = len(train_df)

    artifact = {
        "model": model,
        "feature_cols": SELF_CURE_FEATURE_COLS,
        "target_col": TARGET_COL,
        "trained_at": datetime.now().isoformat(),
        "metadata": metadata,
        "training_features_sample": train_df[SELF_CURE_FEATURE_COLS].sample(
            n=min(1000, len(train_df)), random_state=42
        ).reset_index(drop=True),
    }

    with stage_timer(run_id, "train_self_cure:register", n_customers=n):
        # Bootstrap sebagai champion jika belum ada champion self_cure sama
        # sekali; jika sudah ada, simpan sebagai challenger — harus lolos
        # shadow-scoring + evaluasi (weekly_mlops.py) sebelum dipromosikan,
        # sama seperti alur model recovery utama.
        try:
            get_champion_path(model_type=MODEL_TYPE)
            target_path, role = SELF_CURE_CHALLENGER_MODEL_PATH, "challenger"
        except FileNotFoundError:
            target_path, role = SELF_CURE_MODEL_PATH, "champion"

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        joblib.dump(artifact, target_path)
        version = register_model(target_path, metadata, role=role, model_type=MODEL_TYPE)

    print(f"[Train Self-Cure] Model saved ({role}): {target_path}")
    print(f"[Train Self-Cure] Registry version: {version}")
    print(f"[Train Self-Cure] AUC: {metadata.get('auc')}")

    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        imp_df = pd.DataFrame({"feature": SELF_CURE_FEATURE_COLS, "importance": importances})
        imp_df = imp_df.sort_values("importance", ascending=False).head(5)
        print("[Train Self-Cure] Top-5 feature importance")
        print(imp_df.to_string(index=False))

    return target_path, metadata

if __name__ == "__main__":
    run_train_self_cure()

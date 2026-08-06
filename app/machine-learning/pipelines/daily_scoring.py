"""Runner harian scoring CollectAI."""
from __future__ import annotations

from datetime import datetime
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text, inspect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import DB_URL, LOG_PATH, CHAMPION_MODEL_PATH  # noqa: E402
from src.feature_engineering import compute_contract_features, compute_customer_features, enrich_with_cbs  # noqa: E402
from src.cbs_builder import build_cbs  # noqa: E402
from src.scoring_engine import score_contracts, compute_confidence_level, run_quality_check  # noqa: E402
from src.business_rules import apply_risk_segment, apply_nba, apply_priority  # noqa: E402
from src.model_registry import get_champion_path  # noqa: E402
from pipelines.restructuring_runner import run_restructuring_assessment  # noqa: E402


def _load_table(engine, query: str) -> pd.DataFrame:
    return pd.read_sql(query, engine)


def _resolve_champion_path() -> str:
    try:
        return get_champion_path()
    except Exception:
        if os.path.exists(CHAMPION_MODEL_PATH):
            return CHAMPION_MODEL_PATH
        raise FileNotFoundError("Champion model belum tersedia")


def _upsert_ai_output(engine, df_publish: pd.DataFrame):
    cols = [
        "contract_no", "cust_id", "recovery_score", "confidence_level", "confidence_category",
        "risk_segment", "nba_recommendation", "priority_level", "scoring_date", "updated_at",
        "self_cure_probability", "roll_forward_risk", "ptp_success_probability", "nba_trigger",
    ]

    # Fill missing new columns with NULL for fallback if they don't exist
    for c in ["self_cure_probability", "roll_forward_risk", "ptp_success_probability", "nba_trigger"]:
        if c not in df_publish.columns:
            df_publish[c] = None

    payload = df_publish[cols].copy()

    with engine.begin() as conn:
        if len(payload) > 0:
            try:
                conn.execute(
                    text("DELETE FROM ai_intelligence_output WHERE scoring_date = :scoring_date"),
                    {"scoring_date": payload["scoring_date"].iloc[0]},
                )
            except Exception:
                pass
            payload.to_sql("ai_intelligence_output", conn, if_exists="append", index=False)


def _upsert_feature_snapshot(engine, df_features: pd.DataFrame, scoring_date):
    snapshot = df_features.copy()
    snapshot["scoring_date"] = scoring_date
    snapshot["updated_at"] = datetime.now()

    inspector = inspect(engine)
    if inspector.has_table("scoring_feature_snapshot"):
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM scoring_feature_snapshot WHERE scoring_date = :scoring_date"),
                {"scoring_date": scoring_date},
            )
            
    if len(snapshot) > 0:
        with engine.begin() as conn:
            snapshot.to_sql("scoring_feature_snapshot", conn, if_exists="append", index=False)


def _append_log(summary: dict):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    row = pd.DataFrame([summary])
    if os.path.exists(LOG_PATH):
        row.to_csv(LOG_PATH, mode="a", index=False, header=False)
    else:
        row.to_csv(LOG_PATH, mode="w", index=False)


def run_daily_scoring(reference_date=None, strict_qc=None):
    """``strict_qc``: teruskan False untuk run dev/testing dengan data
    sintetis (menurunkan cek distribusi QC jadi soft-warning, bukan
    hard-fail). Default None = ikuti config.settings.STRICT_QC (True untuk
    produksi)."""
    ref_date = pd.Timestamp(reference_date).date() if reference_date else pd.Timestamp.today().date()
    engine = create_engine(DB_URL)

    # Step 1
    try:
        df_contract = _load_table(engine, "SELECT * FROM contract_snapshot WHERE status='aktif'")
        if df_contract.empty:
            df_contract = _load_table(engine, "SELECT * FROM contract_snapshot")
    except Exception:
        df_contract = _load_table(engine, "SELECT * FROM contract_snapshot")

    df_payment = _load_table(engine, "SELECT * FROM payment_history")
    df_lkp = _load_table(engine, "SELECT * FROM lkp_interaction")
    try:
        df_cbs = _load_table(engine, "SELECT * FROM customer_behavioral_standing")
    except Exception:
        df_cbs = pd.DataFrame(columns=["cust_id"])

    # Step 2
    df_contract_features = compute_contract_features(df_contract, df_payment, df_lkp, ref_date)

    # Bootstrap CBS jika belum ada data
    if df_cbs.empty:
        try:
            df_customer = _load_table(engine, "SELECT * FROM customer_master")
            df_customer_features = compute_customer_features(
                df_contract,
                df_payment,
                df_lkp,
                df_customer,
                df_contract_features,
            )
            df_cbs = build_cbs(df_customer_features)
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM customer_behavioral_standing"))
                if len(df_cbs) > 0:
                    df_cbs.to_sql("customer_behavioral_standing", conn, if_exists="append", index=False)
            print(f"[Daily Scoring] CBS bootstrap: {len(df_cbs):,} records")
        except Exception as e:
            print(f"[Daily Scoring] CBS bootstrap skipped: {e}")
            df_cbs = pd.DataFrame(columns=["cust_id"])

    # Step 3
    cbs_customer_set = set(df_cbs["cust_id"]) if "cust_id" in df_cbs.columns else set()
    df_features = enrich_with_cbs(df_contract_features, df_cbs)
    df_features["cbs_exists"] = df_features["cust_id"].isin(cbs_customer_set)

    # Fill null CBS features untuk scoring
    fill_cols = [
        "ptp_reliability_index", "delay_trend", "historical_default_count", "income_debt_ratio",
        "active_contract_count", "total_active_ots", "behavioral_grade_encoded", "b_list_flag",
    ]
    for c in fill_cols:
        if c not in df_features.columns:
            df_features[c] = 0
    df_features[fill_cols] = df_features[fill_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # Step 4
    champion_path = _resolve_champion_path()
    df_scored = score_contracts(df_features, champion_path)

    # Step 5
    df_scored = compute_confidence_level(df_scored)

    # Step 6
    df_scored["broken_ptp_count"] = (
        pd.to_numeric(df_scored.get("total_ptp_made", 0), errors="coerce").fillna(0)
        - pd.to_numeric(df_scored.get("total_ptp_kept", 0), errors="coerce").fillna(0)
    )
    df_scored = apply_risk_segment(df_scored)
    df_scored = apply_nba(df_scored, df_cbs)
    df_scored = apply_priority(df_scored)

    # Step 7.5 — Restructuring recommendation (TASK-52). Tidak boleh
    # menggagalkan publish scoring utama kalau step ini error; sengaja
    # dijalankan dengan df_scored di memori (belum ada di ai_intelligence_output
    # sampai Step 8) supaya siklus assessment ikut skor hari ini juga.
    try:
        run_restructuring_assessment(reference_date=ref_date, engine=engine, df_scored=df_scored)
    except Exception as exc:
        print(f"[Daily Scoring] Restructuring assessment gagal (dilewati): {exc}")

    # Step 7
    qc_result = run_quality_check(df_scored, strict=strict_qc)

    # Step 8
    df_scored["scoring_date"] = ref_date
    df_scored["updated_at"] = datetime.now()
    _upsert_ai_output(engine, df_scored)
    _upsert_feature_snapshot(engine, df_features, ref_date)

    # Step 9
    segment_counts = df_scored["risk_segment"].value_counts().to_dict()
    priority_counts = df_scored["priority_level"].value_counts().to_dict()
    summary = {
        "run_at": datetime.now().isoformat(),
        "reference_date": str(ref_date),
        "n_scored": int(len(df_scored)),
        "wont_pay_pct": qc_result.get("wont_pay_pct"),
        "self_cure_pct": qc_result.get("self_cure_pct"),
        "critical_pct": qc_result.get("critical_pct"),
        "segment_breakdown": str(segment_counts),
        "priority_breakdown": str(priority_counts),
    }
    _append_log(summary)

    # Step 10
    print("\n[Daily Scoring] Success")
    print(f"  Contracts scored: {len(df_scored):,}")
    
    # MULTI-SCORE SUMMARY
    print(f"\n  MULTI-SCORE SUMMARY:")
    print(f"  Avg RECOVERY_SCORE       : {df_scored.get('recovery_score', pd.Series([0])).mean():.4f}")
    if "self_cure_probability" in df_scored.columns:
        print(f"  Avg SELF_CURE_PROB       : {df_scored['self_cure_probability'].mean():.4f}")
        print(f"  Will Self-Cure (prob>0.7): {(df_scored['self_cure_probability']>=0.70).sum():,}")
    if "roll_forward_risk" in df_scored.columns:
        print(f"  Avg ROLL_FORWARD_RISK    : {df_scored['roll_forward_risk'].mean():.4f}")
        print(f"  High Roll Forward Risk   : {(df_scored['roll_forward_risk']>=0.75).sum():,}")
    if "ptp_success_probability" in df_scored.columns:
        print(f"  Avg PTP_SUCCESS_PROB     : {df_scored['ptp_success_probability'].mean():.4f}")

    print(f"  Segment breakdown: {segment_counts}")
    print(f"  Priority breakdown: {priority_counts}")

    return df_scored


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_daily_scoring(sys.argv[1])
    else:
        run_daily_scoring()

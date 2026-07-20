"""Weekly MLOps orchestrator for CollectAI.

Dijalankan setiap Senin pagi (atau manual):
    python pipelines/weekly_mlops.py

Flow:
    Step 1  – Label outcome baru dari scoring records lama
    Step 2  – Bangun labeled dataset untuk monitoring/retraining
    Step 3  – Hitung performa model (AUC, calibration) 30 hari terakhir
    Step 4  – Hitung drift pada feature distributions vs training snapshot
    Step 5  – Retrain challenger jika AUC < floor ATAU drift critical
    Step 6  – Shadow scoring + evaluasi setelah >= SHADOW_DAYS_MIN hari
    Step 7  – Log ke model_monitoring_log (database)
    Step 8  – Print ringkasan
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

import joblib
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import (  # noqa: E402
    DB_URL,
    CHAMPION_MODEL_PATH,
    CHALLENGER_MODEL_PATH,
    FEATURE_COLS,
    TARGET_COL,
    RETRAIN_DECAY_RATE,
    SHADOW_DAYS_MIN,
    AUC_FLOOR,
    MODEL_TYPE_FEATURE_COLS,
    MODEL_TYPE_TARGET_COL,
)
from src.outcome_labeler import label_historical_scores, get_labeled_dataset  # noqa: E402
from src.model_monitor import (  # noqa: E402
    compute_model_performance,
    run_drift_detection,
    log_monitoring_run,
)
from src.retrain_strategies import strategy_recency_weighted  # noqa: E402
from src.champion_challenger import (  # noqa: E402
    run_shadow_scoring,
    evaluate_champion_vs_challenger,
    promote_challenger,
)
from src.model_registry import (  # noqa: E402
    register_model,
    get_champion_path,
    get_challenger_path,
    get_performance_history,
    _load_registry,
)

# Sub-model yang punya training pipeline terpisah (pipelines/train_*.py) dan
# tidak di-retrain otomatis dari sini — weekly_mlops hanya menjalankan siklus
# shadow-scoring -> evaluate -> promote untuk challenger yang SUDAH ada
# (dibuat dengan menjalankan pipeline training-nya masing-masing).
SUB_MODEL_TYPES = ["self_cure", "roll_forward", "ptp_success"]
from src.feature_engineering import (  # noqa: E402
    compute_contract_features,
    compute_customer_features,
    enrich_with_cbs,
)
from src.cbs_builder import build_cbs  # noqa: E402


# ── HELPERS ────────────────────────────────────────────────────────

def _load_df(engine, query: str) -> pd.DataFrame:
    return pd.read_sql(query, engine)


def _ensure_snapshot_dataset(engine) -> pd.DataFrame:
    """Load tabel scoring_feature_snapshot jika tersedia (optional)."""
    try:
        snapshot = pd.read_sql("SELECT * FROM scoring_feature_snapshot", engine)
    except Exception:
        snapshot = pd.DataFrame()
    if snapshot.empty:
        return snapshot
    snapshot.columns = [c.lower() for c in snapshot.columns]
    return snapshot


def _build_labeled_training_set(engine) -> pd.DataFrame:
    """Load scoring_labels dan join dengan feature snapshot jika tersedia."""
    labeled = get_labeled_dataset(engine)
    if labeled.empty:
        return pd.DataFrame()

    snapshot = _ensure_snapshot_dataset(engine)
    if snapshot.empty:
        # Tidak ada feature snapshot — kembalikan labeled as-is
        # (fitur diisi 0 saat retraining)
        return labeled

    snapshot_keys = snapshot.copy()
    snapshot_keys["scoring_date"] = pd.to_datetime(
        snapshot_keys["scoring_date"], errors="coerce"
    )

    labeled = labeled.copy()
    labeled.columns = [c.lower() for c in labeled.columns]
    labeled["scoring_date"] = pd.to_datetime(labeled["scoring_date"], errors="coerce")

    merged = labeled.merge(
        snapshot_keys,
        on=["contract_no", "scoring_date"],
        how="inner",
        suffixes=("", "_snap"),
    )
    return merged


def _prepare_artifact(model, metadata: dict, df_train: pd.DataFrame) -> dict:
    """Bungkus model + metadata + feature sample untuk drift detection masa depan."""
    artifact = {
        "model": model,
        "feature_cols": FEATURE_COLS,
        "target_col": TARGET_COL,
        "trained_at": datetime.now().isoformat(),
        "metadata": metadata,
    }
    if not df_train.empty:
        sample_cols = [c for c in FEATURE_COLS if c in df_train.columns]
        if sample_cols:
            artifact["training_features_sample"] = (
                df_train[sample_cols]
                .sample(n=min(1000, len(df_train)), random_state=42)
                .reset_index(drop=True)
            )
    return artifact


def _save_artifact(path: str, artifact: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(artifact, path)


def _count_shadow_days(engine, model_type: str = "recovery") -> int:
    """Hitung berapa hari challenger MODEL_TYPE tertentu sudah berjalan di
    shadow mode. Dihitung dari MIN(snapshot_date) di tabel shadow_scores
    untuk model_type tsb — selisih antara tanggal shadow pertama dengan
    hari ini.
    """
    if engine is None:
        return 0
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT MIN(snapshot_date) FROM shadow_scores WHERE model_type = :mt"),
                {"mt": model_type},
            ).scalar()
        if result is None:
            return 0
        first_shadow = pd.Timestamp(result).normalize()
        days_shadow = (pd.Timestamp.today().normalize() - first_shadow).days
        return max(0, int(days_shadow))
    except Exception:
        return 0


def _run_submodel_challenger_cycle(model_type, engine, df_labeled, current_features):
    """Siklus champion-challenger generik untuk 1 sub-model: drift check,
    lalu — jika ada challenger yang sudah dibuat lewat pipelines/train_*.py —
    shadow-scoring, evaluasi, dan promote jika challenger menang.

    Catatan: retrain sub-model TIDAK dipicu otomatis dari sini. Operator
    menjalankan pipelines/train_self_cure.py (dst) secara terjadwal untuk
    menghasilkan challenger; fungsi ini hanya mengurus evaluasi & promosinya.
    Monitoring AUC historis (seperti AUC_FLOOR untuk recovery) belum tersedia
    untuk sub-model karena scoring_labels belum menyimpan histori skor
    sub-model — trigger drift tetap dihitung dan dilaporkan sebagai sinyal.
    """
    feature_cols = MODEL_TYPE_FEATURE_COLS[model_type]
    target_col = MODEL_TYPE_TARGET_COL[model_type]
    result = {"model_type": model_type, "needs_retrain_drift": False, "promoted": False}

    try:
        champion_path = get_champion_path(model_type=model_type)
    except FileNotFoundError:
        print(f"[MLOps:{model_type}] Belum ada champion — jalankan pipelines/train_{model_type}.py dahulu")
        return result

    if not current_features.empty:
        try:
            champion_artifact = joblib.load(champion_path)
            train_snapshot = champion_artifact.get("training_features_sample", pd.DataFrame())
            if not train_snapshot.empty:
                _, needs_retrain_drift = run_drift_detection(train_snapshot, current_features, feature_cols)
                result["needs_retrain_drift"] = needs_retrain_drift
                print(f"[MLOps:{model_type}] Drift retrain triggered: {needs_retrain_drift}")
        except Exception as exc:
            print(f"[MLOps:{model_type}] Drift check gagal: {exc}")

    challenger_path = get_challenger_path(model_type=model_type)
    if not challenger_path or not os.path.exists(challenger_path):
        print(f"[MLOps:{model_type}] Tidak ada challenger aktif")
        return result

    shadow_days = _count_shadow_days(engine, model_type=model_type)
    print(f"[MLOps:{model_type}] Challenger shadow days: {shadow_days} (min: {SHADOW_DAYS_MIN})")

    shadow_scores = pd.DataFrame()
    if not current_features.empty:
        try:
            shadow_scores = run_shadow_scoring(
                current_features, feature_cols, champion_path, challenger_path,
                engine=engine, model_type=model_type,
            )
        except Exception as exc:
            print(f"[MLOps:{model_type}] Shadow scoring gagal: {exc}")

    if shadow_days < SHADOW_DAYS_MIN:
        print(f"[MLOps:{model_type}] Evaluasi belum dilakukan — {SHADOW_DAYS_MIN - shadow_days} hari lagi")
        return result

    if df_labeled.empty or shadow_scores.empty:
        print(f"[MLOps:{model_type}] Evaluasi dilewati: labeled data atau shadow scores kosong")
        return result

    try:
        eval_result = evaluate_champion_vs_challenger(df_labeled, shadow_scores, target_col=target_col)
        print(f"[MLOps:{model_type}] Evaluation decision: {eval_result.get('decision')}")
        if eval_result.get("decision") == "PROMOTE_CHALLENGER":
            promote_challenger(champion_path, challenger_path, model_type=model_type)
            register_model(
                champion_path,
                {
                    "strategy": "recency_weighted",
                    "auc": eval_result.get("challenger_auc"),
                    "evaluated_at": eval_result.get("evaluated_at"),
                    "promoted_from_challenger": challenger_path,
                },
                role="champion",
                model_type=model_type,
            )
            if os.path.exists(challenger_path):
                os.remove(challenger_path)
            result["promoted"] = True
            print(f"[MLOps:{model_type}] ✅ Challenger berhasil dipromote menjadi champion")
        else:
            print(f"[MLOps:{model_type}] Champion dipertahankan (decision: {eval_result.get('decision')})")
    except Exception as exc:
        print(f"[MLOps:{model_type}] Evaluasi champion-challenger gagal: {exc}")

    return result


# ── MAIN ORCHESTRATOR ──────────────────────────────────────────────

def run_weekly_mlops(reference_date=None):
    """Jalankan full MLOps pipeline mingguan.

    Parameters
    ----------
    reference_date : str atau date, default = hari ini
        Tanggal referensi untuk labeling dan drift detection.

    Returns
    -------
    dict ringkasan hasil run
    """
    start = datetime.now()
    ref_date = (
        pd.Timestamp(reference_date).normalize()
        if reference_date
        else pd.Timestamp.today().normalize()
    )
    engine = create_engine(DB_URL)

    print(f"\n{'=' * 72}")
    print(f"[MLOps] Weekly run - {start:%Y-%m-%d %H:%M}")
    print(f"[MLOps] Reference date: {ref_date.date()}")
    print(f"{'=' * 72}")

    # ── STEP 1: Label outcome baru ─────────────────────────────────
    print("\n[MLOps] Step 1/9 — Labeling historical scores...")
    df_ai_output = _load_df(engine, "SELECT * FROM ai_intelligence_output")
    df_payment = _load_df(engine, "SELECT * FROM payment_history")

    new_labels = label_historical_scores(df_ai_output, df_payment, engine=engine)
    print(f"[MLOps] New labels appended: {len(new_labels):,}")

    # ── STEP 2: Bangun labeled dataset ────────────────────────────
    print("\n[MLOps] Step 2/9 — Building labeled training set...")
    df_labeled = _build_labeled_training_set(engine)
    if df_labeled.empty:
        print("[MLOps] Belum ada labeled dataset yang bisa dipakai")
    else:
        print(f"[MLOps] Labeled dataset size: {len(df_labeled):,} records")

    # ── STEP 3: Model performance monitoring ──────────────────────
    print("\n[MLOps] Step 3/9 — Computing model performance...")
    perf = (
        compute_model_performance(df_labeled, window_days=30)
        if not df_labeled.empty
        else {"status": "insufficient_data", "message": "No labeled data"}
    )
    if perf.get("status") == "ok":
        print(
            f"[MLOps] AUC={perf['auc']:.4f} | "
            f"log_loss={perf['log_loss']:.4f} | "
            f"calibration_gap={perf['calibration_gap']:.4f}"
        )
    else:
        print(f"[MLOps] Performance monitor: {perf.get('message', perf.get('status'))}")

    # ── STEP 4: Drift detection ────────────────────────────────────
    print("\n[MLOps] Step 4/9 — Running drift detection...")
    drift_results = {}
    needs_retrain_drift = False
    current_features = pd.DataFrame()

    # Coba load champion; jika belum ada, skip drift detection
    champion_path = None
    train_snapshot = pd.DataFrame()
    try:
        champion_path = get_champion_path()
        champion_artifact = joblib.load(champion_path)
        train_snapshot = champion_artifact.get("training_features_sample", pd.DataFrame())
    except FileNotFoundError:
        print("[MLOps] Champion model belum ada di registry — drift detection dilewati")
    except Exception as exc:
        print(f"[MLOps] Gagal load champion artifact: {exc}")

    # current_features dihitung terlepas dari apakah champion recovery sudah
    # ada — dipakai ulang oleh drift/shadow-scoring recovery MAUPUN ke-3
    # sub-model (self_cure/roll_forward/ptp_success) di step-step berikutnya.
    try:
        df_contract = _load_df(engine, "SELECT * FROM contract_snapshot")
        df_payment_current = _load_df(engine, "SELECT * FROM payment_history")
        df_lkp = _load_df(engine, "SELECT * FROM lkp_interaction")
        df_customer = _load_df(engine, "SELECT * FROM customer_master")

        contract_features = compute_contract_features(
            df_contract, df_payment_current, df_lkp, ref_date
        )
        customer_features = compute_customer_features(
            df_contract, df_payment_current, df_lkp, df_customer, contract_features
        )
        cbs_current = build_cbs(customer_features)
        current_features = enrich_with_cbs(contract_features, cbs_current)
    except Exception as exc:
        print(f"[MLOps] Gagal menghitung current_features: {exc}")

    if champion_path and not current_features.empty:
        try:
            drift_results, needs_retrain_drift = run_drift_detection(
                train_snapshot, current_features, FEATURE_COLS
            )
            print(f"[MLOps] Drift retrain triggered: {needs_retrain_drift}")
        except Exception as exc:
            print(f"[MLOps] Drift detection gagal: {exc}")

    # ── STEP 5: Retrain challenger jika perlu ─────────────────────
    print("\n[MLOps] Step 5/9 — Evaluating retrain need...")
    needs_retrain_perf = (
        perf.get("status") == "ok"
        and perf.get("auc", 1.0) < AUC_FLOOR
    )
    should_retrain = needs_retrain_perf or needs_retrain_drift

    if not should_retrain:
        print("[MLOps] No retrain needed — model performance and drift OK")

    challenger_created = False
    if should_retrain and not df_labeled.empty:
        print("\n[MLOps] Retraining challenger model...")
        reason_parts = []
        if needs_retrain_perf:
            reason_parts.append(f"AUC={perf.get('auc'):.4f} < floor={AUC_FLOOR}")
        if needs_retrain_drift:
            reason_parts.append("feature drift critical")
        print(f"[MLOps] Retrain reason: {', '.join(reason_parts)}")

        train_df = df_labeled.copy()
        # Pastikan semua feature cols tersedia (isi 0 jika tidak ada)
        for col in FEATURE_COLS:
            if col not in train_df.columns:
                train_df[col] = 0.0
        train_df[FEATURE_COLS] = (
            train_df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        )

        if TARGET_COL not in train_df.columns:
            print(f"[MLOps] Retrain dilewati: kolom target '{TARGET_COL}' tidak ada")
        else:
            try:
                model, metadata = strategy_recency_weighted(
                    train_df,
                    FEATURE_COLS,
                    target_col=TARGET_COL,
                    decay_rate=RETRAIN_DECAY_RATE,
                )
                artifact = _prepare_artifact(model, metadata, train_df)
                _save_artifact(CHALLENGER_MODEL_PATH, artifact)
                version = register_model(CHALLENGER_MODEL_PATH, metadata, role="challenger")
                challenger_created = True
                print(f"[MLOps] Challenger saved  : {CHALLENGER_MODEL_PATH}")
                print(f"[MLOps] Challenger version: {version}")
                print(f"[MLOps] Challenger AUC    : {metadata.get('auc')}")
            except Exception as exc:
                print(f"[MLOps] Retrain gagal: {exc}")
    elif should_retrain and df_labeled.empty:
        print("[MLOps] Retrain diperlukan tapi tidak ada labeled data — dilewati")

    # ── STEP 6: Shadow scoring + evaluasi champion-challenger ─────
    print("\n[MLOps] Step 6/9 — Champion-Challenger evaluation...")
    challenger_path = get_challenger_path()
    promoted = False
    eval_result = {}

    if challenger_path and os.path.exists(challenger_path):
        # Hitung berapa hari challenger sudah shadow
        shadow_days = _count_shadow_days(engine)
        print(f"[MLOps] Challenger shadow days: {shadow_days} (min required: {SHADOW_DAYS_MIN})")

        # Shadow scoring menggunakan current_features (bukan df_labeled)
        # — kita perlu menscore kontrak aktif hari ini, bukan data labeled historis
        shadow_df = current_features if not current_features.empty else df_labeled
        if not shadow_df.empty and champion_path:
            try:
                shadow_scores = run_shadow_scoring(
                    shadow_df,
                    FEATURE_COLS,
                    champion_path,
                    challenger_path,
                    engine=engine,
                )
                print(f"[MLOps] Shadow scoring selesai: {len(shadow_scores):,} contracts")
            except Exception as exc:
                print(f"[MLOps] Shadow scoring gagal: {exc}")
                shadow_scores = pd.DataFrame()
        else:
            print("[MLOps] Shadow scoring dilewati: tidak ada data fitur tersedia")
            shadow_scores = pd.DataFrame()

        # Evaluasi hanya jika sudah >= SHADOW_DAYS_MIN
        if shadow_days >= SHADOW_DAYS_MIN:
            if not df_labeled.empty and not shadow_scores.empty:
                try:
                    eval_result = evaluate_champion_vs_challenger(df_labeled, shadow_scores)
                    print(f"[MLOps] Evaluation decision: {eval_result.get('decision')}")

                    if eval_result.get("decision") == "PROMOTE_CHALLENGER":
                        backup_path = promote_challenger(champion_path, challenger_path)
                        # Update registry dengan metadata challenger yang dipromote
                        register_model(
                            champion_path,
                            {
                                "strategy": "recency_weighted",
                                "auc": eval_result.get("challenger_auc"),
                                "evaluated_at": eval_result.get("evaluated_at"),
                                "promoted_from_challenger": challenger_path,
                            },
                            role="champion",
                        )
                        # Hapus file challenger setelah sukses dipromote
                        if os.path.exists(challenger_path):
                            os.remove(challenger_path)
                            print(f"[MLOps] Challenger file dihapus: {challenger_path}")
                        promoted = True
                        print("[MLOps] ✅ Challenger berhasil dipromote menjadi champion")
                    else:
                        print(
                            f"[MLOps] Champion dipertahankan "
                            f"(decision: {eval_result.get('decision')})"
                        )
                except Exception as exc:
                    print(f"[MLOps] Evaluasi champion-challenger gagal: {exc}")
            else:
                print("[MLOps] Evaluasi dilewati: labeled data atau shadow scores kosong")
        else:
            remaining = SHADOW_DAYS_MIN - shadow_days
            print(
                f"[MLOps] Evaluasi belum dilakukan — challenger perlu "
                f"{remaining} hari lagi di shadow mode"
            )
    else:
        print(
            f"[MLOps] Shadow evaluation dilewati "
            f"(challenger ada: {challenger_path is not None})"
        )

    # ── STEP 7/9: Sub-model champion-challenger evaluation ─────────
    print("\n[MLOps] Step 7/9 — Sub-model (self_cure/roll_forward/ptp_success) evaluation...")
    submodel_results = []
    for mtype in SUB_MODEL_TYPES:
        print(f"\n[MLOps:{mtype}] --------------------------------------------")
        submodel_results.append(
            _run_submodel_challenger_cycle(mtype, engine, df_labeled, current_features)
        )

    # ── STEP 8/9: Log ke model_monitoring_log ───────────────────────
    print("\n[MLOps] Step 8/9 — Logging run ke database...")
    # Ambil version champion aktif dari registry (model_type='recovery')
    try:
        registry = _load_registry()
        champ_entry = registry.get("model_types", {}).get("recovery", {}).get("current_champion") or {}
        champion_version = champ_entry.get("version")
    except Exception:
        champion_version = None

    notes_parts = []
    if should_retrain:
        if needs_retrain_perf:
            notes_parts.append(f"AUC={perf.get('auc')} < floor={AUC_FLOOR}")
        if needs_retrain_drift:
            notes_parts.append("drift critical")
    if promoted:
        notes_parts.append("challenger promoted")
    if not notes_parts:
        notes_parts.append("no action needed")

    log_monitoring_run(
        engine=engine,
        run_date=ref_date.date(),
        perf=perf,
        drift_results=drift_results,
        retrain_triggered=should_retrain and challenger_created,
        champion_version=champion_version,
        notes=" | ".join(notes_parts),
    )

    # ── STEP 8: Print ringkasan ────────────────────────────────────
    duration = (datetime.now() - start).total_seconds()
    print(f"\n[MLOps] Step 9/9 — Summary")
    print(f"{'=' * 72}")
    print(f"  Run date       : {ref_date.date()}")
    print(f"  New labels     : {len(new_labels):,}")
    print(f"  Model AUC      : {perf.get('auc', 'N/A')}")
    print(f"  Retrain needed : {should_retrain}")
    print(f"  Challenger     : {'created' if challenger_created else 'none'} (recovery)")
    print(f"  Promotion      : {'YES' if promoted else 'NO'} (recovery)")
    for r in submodel_results:
        print(
            f"  {r['model_type']:<13}: drift_retrain={r['needs_retrain_drift']} "
            f"promoted={r['promoted']}"
        )
    print(f"  Duration       : {duration:.1f}s")
    print(f"{'=' * 72}")

    if not should_retrain and not challenger_path and not any(r["promoted"] for r in submodel_results):
        print("[MLOps] ✅ No action needed — semua model stabil, tidak ada challenger aktif")

    for mtype in ["recovery"] + SUB_MODEL_TYPES:
        get_performance_history(model_type=mtype, last_n=5)
    print(f"{'=' * 72}\n")

    return {
        "performance": perf,
        "drift": drift_results,
        "needs_retrain": should_retrain,
        "challenger_created": challenger_created,
        "promoted": promoted,
        "submodels": submodel_results,
    }


if __name__ == "__main__":
    run_weekly_mlops()

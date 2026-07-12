"""Retraining strategies untuk CollectAI."""
from __future__ import annotations

from datetime import datetime
import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    XGB_N_ESTIMATORS,
    XGB_MAX_DEPTH,
    XGB_LEARNING_RATE,
    XGB_SUBSAMPLE,
    XGB_COLSAMPLE,
    XGB_MIN_CHILD_WEIGHT,
    XGB_GAMMA,
    XGB_REG_ALPHA,
    XGB_REG_LAMBDA,
    CV_N_SPLITS,
    MIN_CV_AUC_TO_DEPLOY,
)


def _prepare_xy(df_labeled: pd.DataFrame, feature_cols: list[str], target_col: str):
    df = df_labeled.copy()
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0).astype(int)
    return df, X, y


def _build_xgb(y_series: pd.Series):
    try:
        import xgboost as xgb
    except Exception as e:
        raise RuntimeError(
            "xgboost tidak bisa di-load. Pastikan dependency sistem terpasang (macOS: brew install libomp)."
        ) from e

    n_neg = int((y_series == 0).sum())
    n_pos = int((y_series == 1).sum())
    spw = n_neg / max(n_pos, 1)
    return xgb.XGBClassifier(
        n_estimators=XGB_N_ESTIMATORS,
        max_depth=XGB_MAX_DEPTH,
        learning_rate=XGB_LEARNING_RATE,
        subsample=XGB_SUBSAMPLE,
        colsample_bytree=XGB_COLSAMPLE,
        min_child_weight=XGB_MIN_CHILD_WEIGHT,
        gamma=XGB_GAMMA,
        reg_alpha=XGB_REG_ALPHA,
        reg_lambda=XGB_REG_LAMBDA,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=spw,
    )


def _cross_validate(model, X, y) -> float:
    cv = StratifiedKFold(n_splits=CV_N_SPLITS, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    return float(np.round(scores.mean(), 4))


def _raise_if_below_threshold(auc_value: float):
    if auc_value < MIN_CV_AUC_TO_DEPLOY:
        raise ValueError(
            f"AUC {auc_value:.4f} di bawah threshold {MIN_CV_AUC_TO_DEPLOY:.2f}"
        )


def strategy_full_retrain(df_labeled, feature_cols, target_col="actual_paid"):
    df, X, y = _prepare_xy(df_labeled, feature_cols, target_col)
    model = _build_xgb(y)
    cv_auc = _cross_validate(model, X, y)
    _raise_if_below_threshold(cv_auc)
    model.fit(X, y, verbose=False)
    return model, {
        "strategy": "full_retrain",
        "n_samples": int(len(df)),
        "auc": cv_auc,
        "trained_at": datetime.now().isoformat(),
    }


def strategy_rolling_window(df_labeled, feature_cols, target_col="actual_paid", months=6):
    df = df_labeled.copy()
    if "scoring_date" not in df.columns:
        raise ValueError("Kolom scoring_date wajib ada untuk rolling window")
    df["scoring_date"] = pd.to_datetime(df["scoring_date"], errors="coerce")
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=months)
    df_window = df[df["scoring_date"] >= cutoff].copy()
    if len(df_window) < 500:
        raise ValueError(f"Data rolling window kurang dari 500: {len(df_window)}")

    _, X, y = _prepare_xy(df_window, feature_cols, target_col)
    model = _build_xgb(y)
    cv_auc = _cross_validate(model, X, y)
    _raise_if_below_threshold(cv_auc)
    model.fit(X, y, verbose=False)

    return model, {
        "strategy": "rolling_window",
        "months": int(months),
        "n_samples": int(len(df_window)),
        "auc": cv_auc,
        "trained_at": datetime.now().isoformat(),
    }


def strategy_recency_weighted(
    df_labeled,
    feature_cols,
    target_col="actual_paid",
    decay_rate=0.70,
):
    df, X, y = _prepare_xy(df_labeled, feature_cols, target_col)
    if "scoring_date" not in df.columns:
        raise ValueError("Kolom scoring_date wajib ada untuk recency-weighted")
    df["scoring_date"] = pd.to_datetime(df["scoring_date"], errors="coerce")

    today = pd.Timestamp.today()
    df["months_ago"] = (
        (today.year - df["scoring_date"].dt.year) * 12
        + (today.month - df["scoring_date"].dt.month)
    ).clip(lower=0)
    w = (decay_rate ** df["months_ago"]).astype(float)

    model = _build_xgb(y)
    model.fit(X, y, sample_weight=w, verbose=False)

    recent = df[df["months_ago"] <= 1].copy()
    if len(recent) >= 100 and recent[target_col].nunique() > 1:
        y_recent = pd.to_numeric(recent[target_col], errors="coerce").fillna(0).astype(int)
        X_recent = recent[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        auc_val = float(np.round(roc_auc_score(y_recent, model.predict_proba(X_recent)[:, 1]), 4))
    else:
        # fallback agar tetap bisa dipakai di dataset kecil
        if y.nunique() > 1:
            auc_val = float(np.round(roc_auc_score(y, model.predict_proba(X)[:, 1]), 4))
        else:
            auc_val = 0.5

    _raise_if_below_threshold(auc_val)

    return model, {
        "strategy": "recency_weighted",
        "n_samples": int(len(df)),
        "auc": auc_val,
        "decay_rate": float(decay_rate),
        "trained_at": datetime.now().isoformat(),
    }

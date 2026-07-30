"""Retraining strategies untuk CollectAI."""
from __future__ import annotations

from datetime import datetime
import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, cross_val_score

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


def _cross_validate(model, X, y, groups=None) -> float:
    """Grouped CV when `groups` (typically cust_id) is available, so contracts
    belonging to the same customer never split across train/test — they share
    the same latent behavioural profile, so an ungrouped split would leak
    across folds and inflate the estimate. Falls back to a plain stratified
    split only when no grouping key was provided."""
    if groups is not None and pd.Series(groups).nunique() >= CV_N_SPLITS:
        cv = StratifiedGroupKFold(n_splits=CV_N_SPLITS, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y, cv=cv, groups=groups, scoring="roc_auc")
    else:
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
    groups = df["cust_id"] if "cust_id" in df.columns else None
    cv_auc = _cross_validate(model, X, y, groups=groups)
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

    df_window_prepared, X, y = _prepare_xy(df_window, feature_cols, target_col)
    model = _build_xgb(y)
    groups = df_window_prepared["cust_id"] if "cust_id" in df_window_prepared.columns else None
    cv_auc = _cross_validate(model, X, y, groups=groups)
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

    # AUC reporting: build_target_variable() assigns ONE constant scoring_date
    # to every row for initial training, so months_ago == 0 everywhere and the
    # old "recent = df[months_ago <= 1]" slice WAS the entire training set —
    # evaluating the just-fitted model on its own training rows, i.e. in-sample
    # AUC, not a generalization estimate. There is no second time point to hold
    # out here, so instead of a time-based split we report a proper grouped
    # cross-validated AUC (grouped by cust_id where available, so a customer's
    # contracts never span both sides of a fold) on a freshly-fit CV model,
    # while the returned `model` below is still fit on the full data with
    # recency weights for actual deployment.
    cv_model = _build_xgb(y)
    groups = df["cust_id"] if "cust_id" in df.columns else None
    if y.nunique() > 1:
        auc_val = _cross_validate(cv_model, X, y, groups=groups)
    else:
        auc_val = 0.5

    model = _build_xgb(y)
    model.fit(X, y, sample_weight=w, verbose=False)

    _raise_if_below_threshold(auc_val)

    return model, {
        "strategy": "recency_weighted",
        "n_samples": int(len(df)),
        "auc": auc_val,
        "decay_rate": float(decay_rate),
        "trained_at": datetime.now().isoformat(),
    }

"""Outcome labeler: build target variable dari payment history.

Untuk training awal: build_target_variable() — semua scoring date sama.
Untuk MLOps weekly: label_historical_scores() — append ke scoring_labels.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LABEL_WINDOW_DAYS


def _label_one_contract(contract_no, scoring_date, df_pay, window):
    """Return 1 jika ada Full/Partial payment dalam (scoring_date, scoring_date+window]."""
    sub = df_pay[df_pay["contract_no"] == contract_no]
    if sub.empty:
        return 0
    end = scoring_date + pd.Timedelta(days=window)
    mask = (
        sub["pay_status"].isin(["Full", "Partial"])
        & (sub["actual_pay_date"] > scoring_date)
        & (sub["actual_pay_date"] <= end)
    )
    return int(mask.any())


def build_target_variable(
    df_features: pd.DataFrame,
    df_payment: pd.DataFrame,
    scoring_date,
    n_days: int = LABEL_WINDOW_DAYS,
) -> pd.DataFrame:
    """Untuk training awal: scoring_date tunggal, label semua kontrak.

    Karena dataset historis kita tidak punya 'scoring_date' yang berbeda-beda,
    pendekatan yang dipakai: gunakan range tanggal pembayaran sebagai jendela
    backward-looking. Setiap kontrak dilabeli 1 jika ada Full/Partial payment
    dalam n_days hari terakhir sebelum scoring_date.
    """
    scoring_date = pd.Timestamp(scoring_date).normalize()
    p = df_payment.copy()
    p.columns = [c.lower() for c in p.columns]
    p["actual_pay_date"] = pd.to_datetime(p["actual_pay_date"], errors="coerce")
    p["pay_status"] = p["pay_status"].astype(str)

    start = scoring_date - pd.Timedelta(days=n_days)
    valid_pay = p[
        p["pay_status"].isin(["Full", "Partial"])
        & (p["actual_pay_date"] >= start)
        & (p["actual_pay_date"] <= scoring_date)
    ]
    paid_set = set(valid_pay["contract_no"].unique())

    out = df_features.copy()
    out["actual_paid"] = out["contract_no"].isin(paid_set).astype(int)
    out["scoring_date"] = scoring_date

    n = len(out)
    n_paid = int(out["actual_paid"].sum())
    rate = n_paid / n if n else 0.0
    print(
        f"[Labeler] training: n={n:,}, paid={n_paid:,} ({rate:.1%}), "
        f"unpaid={n - n_paid:,}"
    )
    return out


def label_historical_scores(
    df_ai_output: pd.DataFrame,
    df_payment: pd.DataFrame,
    engine=None,
    label_window: int = LABEL_WINDOW_DAYS,
) -> pd.DataFrame:
    """MLOps weekly: label scoring records yang sudah cukup tua.

    Hanya label records yang scoring_date <= today - label_window, dan
    yang belum ada di tabel scoring_labels.
    """
    today = pd.Timestamp.today().normalize()
    cutoff = today - pd.Timedelta(days=label_window)

    df = df_ai_output.copy()
    df.columns = [c.lower() for c in df.columns]
    df["scoring_date"] = pd.to_datetime(df["scoring_date"])
    to_label = df[df["scoring_date"] <= cutoff].copy()

    if to_label.empty:
        print("[Labeler] tidak ada records cukup tua untuk dilabeli")
        return pd.DataFrame()

    # Skip yang sudah ada di scoring_labels
    if engine is not None:
        try:
            existing = pd.read_sql(
                "SELECT contract_no, scoring_date FROM scoring_labels", engine
            )
            existing["scoring_date"] = pd.to_datetime(existing["scoring_date"])
            existing_keys = set(
                zip(existing["contract_no"], existing["scoring_date"].dt.date)
            )
            to_label = to_label[~to_label.apply(
                lambda r: (r["contract_no"], r["scoring_date"].date()) in existing_keys,
                axis=1,
            )]
        except Exception:
            pass

    if to_label.empty:
        print("[Labeler] semua records sudah dilabeli sebelumnya")
        return pd.DataFrame()

    p = df_payment.copy()
    p.columns = [c.lower() for c in p.columns]
    p["actual_pay_date"] = pd.to_datetime(p["actual_pay_date"], errors="coerce")
    p["pay_status"] = p["pay_status"].astype(str)

    to_label["actual_paid"] = to_label.apply(
        lambda r: _label_one_contract(
            r["contract_no"], r["scoring_date"], p, label_window
        ),
        axis=1,
    )
    to_label["labeled_date"] = today

    n = len(to_label)
    n_paid = int(to_label["actual_paid"].sum())
    print(f"[Labeler] {n:,} records baru dilabeli, paid={n_paid:,} ({n_paid/n:.1%})")

    if engine is not None:
        cols = [
            "contract_no", "cust_id", "scoring_date", "recovery_score",
            "risk_segment", "actual_paid", "labeled_date",
        ]
        to_label[cols].to_sql(
            "scoring_labels", engine, if_exists="append", index=False
        )

    return to_label

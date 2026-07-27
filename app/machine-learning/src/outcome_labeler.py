"""Outcome labeler: build target variable dari payment history.

Untuk training awal: build_target_variable() — semua scoring date sama.
Untuk MLOps weekly: label_historical_scores() — append ke scoring_labels.
Untuk restructuring (TASK-55): label_restructuring_outcomes() — append ke
restructuring_history, satu-satunya bahan baku training model acceptance
probability Fase 2.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import sys
import os
from sqlalchemy import text

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

    # 1. actual_self_cure
    def _label_self_cure(r):
        contract_no = r["contract_no"]
        scoring_date = r["scoring_date"]
        sub = p[p["contract_no"] == contract_no]
        if sub.empty:
            return 0
        end = scoring_date + pd.Timedelta(days=label_window)
        mask = (
            sub["pay_status"].isin(["Full", "Partial"])
            & (sub["actual_pay_date"] > scoring_date)
            & (sub["actual_pay_date"] <= end)
            & (sub.get("self_cure_flag", False) == True)
        )
        return int(mask.any())

    to_label["actual_self_cure"] = to_label.apply(_label_self_cure, axis=1)

    # 3. actual_ptp_kept
    # Load LKP from engine if possible
    df_lkp = pd.DataFrame()
    if engine is not None:
        try:
            df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", engine)
            df_lkp.columns = [c.lower() for c in df_lkp.columns]
        except Exception:
            pass

    if not df_lkp.empty and "ptp_status" in df_lkp.columns:
        ptp_kept_contracts = set(
            df_lkp[
                (df_lkp["result_code"] == "PTP") &
                (df_lkp["ptp_status"] == "KEPT")
            ]["contract_no"].unique()
        )
        to_label["actual_ptp_kept"] = to_label["contract_no"].isin(ptp_kept_contracts).astype(int)
    else:
        to_label["actual_ptp_kept"] = np.nan

    # 2. actual_roll_forward
    # Proxy: for now set to NaN as it requires next period snapshot. We'll populate if we can load it.
    to_label["actual_roll_forward"] = np.nan

    n = len(to_label)
    n_paid = int(to_label["actual_paid"].sum())
    print(f"[Labeler] {n:,} records baru dilabeli, paid={n_paid:,} ({n_paid/n:.1%})")

    if engine is not None:
        cols = [
            "contract_no", "cust_id", "scoring_date", "recovery_score",
            "risk_segment", "actual_paid", "labeled_date",
            "actual_self_cure", "actual_roll_forward", "actual_ptp_kept"
        ]
        to_label[cols].to_sql(
            "scoring_labels", engine, if_exists="append", index=False
        )

    return to_label


def get_labeled_dataset(engine) -> pd.DataFrame:
    """Ambil seluruh dataset labeled untuk monitoring dan retraining."""
    try:
        labeled = pd.read_sql("SELECT * FROM scoring_labels", engine)
    except Exception:
        return pd.DataFrame()

    labeled.columns = [c.lower() for c in labeled.columns]
    if labeled.empty:
        print("[Labeler] belum ada labeled dataset")
        return labeled

    print(f"[Labeler] {len(labeled):,} records labeled tersedia untuk MLOps")
    return labeled


def label_restructuring_outcomes(engine, reference_date=None) -> pd.DataFrame:
    """TASK-55 — Capture customer_response + post_restructure_dpd_30d/90d
    ke restructuring_history untuk tawaran yang statusnya sudah bergerak
    (ACCEPTED/REJECTED) — offer_status='GENERATED' berarti belum ada
    respons apapun, belum ada yang perlu dicatat.

    Idempotent: melewati (restructure_group_id, offered_date) yang sudah
    ada di restructuring_history.

    response_date dipakai untuk menandai kapan customer benar-benar
    merespons (diisi oleh backend saat endpoint customer-response dipanggil
    — lihat app/backend/services/restructuring_service.py). Fallback ke
    generated_date HANYA untuk baris lama yang belum punya response_date
    terisi (sebelum kolom ini ada).

    Keterbatasan jujur: post_restructure_dpd_30d/90d di sini adalah proxy
    dari DPD_CURRENT kontrak baru (new_contract_no) SAAT job ini jalan,
    bukan snapshot historis presisi di hari ke-30/90 — sistem ini hanya
    punya satu snapshot kontrak per waktu (bukan time series), sama seperti
    keterbatasan actual_roll_forward di label_historical_scores().
    """
    ref_date = pd.Timestamp(reference_date).normalize() if reference_date else pd.Timestamp.today().normalize()

    offers = pd.read_sql(
        "SELECT restructure_group_id, cust_id, offer_status, generated_date, response_date "
        "FROM restructuring_recommendation_output "
        "WHERE offer_status IN ('ACCEPTED', 'REJECTED')",
        engine,
    )
    if offers.empty:
        print("[Restructuring Labeler] Belum ada offer ACCEPTED/REJECTED untuk dilabeli")
        return pd.DataFrame()

    offers.columns = [c.lower() for c in offers.columns]
    offers["offered_date"] = pd.to_datetime(offers["generated_date"])
    offers["response_date"] = pd.to_datetime(offers["response_date"]).fillna(offers["offered_date"])

    existing = pd.read_sql(
        "SELECT restructure_group_id, offered_date FROM restructuring_history", engine
    )
    if not existing.empty:
        existing.columns = [c.lower() for c in existing.columns]
        existing["offered_date"] = pd.to_datetime(existing["offered_date"])
        existing_keys = set(zip(existing["restructure_group_id"], existing["offered_date"].dt.date))
        offers = offers[
            ~offers.apply(lambda r: (r["restructure_group_id"], r["offered_date"].date()) in existing_keys, axis=1)
        ]

    if offers.empty:
        print("[Restructuring Labeler] Semua offer ACCEPTED/REJECTED sudah dilabeli sebelumnya")
        return pd.DataFrame()

    group_map = pd.read_sql(
        text(
            "SELECT restructure_group_id, contract_no FROM restructuring_group_map "
            "WHERE restructure_group_id = ANY(:ids)"
        ),
        engine,
        params={"ids": offers["restructure_group_id"].tolist()},
    )
    group_map.columns = [c.lower() for c in group_map.columns]

    contracts = pd.read_sql("SELECT contract_no, new_contract_no, dpd_current FROM contract_snapshot", engine)
    contracts.columns = [c.lower() for c in contracts.columns]
    new_contract_lookup = contracts.set_index("contract_no")["new_contract_no"].to_dict()
    dpd_lookup = contracts.set_index("contract_no")["dpd_current"].to_dict()

    rows = []
    for _, offer_row in offers.iterrows():
        group_id = offer_row["restructure_group_id"]
        customer_response = "ACCEPTED" if offer_row["offer_status"] == "ACCEPTED" else "REJECTED"
        response_date = offer_row["response_date"]

        post_dpd_30 = None
        post_dpd_90 = None
        if customer_response == "ACCEPTED":
            member_contracts = group_map.loc[group_map["restructure_group_id"] == group_id, "contract_no"]
            new_contract_nos = [new_contract_lookup.get(c) for c in member_contracts if new_contract_lookup.get(c)]
            days_elapsed = (ref_date - response_date).days
            if new_contract_nos:
                current_dpd = dpd_lookup.get(new_contract_nos[0])
                if current_dpd is not None and days_elapsed >= 30:
                    post_dpd_30 = int(current_dpd)
                if current_dpd is not None and days_elapsed >= 90:
                    post_dpd_90 = int(current_dpd)

        rows.append({
            "restructure_group_id": group_id,
            "offered_date": offer_row["offered_date"].date(),
            "customer_response": customer_response,
            "response_date": response_date.date(),
            "post_restructure_dpd_30d": post_dpd_30,
            "post_restructure_dpd_90d": post_dpd_90,
        })

    result = pd.DataFrame(rows)
    result.to_sql("restructuring_history", engine, if_exists="append", index=False)
    print(f"[Restructuring Labeler] {len(result):,} baris baru ditambahkan ke restructuring_history")
    return result

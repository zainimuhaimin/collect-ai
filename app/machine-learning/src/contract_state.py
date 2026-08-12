"""Rekomputasi state kontrak (dpd/cycle/overdue/OTS) murni dari jadwal
cicilan + payment_history LIVE — dipakai simulasi hari-per-hari (TASK-S2,
post-presentation-review-tasks.md).

Sengaja TIDAK menyentuh latents tersembunyi faker (w/c) — sama seperti
kondisi produksi, satu-satunya input adalah riwayat transaksi yang benar-
benar "terjadi" (payment_history) dibandingkan jadwal yang seharusnya
(installment_schedule). Fungsi murni: menerima DataFrame, mengembalikan
DataFrame, tidak menyentuh DB — supaya mudah ditest tanpa Postgres (pola
sama seperti build_payload() di AI Reasoning).

Simplifikasi yang disengaja dibanding formula asli generator
(`assemble_contract_snapshot()`, faker/generate-faker-realistic.py:952-1000):
- `dpd_current` dihitung sebagai usia (hari) angsuran TERTUA yang belum
  lunas — definisi DPD baku, BUKAN formula `phase + 30*(whole_behind-1) -
  grace` milik generator (formula itu butuh `phase`/grace roll acak yang
  tidak seharusnya diketahui komponen ini).
- `cycle` diturunkan dari `overdue_installment_count` TANPA noise pergeseran
  7% yang ada di `_cycle_from_arrears()` — noise itu kosmetik, bukan bagian
  state yang bermakna untuk demo pergerakan.
- Bonus "catch-up" acak saat pembayaran penuh (tergantung `c`, latent
  tersembunyi) TIDAK direplikasi — `k_paid` dihitung langsung dari HITUNGAN
  angsuran lunas sampai `as_of_date`, bukan simulasi backlog bertahap.
Parity byte-identik dengan generator TIDAK diklaim dan TIDAK diperlukan —
ini derivasi baru untuk tujuan berbeda (replay incremental), bukan
pengganti drop-in generator asli.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CYCLE_BUCKET = {0: "C0", 1: "C1", 2: "C2", 3: "C3+"}


def _cycle_from_overdue_count(n) -> str:
    bucket = min(int(n), 3)
    return CYCLE_BUCKET[bucket]


def derive_contract_terms(contract_snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """Turunkan principal/monthly_rate/tenor dari kolom yang SUDAH ADA di
    contract_snapshot (loan_amount, installment_amount, interest_rate) —
    membalik formula anuitas yang dipakai generator saat origination
    (`build_contract_terms()`), TANPA menyentuh latents (w, c).

    loan_amount = tenor * installment (gross, lihat komentar di
    build_contract_terms) -> tenor = round(loan_amount / installment).
    installment = principal * r / (1 - (1+r)^-tenor)  ->  dibalik untuk
    principal.
    """
    df = contract_snapshot_df.copy()
    installment = pd.to_numeric(df["installment_amount"], errors="coerce")
    loan_amount = pd.to_numeric(df["loan_amount"], errors="coerce")
    tenor = (loan_amount / installment).round().fillna(1).clip(lower=1).astype(int)
    monthly_rate = pd.to_numeric(df["interest_rate"], errors="coerce").fillna(0.0) / 12.0

    r = monthly_rate.to_numpy(dtype=float)
    n = tenor.to_numpy(dtype=float)
    inst = installment.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        principal = np.where(
            r > 0,
            inst * (1 - (1 + r) ** (-n)) / r,
            inst * n,
        )

    return pd.DataFrame({
        "contract_no": df["contract_no"].values,
        "principal": principal,
        "monthly_rate": r,
        "tenor": tenor.values,
        "installment_amount": inst,
    })


def recompute_contract_state(
    as_of_date,
    schedule_df: pd.DataFrame,
    payment_history_df: pd.DataFrame,
    contract_terms_df: pd.DataFrame,
) -> pd.DataFrame:
    """Hitung ulang dpd_current/cycle/overdue_installment_count/prnc_ots/
    intr_ots per kontrak, sebagai fungsi (as_of_date, jadwal, payment_history
    LIVE yang sudah ter-suap sampai hari itu).

    ``schedule_df``: contract_no, installment_no, due_date, installment_amount
    (dari `stg_installment_schedule` / faker `--dump-schedule`).
    ``payment_history_df``: payment_history LIVE (contract_no, due_date,
    actual_pay_date, payment_amount, pay_status).
    ``contract_terms_df``: keluaran `derive_contract_terms()`.

    Return: DataFrame [contract_no, dpd_current, cycle,
    overdue_installment_count, prnc_ots, intr_ots, k_paid] — HANYA untuk
    kontrak yang punya jadwal due_date <= as_of_date (kontrak dengan
    seluruh jadwalnya di masa depan tidak dikembalikan; caller sebaiknya
    men-default-kan sisanya ke 0 overdue).
    """
    as_of_ts = pd.Timestamp(as_of_date)

    sched = schedule_df.copy()
    sched["due_date"] = pd.to_datetime(sched["due_date"])
    due = sched[sched["due_date"] <= as_of_ts][["contract_no", "installment_no", "due_date"]].copy()
    if due.empty:
        return pd.DataFrame(columns=[
            "contract_no", "dpd_current", "cycle", "overdue_installment_count",
            "prnc_ots", "intr_ots", "k_paid",
        ])

    pay = payment_history_df.copy()
    pay["due_date"] = pd.to_datetime(pay["due_date"])
    pay["actual_pay_date"] = pd.to_datetime(pay["actual_pay_date"])
    pay = pay[pay["actual_pay_date"] <= as_of_ts]
    paid_ok = (
        pay[pay["pay_status"].isin(["Full", "Overpaid"])][["contract_no", "due_date"]]
        .drop_duplicates()
    )
    paid_ok["_paid"] = True

    merged = due.merge(paid_ok, on=["contract_no", "due_date"], how="left")
    merged["_paid"] = merged["_paid"].fillna(False)

    grp = merged.groupby("contract_no")
    k_paid = grp["_paid"].sum().rename("k_paid")
    overdue_count = grp["_paid"].apply(lambda s: int((~s).sum())).rename("overdue_installment_count")
    oldest_unpaid_due = (
        merged.loc[~merged["_paid"]].groupby("contract_no")["due_date"].min().rename("oldest_unpaid_due")
    )

    state = pd.concat([k_paid, overdue_count], axis=1).reset_index()
    state = state.merge(oldest_unpaid_due.reset_index(), on="contract_no", how="left")
    state["dpd_current"] = (
        (as_of_ts - state["oldest_unpaid_due"]).dt.days.fillna(0).clip(lower=0).astype(int)
    )
    state["cycle"] = state["overdue_installment_count"].apply(_cycle_from_overdue_count)

    state = state.merge(contract_terms_df, on="contract_no", how="left")

    r = state["monthly_rate"].astype(float).to_numpy()
    tenor = state["tenor"].astype(float).to_numpy()
    kp = np.minimum(state["k_paid"].astype(float).to_numpy(), tenor)
    principal = state["principal"].astype(float).to_numpy()
    installment = state["installment_amount"].astype(float).to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        prnc_ots = np.where(
            (r > 0) & (kp < tenor),
            principal * (((1 + r) ** tenor - (1 + r) ** kp) / ((1 + r) ** tenor - 1)),
            np.maximum(0.0, principal * (1 - np.divide(kp, tenor, out=np.ones_like(tenor), where=tenor > 0))),
        )
    prnc_ots = np.maximum(0.0, prnc_ots)
    intr_ots = np.maximum(0.0, (tenor - kp) * installment - prnc_ots)

    state["prnc_ots"] = prnc_ots
    state["intr_ots"] = intr_ots

    return state[[
        "contract_no", "dpd_current", "cycle", "overdue_installment_count",
        "prnc_ots", "intr_ots", "k_paid",
    ]].copy()

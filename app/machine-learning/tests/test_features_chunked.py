"""Parity test — `compute_features_chunked_from_loader()` (TASK-P5 item 1,
dikerjakan di sesi lanjutan) HARUS menghasilkan angka BYTE-IDENTIK dengan
memanggil `compute_contract_features()`/`compute_customer_features()`
langsung pada dataset PENUH (fungsi asli, TIDAK diubah sama sekali).

Dataset sintetis di bawah sengaja mencakup kasus yang paling rawan pecah
kalau partisi per-batch salah:
- customer dengan >1 kontrak (delay_trend/channel_effectiveness/ptp_
  reliability_index HARUS menggabungkan seluruh kontrak customer itu)
- lineage restrukturisasi (new_contract_no menunjuk kontrak LAIN milik
  customer YANG SAMA — is_restructured harus tetap benar walau dipartisi)
- PTP dibuat lalu dibayar (kept) DAN PTP dibuat lalu tidak dibayar (broken)
- delay_trend lintas beberapa bulan (butuh >=2 titik bulan per customer)
- mode recovery_source dengan lebih dari satu nilai (tie-break harus sama
  persis karena baris yang sama selalu digroupby bersama, tidak terpecah
  lintas batch — batch key adalah cust_id, bukan payment_id)

Dijalankan dengan `batch_size=1` (setiap customer jadi batch terpisah — kasus
terburuk untuk pembagian) DAN `batch_size=100` (semua di satu batch — kasus
degenerate, harus tetap identik dengan tanpa-chunking sama sekali).
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.chunked_features import compute_features_chunked_from_loader  # noqa: E402
from src.feature_engineering import compute_contract_features, compute_customer_features  # noqa: E402

TODAY = pd.Timestamp.today().normalize()


def _contract_row(contract_no, cust_id, cycle="C1", dpd=10, prnc_ots=5_000_000, intr_ots=500_000,
                   loan_amount=10_000_000, installment_amount=1_000_000, maturity_days=180,
                   closed_via_restructure=False, new_contract_no=None):
    return {
        "contract_no": contract_no, "cust_id": cust_id, "cycle": cycle, "dpd_current": dpd,
        "prnc_ots": prnc_ots, "intr_ots": intr_ots, "loan_amount": loan_amount,
        "installment_amount": installment_amount,
        "maturity_date": TODAY + pd.Timedelta(days=maturity_days),
        "closed_via_restructure": closed_via_restructure, "new_contract_no": new_contract_no,
        "status": "aktif",
    }


def _payment_rows(contract_no, entries):
    """entries: list of (days_ago, status, delay_days, self_cure_flag, recovery_source)."""
    rows = []
    for i, (da, status, delay, sc, rs) in enumerate(entries):
        rows.append({
            "payment_id": f"PAY-{contract_no}-{i:03d}", "contract_no": contract_no,
            "actual_pay_date": TODAY - pd.Timedelta(days=da), "pay_status": status,
            "delay_days": delay, "self_cure_flag": sc, "recovery_source": rs,
        })
    return rows


def _lkp_rows(contract_no, entries):
    """entries: list of (action_days_ago, result_code, treatment_type, promise_days_from_now, ptp_status)."""
    rows = []
    for i, (da, code, treatment, promise_from_now, ptp_status) in enumerate(entries):
        rows.append({
            "lkp_id": f"LKP-{contract_no}-{i:03d}", "contract_no": contract_no,
            "action_date": TODAY - pd.Timedelta(days=da), "result_code": code,
            "treatment_type": treatment, "interaction_score": 3,
            "promise_date": (TODAY + pd.Timedelta(days=promise_from_now)) if promise_from_now is not None else pd.NaT,
            "ptp_status": ptp_status, "rpc_flag": 1 if code != "Tidak Bisa Dihubungi" else 0,
            "contact_success_flag": 1, "ptp_amount": 500_000 if code == "PTP" else 0,
        })
    return rows


def _build_dataset():
    contracts = [
        # CUST-A: 2 kontrak, salah satunya lineage restrukturisasi
        _contract_row("CTR-A-1", "CUST-A", cycle="C2", dpd=45),
        _contract_row("CTR-A-2", "CUST-A", cycle="C0", dpd=0, closed_via_restructure=True, new_contract_no="CTR-A-1"),
        # CUST-B: 1 kontrak, PTP kept
        _contract_row("CTR-B-1", "CUST-B", cycle="C1", dpd=15),
        # CUST-C: 1 kontrak, PTP broken + mode tie recovery_source
        _contract_row("CTR-C-1", "CUST-C", cycle="C3+", dpd=95),
        # CUST-D: 3 kontrak, delay_trend lintas bulan
        _contract_row("CTR-D-1", "CUST-D", cycle="C1", dpd=20),
        _contract_row("CTR-D-2", "CUST-D", cycle="C2", dpd=40),
        _contract_row("CTR-D-3", "CUST-D", cycle="C0", dpd=0),
        # CUST-E: tidak ada payment/lkp sama sekali (edge case kosong)
        _contract_row("CTR-E-1", "CUST-E", cycle="C0", dpd=0),
    ]
    df_contract = pd.DataFrame(contracts)

    payments = []
    payments += _payment_rows("CTR-A-1", [(10, "Full", 5, True, "WA"), (40, "Partial", 20, False, "Deskcoll")])
    payments += _payment_rows("CTR-B-1", [(3, "Full", 1, True, "WA")])
    payments += _payment_rows("CTR-C-1", [(60, "Partial", 30, False, "Visit")])
    # CUST-D: 3 bulan berturut, delay_days naik (trend positif) — 2 kontrak beda punya payment
    payments += _payment_rows("CTR-D-1", [(95, "Full", 2, True, "WA"), (65, "Full", 8, True, "WA"), (35, "Full", 15, True, "Deskcoll")])
    payments += _payment_rows("CTR-D-2", [(90, "Partial", 3, False, "WA")])
    # Mode tie: recovery_source WA vs Deskcoll masing-masing 1x untuk CTR-C-1 (ditambah 1 lagi)
    payments += _payment_rows("CTR-C-1", [(20, "Full", 4, False, "WA")])
    df_payment = pd.DataFrame(payments)

    lkps = []
    # CUST-B: PTP dibuat, dibayar dalam window (kept) — payment CTR-B-1 3 hari lalu,
    # promise_date 5 hari lalu (window PTP_DAYS_WINDOW=7 default settings)
    lkps += _lkp_rows("CTR-B-1", [(5, "PTP", "Deskcoll", -5 + 3, "KEPT")])
    # CUST-C: PTP dibuat, TIDAK dibayar dalam window (broken)
    lkps += _lkp_rows("CTR-C-1", [(30, "PTP", "Visit", -30 + 100, "BROKEN")])
    # CUST-A: rejection + bayar via lkp untuk channel_effectiveness
    lkps += _lkp_rows("CTR-A-1", [(12, "Bayar", "WA", None, None), (50, "Menolak", "Somasi", None, None)])
    lkps += _lkp_rows("CTR-D-1", [(90, "Bayar", "WA", None, None)])
    df_lkp = pd.DataFrame(lkps)

    df_customer = pd.DataFrame([
        {"cust_id": "CUST-A", "cust_income_level": "Mid", "cust_segment": "Medium Risk"},
        {"cust_id": "CUST-B", "cust_income_level": "Low", "cust_segment": "High Risk"},
        {"cust_id": "CUST-C", "cust_income_level": "High", "cust_segment": "Low Risk"},
        {"cust_id": "CUST-D", "cust_income_level": "Mid", "cust_segment": "Medium Risk"},
        {"cust_id": "CUST-E", "cust_income_level": "Mid", "cust_segment": "Medium Risk"},
    ])
    return df_contract, df_payment, df_lkp, df_customer


def _make_loader(df_payment, df_lkp):
    def _load(contract_nos):
        p = df_payment[df_payment["contract_no"].isin(contract_nos)].copy() if not df_payment.empty else df_payment.copy()
        l = df_lkp[df_lkp["contract_no"].isin(contract_nos)].copy() if not df_lkp.empty else df_lkp.copy()
        return p, l
    return _load


@pytest.mark.parametrize("batch_size", [1, 2, 100])
def test_chunked_parity_contract_features(batch_size):
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()

    cf_full = compute_contract_features(df_contract, df_payment, df_lkp, TODAY, df_customer=df_customer)
    cf_chunked, _ = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=batch_size,
    )

    cf_full_sorted = cf_full.sort_values("contract_no").reset_index(drop=True)
    cf_chunked_sorted = cf_chunked.sort_values("contract_no").reset_index(drop=True)
    pd.testing.assert_frame_equal(cf_full_sorted, cf_chunked_sorted, check_like=False)


@pytest.mark.parametrize("batch_size", [1, 2, 100])
def test_chunked_parity_customer_features(batch_size):
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()

    cf_full = compute_contract_features(df_contract, df_payment, df_lkp, TODAY, df_customer=df_customer)
    custf_full = compute_customer_features(
        df_contract, df_payment, df_lkp, df_customer, df_contract_features=cf_full,
    )
    _, custf_chunked = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=batch_size,
    )

    custf_full_sorted = custf_full.sort_values("cust_id").reset_index(drop=True)
    custf_chunked_sorted = custf_chunked.sort_values("cust_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(custf_full_sorted, custf_chunked_sorted, check_like=False)


def test_chunked_parity_with_feature_cutoff_date():
    """Jalur anti-leakage (training) — feature_cutoff_date juga harus identik."""
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()
    cutoff = TODAY - pd.Timedelta(days=15)

    cf_full = compute_contract_features(
        df_contract, df_payment, df_lkp, TODAY, df_customer=df_customer, feature_cutoff_date=cutoff,
    )
    cf_chunked, _ = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, feature_cutoff_date=cutoff, batch_size=2,
    )

    cf_full_sorted = cf_full.sort_values("contract_no").reset_index(drop=True)
    cf_chunked_sorted = cf_chunked.sort_values("contract_no").reset_index(drop=True)
    pd.testing.assert_frame_equal(cf_full_sorted, cf_chunked_sorted, check_like=False)


def test_chunked_handles_customer_with_no_payment_or_lkp():
    """CUST-E (CTR-E-1) tidak punya payment/lkp sama sekali — tidak boleh
    membuat batch itu error atau hilang dari hasil."""
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()
    cf_chunked, custf_chunked = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=1,
    )
    assert "CTR-E-1" in cf_chunked["contract_no"].values
    assert "CUST-E" in custf_chunked["cust_id"].values


def test_chunked_need_customer_features_false_skips_and_returns_none():
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()
    cf_chunked, custf_chunked = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=2, need_customer_features=False,
    )
    assert custf_chunked is None
    assert len(cf_chunked) == len(df_contract)


@pytest.mark.parametrize("batch_size", [1, 2, 100])
def test_chunked_parity_pass_customer_false(batch_size):
    """Kombinasi param yang dipakai daily_scoring.py/weekly_mlops.py/
    cbs_builder.py::update_cbs() — pass_customer_to_contract_features=False
    (BEDA dari train_*.py yang pakai True). Sebelumnya kombinasi ini hanya
    diverifikasi lewat parity gate manual pada data real (git stash+diff),
    tidak ada regression test permanen — celah ini ditutup di sini."""
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()

    cf_full = compute_contract_features(df_contract, df_payment, df_lkp, TODAY, df_customer=None)
    custf_full = compute_customer_features(
        df_contract, df_payment, df_lkp, df_customer, df_contract_features=cf_full,
    )
    cf_chunked, custf_chunked = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=batch_size,
        pass_customer_to_contract_features=False,
    )

    pd.testing.assert_frame_equal(
        cf_full.sort_values("contract_no").reset_index(drop=True),
        cf_chunked.sort_values("contract_no").reset_index(drop=True),
        check_like=False,
    )
    pd.testing.assert_frame_equal(
        custf_full.sort_values("cust_id").reset_index(drop=True),
        custf_chunked.sort_values("cust_id").reset_index(drop=True),
        check_like=False,
    )


def test_chunked_restructuring_lineage_preserved_within_batch():
    """CTR-A-2 (closed_via_restructure) -> new_contract_no=CTR-A-1, keduanya
    milik CUST-A yang sama — is_restructured pada CTR-A-1 harus tetap 1
    walau dipartisi (batch_size=1 memaksa SELURUH kontrak CUST-A tetap
    dalam SATU batch karena partisi per cust_id, bukan per contract_no)."""
    df_contract, df_payment, df_lkp, df_customer = _build_dataset()
    cf_chunked, _ = compute_features_chunked_from_loader(
        df_contract, df_customer, _make_loader(df_payment, df_lkp),
        reference_date=TODAY, batch_size=1,
    )
    row = cf_chunked[cf_chunked["contract_no"] == "CTR-A-1"].iloc[0]
    assert row["is_restructured"] == 1

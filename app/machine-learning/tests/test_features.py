"""Unit tests untuk Phase 2 — Feature Engineering.

Test coverage:
  - TASK-05: compute_contract_features
  - TASK-06: compute_customer_features
  - TASK-07: enrich_with_cbs

Jalankan:
    cd app/machine-learning
    pytest tests/test_features.py -v
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

# Tambah root ke sys.path agar import bekerja tanpa install package
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.feature_engineering import (
    compute_contract_features,
    compute_customer_features,
    enrich_with_cbs,
)
from config.settings import FEATURE_COLS


# ── HELPERS / FIXTURES ───────────────────────────────────────────────

def _make_contract(contract_no="C001", cust_id="CUST001", cycle="C1", dpd=10,
                   prnc_ots=5_000_000, intr_ots=500_000):
    return pd.DataFrame([{
        "contract_no": contract_no,
        "cust_id": cust_id,
        "cycle": cycle,
        "dpd_current": dpd,
        "prnc_ots": prnc_ots,
        "intr_ots": intr_ots,
    }])


def _make_payment(contract_no="C001", statuses=None, delay_days=None, days_ago=None):
    today = pd.Timestamp.today().normalize()
    if statuses is None:
        statuses = ["Full"]
    if delay_days is None:
        delay_days = [0] * len(statuses)
    if days_ago is None:
        days_ago = [10] * len(statuses)
    rows = []
    for i, (s, d, da) in enumerate(zip(statuses, delay_days, days_ago)):
        rows.append({
            "payment_id": f"P{i:03d}",
            "contract_no": contract_no,
            "actual_pay_date": today - pd.Timedelta(days=da),
            "pay_status": s,
            "delay_days": d,
        })
    return pd.DataFrame(rows)


def _make_lkp(contract_no="C001", result_codes=None, treatment_types=None,
              interaction_scores=None, action_days_ago=None, promise_days_from_now=None):
    today = pd.Timestamp.today().normalize()
    if result_codes is None:
        result_codes = ["PTP"]
    n = len(result_codes)
    if treatment_types is None:
        treatment_types = ["Deskcoll"] * n
    if interaction_scores is None:
        interaction_scores = [3] * n
    if action_days_ago is None:
        action_days_ago = list(range(1, n + 1))
    if promise_days_from_now is None:
        promise_days_from_now = [7] * n

    rows = []
    for i in range(n):
        rows.append({
            "lkp_id": f"L{i:03d}",
            "contract_no": contract_no,
            "action_date": today - pd.Timedelta(days=action_days_ago[i]),
            "promise_date": today + pd.Timedelta(days=promise_days_from_now[i]),
            "result_code": result_codes[i],
            "treatment_type": treatment_types[i],
            "interaction_score": interaction_scores[i],
        })
    return pd.DataFrame(rows)


def _make_customer(cust_id="CUST001", income_level="Mid", segment="Medium Risk"):
    return pd.DataFrame([{
        "cust_id": cust_id,
        "cust_income_level": income_level,
        "cust_segment": segment,
    }])


# ── TASK-05: Contract-level features ────────────────────────────────

class TestComputeContractFeatures:

    def test_payment_rate_full(self):
        """3 Full payments → payment_rate = 1.0."""
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full", "Full", "Full"], delay_days=[0, 0, 0])
        result = compute_contract_features(df_c, df_p, pd.DataFrame())
        assert float(result["payment_rate"].iloc[0]) == pytest.approx(1.0)

    def test_payment_rate_mixed(self):
        """1 Full + 1 Partial + 1 None (no pay) → rate = 1/3."""
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full", "Partial", "None"], delay_days=[0, 0, 0])
        result = compute_contract_features(df_c, df_p, pd.DataFrame())
        assert float(result["payment_rate"].iloc[0]) == pytest.approx(1 / 3, abs=0.01)

    def test_ptp_fulfillment_no_ptp(self):
        """Tidak ada PTP → ptp_fulfillment_rate = NaN."""
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full"])
        df_l = _make_lkp(result_codes=["Bayar"])
        result = compute_contract_features(df_c, df_p, df_l)
        assert pd.isna(result["ptp_fulfillment_rate"].iloc[0]), \
            "ptp_fulfillment_rate harus NULL jika total_ptp_made = 0"

    def test_ptp_fulfillment_kept(self):
        """PTP dibuat → ada payment dalam PTP_DAYS_WINDOW → kept = 1."""
        today = pd.Timestamp.today().normalize()
        df_c = _make_contract()
        df_l = pd.DataFrame([{
            "lkp_id": "L001",
            "contract_no": "C001",
            "action_date": today - pd.Timedelta(days=2),
            "promise_date": today + pd.Timedelta(days=5),
            "result_code": "PTP",
            "treatment_type": "Deskcoll",
            "interaction_score": 3,
        }])
        # Payment terjadi tepat pada promise date
        df_p = pd.DataFrame([{
            "payment_id": "P001",
            "contract_no": "C001",
            "actual_pay_date": today + pd.Timedelta(days=5),
            "pay_status": "Full",
            "delay_days": 0,
        }])
        result = compute_contract_features(df_c, df_p, df_l)
        assert result["total_ptp_made"].iloc[0] == 1
        assert result["total_ptp_kept"].iloc[0] == 1
        assert result["ptp_fulfillment_rate"].iloc[0] == pytest.approx(1.0)

    def test_ptp_fulfillment_broken(self):
        """PTP dibuat → tidak ada payment dalam window → kept = 0."""
        today = pd.Timestamp.today().normalize()
        df_c = _make_contract()
        df_l = pd.DataFrame([{
            "lkp_id": "L001",
            "contract_no": "C001",
            "action_date": today - pd.Timedelta(days=30),
            "promise_date": today - pd.Timedelta(days=25),  # promise sudah lewat
            "result_code": "PTP",
            "treatment_type": "Deskcoll",
            "interaction_score": 2,
        }])
        df_p = pd.DataFrame(columns=["payment_id", "contract_no", "actual_pay_date",
                                     "pay_status", "delay_days"])
        result = compute_contract_features(df_c, df_p, df_l)
        assert result["total_ptp_made"].iloc[0] == 1
        assert result["total_ptp_kept"].iloc[0] == 0
        assert result["ptp_fulfillment_rate"].iloc[0] == pytest.approx(0.0)

    def test_cycle_encoding(self):
        """C0→0, C1→1, C2→2, C3→3."""
        for cycle, expected in [("C0", 0), ("C1", 1), ("C2", 2), ("C3", 3), ("C3+", 3)]:
            df_c = _make_contract(cycle=cycle)
            result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
            assert result["cycle_encoded"].iloc[0] == expected, \
                f"cycle {cycle} harus encoded {expected}"

    def test_last_result_code_encoded_range(self):
        """last_result_code_encoded harus 0–4 untuk setiap result code."""
        result_map = {
            "Bayar": 4, "PTP": 3, "Rumah Kosong": 2,
            "Tidak Bisa": 1, "Menolak": 0
        }
        for code, expected_enc in result_map.items():
            df_c = _make_contract()
            df_l = _make_lkp(result_codes=[code])
            result = compute_contract_features(df_c, pd.DataFrame(), df_l)
            assert result["last_result_code_encoded"].iloc[0] == expected_enc, \
                f"result_code '{code}' harus encoded {expected_enc}"

    def test_no_payment_no_lkp_defaults(self):
        """Tanpa payment & LKP, kolom numerik harus ada dengan nilai default."""
        df_c = _make_contract()
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert result["payment_count"].iloc[0] == 0
        assert result["rejection_count"].iloc[0] == 0
        assert result["treatment_count"].iloc[0] == 0
        assert result["total_ptp_made"].iloc[0] == 0

    def test_all_required_columns_present(self):
        """Semua 13+ fitur harus hadir di output."""
        required = [
            "dpd_current", "cycle_encoded", "total_ots", "payment_rate",
            "partial_rate", "avg_delay_days", "days_since_last_pay",
            "ptp_fulfillment_rate", "avg_interaction_score",
            "last_result_code_encoded", "treatment_count",
            "rejection_count", "payment_count",
        ]
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full"])
        df_l = _make_lkp(result_codes=["Bayar"])
        result = compute_contract_features(df_c, df_p, df_l)
        for col in required:
            assert col in result.columns, f"Kolom '{col}' hilang dari output"


# ── TASK-06: Customer-level features ────────────────────────────────

class TestComputeCustomerFeatures:

    def _make_3_contracts(self):
        """1 nasabah dengan 3 kontrak aktif."""
        return pd.DataFrame([
            {"contract_no": "C001", "cust_id": "CUST001", "cycle": "C1",
             "dpd_current": 5, "prnc_ots": 3_000_000, "intr_ots": 200_000, "status": "Aktif"},
            {"contract_no": "C002", "cust_id": "CUST001", "cycle": "C2",
             "dpd_current": 15, "prnc_ots": 4_000_000, "intr_ots": 300_000, "status": "Aktif"},
            {"contract_no": "C003", "cust_id": "CUST001", "cycle": "C1",
             "dpd_current": 8, "prnc_ots": 2_000_000, "intr_ots": 100_000, "status": "Aktif"},
        ])

    def test_customer_multi_contract_count(self):
        """1 nasabah dengan 3 kontrak aktif → active_contract_count = 3."""
        df_c = self._make_3_contracts()
        df_cust = _make_customer()
        result = compute_customer_features(df_c, pd.DataFrame(), pd.DataFrame(), df_cust)
        row = result[result["cust_id"] == "CUST001"].iloc[0]
        assert row["active_contract_count"] == 3

    def test_customer_total_active_ots(self):
        """total_active_ots = SUM of prnc_ots + intr_ots across active contracts."""
        df_c = self._make_3_contracts()
        df_cust = _make_customer()
        result = compute_customer_features(df_c, pd.DataFrame(), pd.DataFrame(), df_cust)
        row = result[result["cust_id"] == "CUST001"].iloc[0]
        expected_ots = (3_000_000 + 200_000) + (4_000_000 + 300_000) + (2_000_000 + 100_000)
        assert row["total_active_ots"] == pytest.approx(expected_ots)

    def test_delay_trend_worsening(self):
        """Delay naik setiap bulan → delay_trend > 0."""
        today = pd.Timestamp.today().normalize()
        payments = []
        for i, delay in enumerate([30, 25, 20, 15, 10, 5]):
            date_ = today - pd.DateOffset(months=i)
            payments.append({
                "payment_id": f"P{i:03d}",
                "contract_no": "C001",
                "actual_pay_date": date_,
                "pay_status": "Full",
                "delay_days": delay,
            })
        df_p = pd.DataFrame(payments)
        df_c = _make_contract()
        df_cust = _make_customer()
        result = compute_customer_features(df_c, df_p, pd.DataFrame(), df_cust)
        row = result[result["cust_id"] == "CUST001"].iloc[0]
        assert row["delay_trend"] > 0, \
            f"delay_trend harus positif (memburuk), dapat {row['delay_trend']}"

    def test_ptp_reliability_index_null_if_no_ptp(self):
        """Jika tidak ada PTP sama sekali → ptp_reliability_index harus NaN."""
        df_c = _make_contract()
        df_l = _make_lkp(result_codes=["Bayar"])  # tidak ada PTP
        df_cust = _make_customer()
        result = compute_customer_features(df_c, pd.DataFrame(), df_l, df_cust)
        row = result[result["cust_id"] == "CUST001"].iloc[0]
        assert pd.isna(row["ptp_reliability_index"]), \
            "ptp_reliability_index harus NULL jika tidak ada PTP"

    def test_composite_behavioral_score_in_range(self):
        """composite_behavioral_score harus dalam [0.0, 1.0]."""
        df_c = self._make_3_contracts()
        df_p = _make_payment(statuses=["Full", "Full"], delay_days=[5, 5])
        df_cust = _make_customer()
        result = compute_customer_features(df_c, df_p, pd.DataFrame(), df_cust)
        for score in result["composite_behavioral_score"]:
            assert 0.0 <= score <= 1.0, f"composite_behavioral_score={score} di luar [0,1]"


# ── TASK-07: Enrichment with CBS ────────────────────────────────────

class TestEnrichWithCbs:

    def _make_cbs_df(self, cust_id="CUST001", grade="B", b_list="N"):
        return pd.DataFrame([{
            "cust_id": cust_id,
            "ptp_reliability_index": 0.75,
            "delay_trend": -0.5,
            "historical_default_count": 0,
            "income_debt_ratio": 1.2,
            "active_contract_count": 1,
            "total_active_ots": 5_000_000,
            "behavioral_grade": grade,
            "b_list_status": b_list,
        }])

    def test_enrichment_no_cbs(self):
        """Kontrak baru tanpa CBS → tidak error, output punya 1 baris."""
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full"])
        cf = compute_contract_features(df_c, df_p, pd.DataFrame())

        # CBS kosong → LEFT JOIN akan produce NaN untuk semua CBS cols
        df_cbs = pd.DataFrame(columns=["cust_id", "behavioral_grade", "b_list_status"])
        result = enrich_with_cbs(cf, df_cbs)
        assert len(result) == 1  # tidak error
        assert result["contract_no"].iloc[0] == "C001"

    def test_enrichment_behavioral_grade_encoded(self):
        """behavioral_grade_encoded harus sesuai map (A=3, B=2, C=1, D=0)."""
        df_c = _make_contract()
        cf = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        for grade, expected_enc in [("A", 3), ("B", 2), ("C", 1), ("D", 0)]:
            df_cbs = self._make_cbs_df(grade=grade)
            result = enrich_with_cbs(cf, df_cbs)
            assert result["behavioral_grade_encoded"].iloc[0] == expected_enc, \
                f"Grade '{grade}' harus encoded {expected_enc}"

    def test_enrichment_b_list_flag(self):
        """b_list_status 'Y' → b_list_flag = 1, 'N' → 0."""
        df_c = _make_contract()
        cf = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())

        df_cbs_y = self._make_cbs_df(b_list="Y")
        result_y = enrich_with_cbs(cf, df_cbs_y)
        assert result_y["b_list_flag"].iloc[0] == 1

        df_cbs_n = self._make_cbs_df(b_list="N")
        result_n = enrich_with_cbs(cf, df_cbs_n)
        assert result_n["b_list_flag"].iloc[0] == 0

    def test_enrichment_no_duplicates(self):
        """Tidak ada duplikat CONTRACT_NO di output enrichment."""
        df_c = pd.DataFrame([
            {"contract_no": "C001", "cust_id": "CUST001", "cycle": "C1",
             "dpd_current": 5, "prnc_ots": 1e6, "intr_ots": 1e5},
            {"contract_no": "C002", "cust_id": "CUST001", "cycle": "C2",
             "dpd_current": 15, "prnc_ots": 2e6, "intr_ots": 2e5},
        ])
        cf = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        df_cbs = self._make_cbs_df()
        result = enrich_with_cbs(cf, df_cbs)
        assert result["contract_no"].duplicated().sum() == 0

    def test_enrichment_all_feature_cols_present(self):
        """Semua kolom dari FEATURE_COLS harus hadir di output enrichment."""
        df_c = _make_contract()
        df_p = _make_payment(statuses=["Full"])
        df_l = _make_lkp(result_codes=["PTP"])
        cf = compute_contract_features(df_c, df_p, df_l)
        df_cbs = self._make_cbs_df()
        result = enrich_with_cbs(cf, df_cbs)
        for col in FEATURE_COLS:
            assert col in result.columns, f"Kolom '{col}' dari FEATURE_COLS hilang di output"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ── TASK-33/34/35: New Features ──────────────────────────────────────

class TestNewContractFeatures:
    """Tests untuk fitur baru TASK-33, TASK-34, TASK-35."""

    def _base_contract(self, prev_cycle="C1", cycle="C2", loan_amount=100_000_000,
                        prnc_ots=30_000_000, intr_ots=0, maturity_date=None):
        today = pd.Timestamp.today().normalize()
        if maturity_date is None:
            maturity_date = (today + pd.Timedelta(days=200)).strftime("%Y-%m-%d")
        return pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "cycle": cycle,
            "dpd_current": 5,
            "prnc_ots": prnc_ots,
            "intr_ots": intr_ots,
            "prev_cycle": prev_cycle,
            "loan_amount": loan_amount,
            "installment_amount": 2_000_000,
            "maturity_date": maturity_date,
        }])

    def test_cycle_direction_worsening(self):
        """C1 → C2: cycle_direction = +1 (makin parah)."""
        df_c = self._base_contract(prev_cycle="C1", cycle="C2")
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert int(result["cycle_direction"].iloc[0]) == 1

    def test_cycle_direction_improving(self):
        """C2 → C1: cycle_direction = -1 (membaik)."""
        df_c = self._base_contract(prev_cycle="C2", cycle="C1")
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert int(result["cycle_direction"].iloc[0]) == -1

    def test_days_to_maturity_positive(self):
        """Maturity di masa depan → days_to_maturity > 0."""
        today = pd.Timestamp.today().normalize()
        future = (today + pd.Timedelta(days=90)).strftime("%Y-%m-%d")
        df_c = self._base_contract(maturity_date=future)
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert result["days_to_maturity"].iloc[0] > 0

    def test_days_to_maturity_past(self):
        """Maturity sudah lewat → di-clip ke 0."""
        past = "2020-01-01"
        df_c = self._base_contract(maturity_date=past)
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert int(result["days_to_maturity"].iloc[0]) == 0

    def test_rpc_rate_calculation(self):
        """3 dari 5 LKP berhasil RPC → rpc_rate = 0.6."""
        df_c = self._base_contract()
        today = pd.Timestamp.today().normalize()
        rows = []
        for i in range(5):
            rows.append({
                "lkp_id": f"L{i:03d}",
                "contract_no": "C999",
                "action_date": today - pd.Timedelta(days=i + 1),
                "promise_date": today + pd.Timedelta(days=7),
                "result_code": "Bayar",
                "treatment_type": "Deskcoll",
                "interaction_score": 3,
                "rpc_flag": (i < 3),  # 3 True, 2 False
            })
        df_l = pd.DataFrame(rows)
        result = compute_contract_features(df_c, pd.DataFrame(), df_l)
        assert float(result["rpc_rate"].iloc[0]) == pytest.approx(0.6, abs=0.01)

    def test_ptp_status_direct(self):
        """PTP_STATUS='BROKEN' di LKP langsung terhitung di ptp_fulfillment_rate
        tanpa perlu mencocokkan payment window."""
        df_c = self._base_contract()
        today = pd.Timestamp.today().normalize()
        # 1 PTP OPEN, 1 PTP BROKEN → total_ptp_made = 2 (dari result_code)
        # PTP kept dihitung dari payment window, bukan ptp_status
        # → test ini memastikan open_ptp_count terhitung dari ptp_status
        df_l = pd.DataFrame([
            {
                "lkp_id": "L001",
                "contract_no": "C999",
                "action_date": today - pd.Timedelta(days=3),
                "promise_date": today + pd.Timedelta(days=4),
                "result_code": "PTP",
                "treatment_type": "Deskcoll",
                "interaction_score": 3,
                "ptp_status": "OPEN",
            },
            {
                "lkp_id": "L002",
                "contract_no": "C999",
                "action_date": today - pd.Timedelta(days=10),
                "promise_date": today - pd.Timedelta(days=3),
                "result_code": "PTP",
                "treatment_type": "Deskcoll",
                "interaction_score": 3,
                "ptp_status": "BROKEN",
            },
        ])
        result = compute_contract_features(df_c, pd.DataFrame(), df_l)
        # open_ptp_count harus = 1 (hanya yang OPEN)
        assert int(result["open_ptp_count"].iloc[0]) == 1
        # total_ptp_made = 2 (kedua result_code = PTP)
        assert int(result["total_ptp_made"].iloc[0]) == 2

    def test_self_cure_rate(self):
        """2 dari 3 payment punya self_cure_flag=True → self_cure_rate ≈ 0.667."""
        df_c = self._base_contract()
        today = pd.Timestamp.today().normalize()
        df_p = pd.DataFrame([
            {"payment_id": "P001", "contract_no": "C999",
             "actual_pay_date": today - pd.Timedelta(days=30),
             "pay_status": "Full", "delay_days": 0, "self_cure_flag": True},
            {"payment_id": "P002", "contract_no": "C999",
             "actual_pay_date": today - pd.Timedelta(days=60),
             "pay_status": "Full", "delay_days": 0, "self_cure_flag": True},
            {"payment_id": "P003", "contract_no": "C999",
             "actual_pay_date": today - pd.Timedelta(days=90),
             "pay_status": "Partial", "delay_days": 5, "self_cure_flag": False},
        ])
        result = compute_contract_features(df_c, df_p, pd.DataFrame())
        assert float(result["self_cure_rate"].iloc[0]) == pytest.approx(2/3, abs=0.01)

    def test_recovery_ratio(self):
        """loan=100jt, total_ots=30jt → recovery_ratio = (100-30)/100 = 0.70."""
        df_c = self._base_contract(loan_amount=100_000_000, prnc_ots=30_000_000, intr_ots=0)
        result = compute_contract_features(df_c, pd.DataFrame(), pd.DataFrame())
        assert float(result["recovery_ratio"].iloc[0]) == pytest.approx(0.70, abs=0.01)

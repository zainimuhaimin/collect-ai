"""Unit tests untuk Phase 3 — Customer Behavioral Standing (CBS).

Test coverage:
  - TASK-09: build_cbs (business rules)
  - TASK-11: CBS rules verification

Jalankan:
    cd app/machine-learning
    pytest tests/test_cbs.py -v
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.cbs_builder import build_cbs


# ── HELPERS ──────────────────────────────────────────────────────────

def _make_customer_features(
    cust_id="CUST001",
    composite_score=0.75,
    broken_ptp_count=0,
    historical_default_count=0,
    ptp_reliability_index=None,
    sum_ptp_made=0,
    active_contract_count=1,
    total_active_ots=5_000_000,
    channel_effectiveness=None,
    cust_segment="Medium Risk",
    avg_payment_rate=0.8,
    avg_delay_days_cust=10.0,
    avg_interaction_score_cust=3.0,
    delay_trend=0.0,
    income_debt_ratio=1.0,
    sum_ptp_kept=0,
):
    return pd.DataFrame([{
        "cust_id": cust_id,
        "composite_behavioral_score": composite_score,
        "broken_ptp_count": broken_ptp_count,
        "historical_default_count": historical_default_count,
        "ptp_reliability_index": ptp_reliability_index,
        "sum_ptp_made": sum_ptp_made,
        "sum_ptp_kept": sum_ptp_kept,
        "active_contract_count": active_contract_count,
        "total_active_ots": total_active_ots,
        "channel_effectiveness": channel_effectiveness,
        "cust_segment": cust_segment,
        "avg_payment_rate": avg_payment_rate,
        "avg_delay_days_cust": avg_delay_days_cust,
        "avg_interaction_score_cust": avg_interaction_score_cust,
        "delay_trend": delay_trend,
        "income_debt_ratio": income_debt_ratio,
    }])


# ── TESTS ────────────────────────────────────────────────────────────

class TestBuildCbs:

    def test_grade_a(self):
        """composite_score = 0.85 → behavioral_grade = A."""
        df = _make_customer_features(composite_score=0.85)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "A"

    def test_grade_b(self):
        """composite_score = 0.65 → behavioral_grade = B."""
        df = _make_customer_features(composite_score=0.65)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "B"

    def test_grade_c(self):
        """composite_score = 0.50 → behavioral_grade = C."""
        df = _make_customer_features(composite_score=0.50)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "C"

    def test_grade_d(self):
        """composite_score = 0.30 → behavioral_grade = D."""
        df = _make_customer_features(composite_score=0.30)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "D"

    def test_grade_d_override_broken_ptp(self):
        """Score = 0.75 tapi broken_ptp = 6 → Grade D (override)."""
        df = _make_customer_features(composite_score=0.75, broken_ptp_count=6)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "D", \
            "Grade harus di-override ke D karena broken_ptp >= 5"

    def test_grade_d_override_historical_default(self):
        """Score = 0.80 tapi historical_default = 3 → Grade D (override)."""
        df = _make_customer_features(composite_score=0.80, historical_default_count=3)
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "D"

    def test_grade_d_override_low_ptp_reliability(self):
        """ptp_reliability < 0.10 dan sum_ptp_made >= 3 → Grade D (override)."""
        df = _make_customer_features(
            composite_score=0.75,
            ptp_reliability_index=0.05,
            sum_ptp_made=5,
        )
        result = build_cbs(df)
        assert result["behavioral_grade"].iloc[0] == "D"

    def test_blist_is_y_when_grade_d(self):
        """Grade D → B_LIST_STATUS = Y."""
        df = _make_customer_features(composite_score=0.20)  # Grade D
        result = build_cbs(df)
        assert result["b_list_status"].iloc[0] == "Y"

    def test_blist_is_n_when_grade_b(self):
        """Grade B, no blacklist conditions → B_LIST_STATUS = N."""
        df = _make_customer_features(composite_score=0.65)
        result = build_cbs(df)
        assert result["b_list_status"].iloc[0] == "N"

    def test_blist_from_broken_ptp(self):
        """broken_ptp >= 5 → B_LIST_STATUS = Y meski grade tidak D."""
        df = _make_customer_features(composite_score=0.70, broken_ptp_count=5)
        result = build_cbs(df)
        assert result["b_list_status"].iloc[0] == "Y"

    def test_recovery_effort_high_grade_d(self):
        """Grade D → recovery_effort_level = High."""
        df = _make_customer_features(composite_score=0.20)
        result = build_cbs(df)
        assert result["recovery_effort_level"].iloc[0] == "High"

    def test_recovery_effort_low_grade_a(self):
        """Grade A → recovery_effort_level = Low."""
        df = _make_customer_features(composite_score=0.85)
        result = build_cbs(df)
        assert result["recovery_effort_level"].iloc[0] == "Low"

    def test_recovery_effort_mid_grade_b(self):
        """Grade B, single contract → recovery_effort_level = Mid."""
        df = _make_customer_features(composite_score=0.65, active_contract_count=1)
        result = build_cbs(df)
        assert result["recovery_effort_level"].iloc[0] == "Mid"

    def test_recovery_effort_high_multicontract(self):
        """Grade B + 3 kontrak aktif → recovery_effort_level = High."""
        df = _make_customer_features(composite_score=0.65, active_contract_count=3)
        result = build_cbs(df)
        assert result["recovery_effort_level"].iloc[0] == "High"

    def test_ptp_index_null_when_no_ptp(self):
        """Belum pernah ada PTP → ptp_reliability_index = NULL (NaN)."""
        df = _make_customer_features(ptp_reliability_index=None, sum_ptp_made=0)
        result = build_cbs(df)
        assert pd.isna(result["ptp_reliability_index"].iloc[0]), \
            "ptp_reliability_index harus NULL jika belum ada PTP"

    def test_behavioral_grade_never_null(self):
        """behavioral_grade selalu A, B, C, atau D — tidak pernah NULL."""
        for score in [0.0, 0.39, 0.40, 0.59, 0.60, 0.79, 0.80, 1.0]:
            df = _make_customer_features(composite_score=score)
            result = build_cbs(df)
            grade = result["behavioral_grade"].iloc[0]
            assert grade in {"A", "B", "C", "D"}, \
                f"Grade {grade!r} tidak valid untuk score={score}"

    def test_b_list_never_null(self):
        """b_list_status selalu 'Y' atau 'N' — tidak pernah NULL."""
        for score in [0.0, 0.5, 1.0]:
            df = _make_customer_features(composite_score=score)
            result = build_cbs(df)
            b_list = result["b_list_status"].iloc[0]
            assert b_list in {"Y", "N"}, \
                f"B_LIST_STATUS {b_list!r} tidak valid"

    def test_output_columns(self):
        """Output CBS harus punya semua kolom yang diperlukan."""
        expected_cols = {
            "cust_id", "active_contract_count", "total_active_ots",
            "behavioral_grade", "recovery_effort_level",
            "ptp_reliability_index", "collection_sensitivity",
            "b_list_status", "update_timestamp",
        }
        df = _make_customer_features()
        result = build_cbs(df)
        missing = expected_cols - set(result.columns)
        assert not missing, f"Kolom CBS yang hilang: {missing}"

    def test_collection_sensitivity_from_channel(self):
        """collection_sensitivity diambil dari channel_effectiveness jika tidak NULL."""
        df = _make_customer_features(channel_effectiveness="Visit")
        result = build_cbs(df)
        assert result["collection_sensitivity"].iloc[0] == "Visit"

    def test_collection_sensitivity_fallback_segment(self):
        """Jika channel_effectiveness NULL, fallback ke default segment."""
        df = _make_customer_features(channel_effectiveness=None, cust_segment="High Risk")
        result = build_cbs(df)
        # High Risk → Visit (berdasarkan SEGMENT_DEFAULT_CHANNEL di cbs_builder)
        assert result["collection_sensitivity"].iloc[0] == "Visit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

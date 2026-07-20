"""Unit tests untuk Phase 5 — Business Rules & Scoring Engine.

Test coverage:
  - TASK-16/17: score_contracts, compute_confidence_level
  - TASK-18: apply_risk_segment, apply_nba, apply_priority
  - TASK-19: run_quality_check

Jalankan:
    cd app/machine-learning
    pytest tests/test_rules.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.business_rules import apply_risk_segment, apply_nba, apply_priority
from src.scoring_engine import compute_confidence_level, run_quality_check


# ── HELPERS ──────────────────────────────────────────────────────────

def _base_df(
    contract_no="C001",
    cust_id="CUST001",
    recovery_score=0.5,
    rejection_count=0,
    last_result_code_encoded=3,
    broken_ptp_count=0,
    income_debt_ratio=1.0,
    dpd_current=5,
    payment_rate=0.8,
    cycle_encoded=1,
    total_ots=5_000_000,
    historical_default_count=0,
    payment_count=3,
    treatment_count=3,
    ptp_fulfillment_rate=0.5,
    avg_delay_days=10.0,
    avg_interaction_score=3.0,
    ptp_reliability_index=0.7,
):
    return pd.DataFrame([{
        "contract_no": contract_no,
        "cust_id": cust_id,
        "recovery_score": recovery_score,
        "rejection_count": rejection_count,
        "last_result_code_encoded": last_result_code_encoded,
        "broken_ptp_count": broken_ptp_count,
        "income_debt_ratio": income_debt_ratio,
        "dpd_current": dpd_current,
        "payment_rate": payment_rate,
        "cycle_encoded": cycle_encoded,
        "total_ots": total_ots,
        "historical_default_count": historical_default_count,
        "payment_count": payment_count,
        "treatment_count": treatment_count,
        "ptp_fulfillment_rate": ptp_fulfillment_rate,
        "avg_delay_days": avg_delay_days,
        "avg_interaction_score": avg_interaction_score,
        "ptp_reliability_index": ptp_reliability_index,
    }])


# ── RISK SEGMENT TESTS ────────────────────────────────────────────────

class TestApplyRiskSegment:

    def test_wont_pay_low_score_high_rejection(self):
        """score < 0.30 AND rejection >= 2 → Won't Pay."""
        df = _base_df(recovery_score=0.20, rejection_count=2)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Won't Pay"

    def test_wont_pay_low_score_low_result_code(self):
        """score < 0.30 AND last_result <= 1 → Won't Pay."""
        df = _base_df(recovery_score=0.25, last_result_code_encoded=1, rejection_count=0)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Won't Pay"

    def test_cannot_pay_mid_score_broken_ptp(self):
        """0.30 <= score < 0.50 AND broken_ptp > 0 → Cannot Pay."""
        df = _base_df(recovery_score=0.40, broken_ptp_count=1)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Cannot Pay"

    def test_cannot_pay_mid_score_high_debt(self):
        """0.30 <= score < 0.50 AND income_debt_ratio > 2.0 → Cannot Pay."""
        df = _base_df(recovery_score=0.45, income_debt_ratio=2.5)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Cannot Pay"

    def test_self_cure_high_score(self):
        """score >= 0.70 AND dpd <= 7 AND payment_rate >= 0.80 AND self_cure_probability >= 0.70 → Self-cure."""
        df = _base_df(recovery_score=0.80, dpd_current=5, payment_rate=0.85)
        df["self_cure_probability"] = 0.80  # New requirement: must have high prob
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Self-cure"

    def test_can_pay_default(self):
        """Score = 0.60, no special conditions → Can Pay."""
        df = _base_df(recovery_score=0.60, dpd_current=20, payment_rate=0.5)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Can Pay"

    def test_self_cure_not_triggered_high_dpd(self):
        """score >= 0.70 tapi dpd > 7 → bukan Self-cure."""
        df = _base_df(recovery_score=0.80, dpd_current=15, payment_rate=0.85)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] != "Self-cure"

    def test_risk_segment_valid_values(self):
        """risk_segment harus selalu salah satu dari 4 nilai valid."""
        valid = {"Self-cure", "Can Pay", "Cannot Pay", "Won't Pay"}
        for score in np.linspace(0.0, 1.0, 20):
            df = _base_df(recovery_score=float(score))
            result = apply_risk_segment(df)
            seg = result["risk_segment"].iloc[0]
            assert seg in valid, f"risk_segment '{seg}' tidak valid untuk score={score:.2f}"


# ── NBA TESTS ─────────────────────────────────────────────────────────

class TestApplyNba:

    def _scored_df(self, segment="Can Pay", cycle=1, ots=5_000_000, hist=0):
        return pd.DataFrame([{
            "contract_no": "C001",
            "cust_id": "CUST001",
            "risk_segment": segment,
            "cycle_encoded": cycle,
            "total_ots": ots,
            "historical_default_count": hist,
        }])

    def test_self_cure_gets_wa(self):
        """Self-cure → NBA = WA."""
        df = self._scored_df(segment="Self-cure")
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "WA"

    def test_can_pay_cycle_0_gets_wa(self):
        """Can Pay + cycle <= 1 → NBA = WA."""
        df = self._scored_df(segment="Can Pay", cycle=0)
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "WA"

    def test_can_pay_cycle_2_gets_deskcoll(self):
        """Can Pay + cycle >= 2 → NBA = Deskcoll."""
        df = self._scored_df(segment="Can Pay", cycle=2)
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "Deskcoll"

    def test_wont_pay_low_ots_gets_visit(self):
        """Won't Pay + OTS < 5jt → NBA = Visit."""
        df = self._scored_df(segment="Won't Pay", ots=3_000_000)
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "Visit"

    def test_wont_pay_high_ots_gets_somasi(self):
        """Won't Pay + OTS >= 5jt → NBA = Somasi."""
        df = self._scored_df(segment="Won't Pay", ots=10_000_000)
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "Somasi"

    def test_wont_pay_very_high_ots_hist_default_gets_pickup(self):
        """Won't Pay + OTS >= 20jt + hist_default >= 2 → NBA = Pickup."""
        df = self._scored_df(segment="Won't Pay", ots=25_000_000, hist=2)
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "Pickup"

    def test_nba_override_upgrades(self):
        """COLLECTION_SENSITIVITY=Visit dan NBA default=WA → output NBA=Visit (upgrade)."""
        df = self._scored_df(segment="Self-cure")  # NBA default = WA
        df_cbs = pd.DataFrame([{
            "cust_id": "CUST001",
            "collection_sensitivity": "Visit",  # rank lebih tinggi dari WA
        }])
        result = apply_nba(df, df_cbs)
        assert result["nba_recommendation"].iloc[0] == "Visit"

    def test_nba_override_does_not_downgrade(self):
        """NBA=Somasi, sensitivity=WA → tetap Somasi (tidak downgrade)."""
        df = self._scored_df(segment="Won't Pay", ots=10_000_000)  # NBA = Somasi
        df_cbs = pd.DataFrame([{
            "cust_id": "CUST001",
            "collection_sensitivity": "WA",  # rank lebih rendah dari Somasi
        }])
        result = apply_nba(df, df_cbs)
        assert result["nba_recommendation"].iloc[0] == "Somasi"

    def test_nba_valid_values(self):
        """nba_recommendation harus selalu dari nilai valid."""
        valid = {"WA", "Deskcoll", "Visit", "Somasi", "Pickup"}
        for seg in ["Self-cure", "Can Pay", "Cannot Pay", "Won't Pay"]:
            for cycle in [0, 1, 2, 3]:
                df = self._scored_df(segment=seg, cycle=cycle)
                result = apply_nba(df)
                nba = result["nba_recommendation"].iloc[0]
                assert nba in valid, f"NBA '{nba}' tidak valid"


# ── PRIORITY TESTS ────────────────────────────────────────────────────

class TestApplyPriority:

    def _df_with_segment_ots(self, segment, ots):
        return pd.DataFrame([{
            "contract_no": "C001",
            "risk_segment": segment,
            "total_ots": ots,
        }])

    def test_wont_pay_high_ots_critical(self):
        """Won't Pay + OTS >= 20jt → Critical."""
        df = self._df_with_segment_ots("Won't Pay", 25_000_000)
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "Critical"

    def test_wont_pay_low_ots_high(self):
        """Won't Pay + OTS < 5jt → High."""
        df = self._df_with_segment_ots("Won't Pay", 3_000_000)
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "High"

    def test_cannot_pay_high_ots_critical(self):
        """Cannot Pay + OTS >= 20jt → Critical."""
        df = self._df_with_segment_ots("Cannot Pay", 22_000_000)
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "Critical"

    def test_can_pay_low_ots_low(self):
        """Can Pay + OTS < 5jt → Low."""
        df = self._df_with_segment_ots("Can Pay", 2_000_000)
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "Low"

    def test_self_cure_any_ots_low_or_medium(self):
        """Self-cure hanya bisa Low atau Medium (tidak Critical)."""
        for ots in [1_000_000, 10_000_000, 25_000_000]:
            df = self._df_with_segment_ots("Self-cure", ots)
            result = apply_priority(df)
            pl = result["priority_level"].iloc[0]
            assert pl in {"Low", "Medium"}, \
                f"Self-cure tidak boleh Critical, dapat {pl} untuk OTS={ots}"

    def test_priority_valid_values(self):
        """priority_level harus selalu salah satu dari: Critical, High, Medium, Low."""
        valid = {"Critical", "High", "Medium", "Low"}
        for seg in ["Self-cure", "Can Pay", "Cannot Pay", "Won't Pay"]:
            for ots in [1_000_000, 10_000_000, 25_000_000]:
                df = self._df_with_segment_ots(seg, ots)
                result = apply_priority(df)
                pl = result["priority_level"].iloc[0]
                assert pl in valid, f"priority_level '{pl}' tidak valid"


# ── CONFIDENCE LEVEL TESTS ────────────────────────────────────────────

class TestComputeConfidenceLevel:

    def test_confidence_in_range(self):
        """confidence_level harus dalam [0.0, 1.0]."""
        df = _base_df()
        result = compute_confidence_level(df)
        cl = result["confidence_level"].iloc[0]
        assert 0.0 <= cl <= 1.0

    def test_score_at_0_5_certainty_zero(self):
        """recovery_score = 0.5 → conf_model_certainty = 0.0."""
        df = _base_df(recovery_score=0.5)
        result = compute_confidence_level(df)
        assert result["conf_model_certainty"].iloc[0] == pytest.approx(0.0)

    def test_score_at_extremes_certainty_high(self):
        """recovery_score = 0.0 atau 1.0 → conf_model_certainty = 1.0."""
        for score in [0.0, 1.0]:
            df = _base_df(recovery_score=score)
            result = compute_confidence_level(df)
            assert result["conf_model_certainty"].iloc[0] == pytest.approx(1.0)

    def test_no_payment_history_low_completeness(self):
        """Tanpa payment history (payment_count=0, NaN features) → completeness rendah."""
        df = pd.DataFrame([{
            "contract_no": "C001",
            "cust_id": "CUST001",
            "recovery_score": 0.5,
            "payment_count": 0,
            "treatment_count": 0,
            "avg_delay_days": None,
            "payment_rate": None,
            "ptp_fulfillment_rate": None,
            "avg_interaction_score": None,
            "ptp_reliability_index": None,
        }])
        result = compute_confidence_level(df)
        assert result["conf_data_completeness"].iloc[0] == pytest.approx(0.0)

    def test_confidence_category_high(self):
        """confidence_level >= 0.75 → confidence_category = HIGH."""
        df = _base_df(recovery_score=0.95, payment_count=10, treatment_count=5)
        result = compute_confidence_level(df)
        if result["confidence_level"].iloc[0] >= 0.75:
            assert result["confidence_category"].iloc[0] == "HIGH"

    def test_confidence_category_low(self):
        """confidence_level < 0.50 → confidence_category = LOW."""
        df = pd.DataFrame([{
            "contract_no": "C001",
            "cust_id": "CUST001",
            "recovery_score": 0.50,
            "payment_count": 0,
            "treatment_count": 0,
            "avg_delay_days": None,
            "payment_rate": None,
            "ptp_fulfillment_rate": None,
            "avg_interaction_score": None,
            "ptp_reliability_index": None,
        }])
        result = compute_confidence_level(df)
        if result["confidence_level"].iloc[0] < 0.50:
            assert result["confidence_category"].iloc[0] == "LOW"

    def test_sub_components_present(self):
        """Semua 3 sub-komponen tersimpan sebagai kolom terpisah."""
        df = _base_df()
        result = compute_confidence_level(df)
        assert "conf_data_completeness" in result.columns
        assert "conf_history_depth" in result.columns
        assert "conf_model_certainty" in result.columns


# ── QUALITY CHECK TESTS ───────────────────────────────────────────────

class TestRunQualityCheck:

    def _valid_output_df(self, n=10):
        """Buat DataFrame output yang valid (melewati semua hard checks)."""
        segs = ["Can Pay"] * n
        return pd.DataFrame({
            "contract_no": [f"C{i:03d}" for i in range(n)],
            "cust_id": [f"CUST{i:03d}" for i in range(n)],
            "recovery_score": [0.6] * n,
            "confidence_level": [0.7] * n,
            "risk_segment": segs,
            "nba_recommendation": ["WA"] * n,
            "priority_level": ["Medium"] * n,
        })

    def test_valid_output_passes(self):
        """Output yang valid harus lulus QC tanpa error."""
        df = self._valid_output_df()
        result = run_quality_check(df)
        assert result["status"] == "pass"

    def test_range_failure_raises(self):
        """recovery_score di luar [0,1] → hard fail → ValueError."""
        df = self._valid_output_df()
        df.loc[0, "recovery_score"] = 1.5
        with pytest.raises(ValueError, match="QC hard-fail"):
            run_quality_check(df)

    def test_null_required_column_raises(self):
        """NULL di kolom wajib → hard fail → ValueError."""
        df = self._valid_output_df()
        df.loc[0, "risk_segment"] = None
        with pytest.raises(ValueError, match="QC hard-fail"):
            run_quality_check(df)

    def test_duplicate_contract_no_raises(self):
        """Duplikat CONTRACT_NO → hard fail → ValueError."""
        df = self._valid_output_df()
        df.loc[1, "contract_no"] = df.loc[0, "contract_no"]
        with pytest.raises(ValueError, match="QC hard-fail"):
            run_quality_check(df)

    def test_qc_returns_distribution_stats(self):
        """Output QC harus punya keys distribusi."""
        df = self._valid_output_df()
        result = run_quality_check(df)
        assert "wont_pay_pct" in result
        assert "self_cure_pct" in result
        assert "critical_pct" in result



if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ── TASK-42: Sub-Model Business Rules Tests ───────────────────────────

class TestSubModelBusinessRules:
    """Tests untuk perubahan business rules berdasarkan sub-model scores."""

    def _base_selfcure_candidate(self, self_cure_probability=0.80):
        """Nasabah yang memenuhi semua syarat Self-cure."""
        return pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "recovery_score": 0.75,         # >= 0.70 ✓
            "dpd_current": 5,               # <= 7 ✓
            "payment_rate": 0.90,           # >= 0.80 ✓
            "self_cure_probability": self_cure_probability,
            "rejection_count": 0,
            "last_result_code_encoded": 3,
            "broken_ptp_count": 0,
            "income_debt_ratio": 1.0,
        }])

    def test_self_cure_needs_high_prob(self):
        """prob_self_cure=0.50 (di bawah threshold 0.70) → bukan Self-cure meski skor lain OK."""
        df = self._base_selfcure_candidate(self_cure_probability=0.50)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] != "Self-cure", \
            "Seharusnya bukan Self-cure karena self_cure_probability < 0.70"

    def test_self_cure_with_high_prob(self):
        """Semua syarat terpenuhi termasuk prob >= 0.70 → Self-cure."""
        df = self._base_selfcure_candidate(self_cure_probability=0.80)
        result = apply_risk_segment(df)
        assert result["risk_segment"].iloc[0] == "Self-cure"

    def test_priority_escalation_roll_fwd(self):
        """Medium priority + roll_forward_risk=0.80 → naik menjadi High."""
        df = pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "risk_segment": "Can Pay",
            "total_ots": 10_000_000,        # mid tier → base = Medium
            "roll_forward_risk": 0.80,      # >= 0.75 → escalate
        }])
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "High", \
            "Priority harusnya naik dari Medium ke High karena roll_forward_risk >= 0.75"

    def test_priority_no_escalation_low_roll_fwd(self):
        """roll_forward_risk=0.50 (< 0.75) → tidak ada eskalasi."""
        df = pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "risk_segment": "Can Pay",
            "total_ots": 10_000_000,        # mid tier → base = Medium
            "roll_forward_risk": 0.50,      # < 0.75 → tidak escalate
        }])
        result = apply_priority(df)
        assert result["priority_level"].iloc[0] == "Medium"

    def test_nba_selfcure_override(self):
        """self_cure_probability=0.80 → NBA = WA, override semua aturan sebelumnya."""
        df = pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "risk_segment": "Cannot Pay",   # rule biasa → Deskcoll atau Visit
            "cycle_encoded": 2,             # rule → Visit
            "total_ots": 5_000_000,
            "historical_default_count": 0,
            "self_cure_probability": 0.80,  # override → WA
        }])
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "WA", \
            "NBA harusnya WA karena self_cure_probability >= 0.70"

    def test_nba_low_rpc_visit(self):
        """rpc_rate=0.10 (< 0.30) → minimum Visit, bukan WA atau Deskcoll."""
        df = pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "risk_segment": "Can Pay",      # base → WA (cycle <= 1)
            "cycle_encoded": 0,
            "total_ots": 3_000_000,
            "historical_default_count": 0,
            "rpc_rate": 0.10,               # < 0.30 → minimum Visit
            # no self_cure_probability → tidak ada override-1
        }])
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "Visit", \
            "NBA harusnya minimum Visit karena rpc_rate < 0.30"

    def test_nba_near_maturity_small_balance(self):
        """days_to_maturity < 60 AND ambc kecil → NBA = WA."""
        df = pd.DataFrame([{
            "contract_no": "C999",
            "cust_id": "CUST999",
            "risk_segment": "Cannot Pay",   # rule biasa → Deskcoll
            "cycle_encoded": 1,
            "total_ots": 5_000_000,
            "historical_default_count": 0,
            "days_to_maturity": 20,         # < 60 ✓
            "ambc": 1_500_000,              # < installment_amount * 2 = 4_000_000 ✓
            "installment_amount": 2_000_000,
        }])
        result = apply_nba(df)
        assert result["nba_recommendation"].iloc[0] == "WA", \
            "NBA harusnya WA karena near-maturity dengan saldo kecil"

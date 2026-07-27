"""Unit tests untuk Restructuring Recommendation Engine (TASK-56).

Test coverage:
  - TASK-50: eligibility classifier (3 kondisi BLOCKED + 5 kondisi MANUAL_REVIEW)
  - TASK-51: refinance/consolidation/takeover calc, guardrail, orchestrator

Jalankan:
    cd app/machine-learning
    pytest tests/test_restructuring_engine.py -v
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.restructuring_offer_calculator import (  # noqa: E402
    AssetAppraisal,
    ContractInput,
    CustomerContext,
    EligibilityTier,
    OfferType,
    RestructureOffer,
    RestructurePolicy,
    apply_guardrail,
    assess_restructuring_options,
    calculate_consolidation_offer,
    calculate_refinance_offer,
    calculate_takeover_offer,
    classify_eligibility,
)

POLICY = RestructurePolicy()


def _make_contract(**overrides) -> ContractInput:
    base = dict(
        contract_no="C001", cust_id="CUST01", product_type="Kredit Motor",
        total_ots=15_000_000, interest_rate=0.24, remaining_tenor_months=18,
        installment_amount=1_100_000, dpd_current=45, risk_segment="Cannot Pay",
        recovery_score=0.35, self_cure_probability=0.20,
    )
    base.update(overrides)
    return ContractInput(**base)


def _make_customer(**overrides) -> CustomerContext:
    base = dict(cust_id="CUST01", b_list_status="N", restructure_count=0, active_contract_count=1)
    base.update(overrides)
    return CustomerContext(**base)


# ── TASK-50: Eligibility — 3 kondisi BLOCKED ──────────────────────────

class TestEligibilityBlocked:
    def test_blocked_closed_via_restructure(self):
        contract = _make_contract(closed_via_restructure=True)
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.BLOCKED
        assert any("ditutup" in r for r in result.reasons)

    def test_blocked_invalid_interest_rate(self):
        contract = _make_contract(interest_rate=0.0)
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.BLOCKED

    def test_blocked_invalid_total_ots(self):
        contract = _make_contract(total_ots=0.0)
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.BLOCKED

    def test_blocked_never_triggered_by_business_judgment(self):
        """BLOCKED cuma boleh dipicu masalah data — risk_segment/B_LIST/DPD/
        self_cure/restructure_count TIDAK BOLEH memicu BLOCKED walau ekstrem."""
        contract = _make_contract(
            risk_segment="Won't Pay", dpd_current=999, self_cure_probability=0.99,
        )
        customer = _make_customer(b_list_status="Y", restructure_count=99)
        result = classify_eligibility(contract, customer, POLICY)
        assert result.tier != EligibilityTier.BLOCKED


# ── TASK-50: Eligibility — 5 kondisi MANUAL_REVIEW ────────────────────

class TestEligibilityManualReview:
    def test_manual_review_wrong_risk_segment(self):
        contract = _make_contract(risk_segment="Won't Pay")
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.MANUAL_REVIEW

    def test_manual_review_blist(self):
        contract = _make_contract()
        customer = _make_customer(b_list_status="Y")
        result = classify_eligibility(contract, customer, POLICY)
        assert result.tier == EligibilityTier.MANUAL_REVIEW

    def test_manual_review_high_self_cure_probability(self):
        contract = _make_contract(self_cure_probability=0.85)
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.MANUAL_REVIEW

    def test_manual_review_dpd_out_of_window(self):
        """DPD 10 hari — terlalu dini, di luar window standar (30-180)."""
        contract = _make_contract(dpd_current=10)
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.MANUAL_REVIEW

    def test_manual_review_restructure_count_maxed(self):
        contract = _make_contract()
        customer = _make_customer(restructure_count=POLICY.max_restructure_per_customer)
        result = classify_eligibility(contract, customer, POLICY)
        assert result.tier == EligibilityTier.MANUAL_REVIEW

    def test_auto_when_all_standard_criteria_met(self):
        contract = _make_contract()
        result = classify_eligibility(contract, _make_customer(), POLICY)
        assert result.tier == EligibilityTier.AUTO
        assert result.reasons == []


# ── TASK-51: Refinance ─────────────────────────────────────────────────

class TestRefinanceOffer:
    def test_new_rate_applies_haircut_and_floor(self):
        contract = _make_contract(interest_rate=0.24)
        offer = calculate_refinance_offer(contract, POLICY)
        expected_rate = max(0.24 * (1 - POLICY.max_haircut_pct), POLICY.min_rate_floor)
        assert offer.recommended_new_rate == pytest.approx(round(expected_rate, 4))

    def test_new_tenor_extended_within_cap(self):
        contract = _make_contract(remaining_tenor_months=18)
        offer = calculate_refinance_offer(contract, POLICY)
        max_ext = min(POLICY.max_tenor_extension_months, int(18 * POLICY.max_tenor_extension_ratio))
        assert offer.recommended_new_tenor_months == 18 + max_ext

    def test_offer_type_is_refinance(self):
        offer = calculate_refinance_offer(_make_contract(), POLICY)
        assert offer.offer_type == OfferType.REFINANCE
        assert offer.contract_nos == ["C001"]


# ── TASK-51: Consolidation ───────────────────────────────────────────

class TestConsolidationOffer:
    def test_returns_none_below_min_active_contracts(self):
        contract = _make_contract()
        result = calculate_consolidation_offer([contract], POLICY)
        assert result is None

    def test_combines_multiple_contracts(self):
        c1 = _make_contract(contract_no="C001", total_ots=10_000_000, interest_rate=0.20)
        c2 = _make_contract(contract_no="C002", total_ots=5_000_000, interest_rate=0.30)
        offer = calculate_consolidation_offer([c1, c2], POLICY)
        assert offer is not None
        assert offer.offer_type == OfferType.CONSOLIDATE
        assert set(offer.contract_nos) == {"C001", "C002"}
        assert offer.total_ots_combined == pytest.approx(15_000_000)

    def test_weighted_rate_reflects_ots_proportion(self):
        c1 = _make_contract(contract_no="C001", total_ots=10_000_000, interest_rate=0.20)
        c2 = _make_contract(contract_no="C002", total_ots=5_000_000, interest_rate=0.30)
        offer = calculate_consolidation_offer([c1, c2], POLICY)
        weighted = (10_000_000 * 0.20 + 5_000_000 * 0.30) / 15_000_000
        expected_rate = max(weighted * (1 - POLICY.max_haircut_pct), POLICY.min_rate_floor)
        assert offer.recommended_new_rate == pytest.approx(round(expected_rate, 4))


# ── TASK-51: Takeover (termasuk edge case) ───────────────────────────

class TestTakeoverOffer:
    def test_none_when_appraisal_expired(self):
        contract = _make_contract(total_ots=10_000_000)
        today = date(2026, 1, 1)
        stale_appraisal = AssetAppraisal(
            contract_no="C001", appraised_value=12_000_000,
            appraisal_date=today - timedelta(days=200),  # > 3 bulan
        )
        result = calculate_takeover_offer(contract, stale_appraisal, POLICY, today=today)
        assert result is None

    def test_none_when_asset_value_below_ratio(self):
        contract = _make_contract(total_ots=10_000_000)
        today = date(2026, 1, 1)
        low_value_appraisal = AssetAppraisal(
            contract_no="C001", appraised_value=4_000_000,  # < 50% dari 10jt
            appraisal_date=today - timedelta(days=10),
        )
        result = calculate_takeover_offer(contract, low_value_appraisal, POLICY, today=today)
        assert result is None

    def test_full_payoff_when_asset_covers_all_ots(self):
        contract = _make_contract(total_ots=10_000_000)
        today = date(2026, 1, 1)
        appraisal = AssetAppraisal(
            contract_no="C001", appraised_value=15_000_000,
            appraisal_date=today - timedelta(days=10),
        )
        offer = calculate_takeover_offer(contract, appraisal, POLICY, today=today)
        assert offer is not None
        assert offer.recovery_from_asset == pytest.approx(10_000_000)
        assert offer.recommended_new_installment == 0.0

    def test_partial_payoff_with_remaining_installment(self):
        contract = _make_contract(total_ots=10_000_000, remaining_tenor_months=12)
        today = date(2026, 1, 1)
        appraisal = AssetAppraisal(
            contract_no="C001", appraised_value=6_000_000,  # 60% ratio, sisa 4jt
            appraisal_date=today - timedelta(days=10),
        )
        offer = calculate_takeover_offer(contract, appraisal, POLICY, today=today)
        assert offer is not None
        assert offer.recovery_from_asset == pytest.approx(6_000_000)
        assert offer.recommended_new_installment > 0


# ── TASK-51: Guardrail ─────────────────────────────────────────────────

class TestGuardrail:
    def test_fails_when_npv_restructured_not_better(self):
        offer = RestructureOffer(
            offer_type=OfferType.REFINANCE, contract_nos=["C001"], cust_id="CUST01",
            total_ots_combined=10_000_000, recommended_new_tenor_months=24,
            recommended_new_rate=0.15, recommended_new_installment=500_000,
            npv_baseline=8_000_000, npv_restructured=7_000_000,  # lebih buruk
        )
        result = apply_guardrail(offer)
        assert result.is_guardrail_passed is False
        assert len(result.rejection_reasons) > 0

    def test_passes_when_npv_restructured_better(self):
        offer = RestructureOffer(
            offer_type=OfferType.REFINANCE, contract_nos=["C001"], cust_id="CUST01",
            total_ots_combined=10_000_000, recommended_new_tenor_months=24,
            recommended_new_rate=0.15, recommended_new_installment=500_000,
            npv_baseline=7_000_000, npv_restructured=8_000_000,
        )
        result = apply_guardrail(offer)
        assert result.is_guardrail_passed is True
        assert result.rejection_reasons == []


# ── Orchestrator: assess_restructuring_options ────────────────────────

class TestAssessRestructuringOptions:
    def test_blocked_returns_empty_offers(self):
        contract = _make_contract(interest_rate=0.0)
        result = assess_restructuring_options(contract, _make_customer(), POLICY)
        assert result.eligibility_tier == EligibilityTier.BLOCKED
        assert result.offers == []

    def test_manual_review_still_returns_offers(self):
        """Regresi paling penting: MANUAL_REVIEW TIDAK BOLEH offers kosong."""
        contract = _make_contract(dpd_current=10)  # di luar window -> MANUAL_REVIEW
        result = assess_restructuring_options(contract, _make_customer(), POLICY)
        assert result.eligibility_tier == EligibilityTier.MANUAL_REVIEW
        assert len(result.offers) >= 1

    def test_auto_returns_offers(self):
        contract = _make_contract()
        result = assess_restructuring_options(contract, _make_customer(), POLICY)
        assert result.eligibility_tier == EligibilityTier.AUTO
        assert len(result.offers) >= 1

    def test_offers_ranked_by_npv_gain_descending(self):
        contract = _make_contract()
        siblings = [_make_contract(contract_no="C002", cust_id="CUST01")]
        result = assess_restructuring_options(contract, _make_customer(), POLICY, sibling_contracts=siblings)
        gains = [o.npv_restructured - o.npv_baseline for o in result.offers]
        assert gains == sorted(gains, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

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
    amortizable_principal,
    apply_guardrail,
    assess_restructuring_options,
    calculate_consolidation_offer,
    calculate_refinance_offer,
    calculate_takeover_offer,
    classify_eligibility,
    effective_remaining_tenor,
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
        base = effective_remaining_tenor(contract)
        max_ext = min(POLICY.max_tenor_extension_months, int(base * POLICY.max_tenor_extension_ratio))
        assert offer.recommended_new_tenor_months == base + max_ext

    def test_tenor_base_is_unpaid_installments_not_maturity_date(self):
        """Koreksi #2: basis tenor adalah jumlah cicilan yang masih terutang
        (total_ots / installment), BUKAN jarak ke maturity_date. Nasabah
        menunggak punya sisa cicilan melebihi maturity kontraknya, dan memakai
        maturity_date memaksa saldo besar ke jendela pendek sehingga cicilan
        barunya meledak. Di sini maturity_date sengaja menyatakan 2 bulan lagi
        padahal masih ada ~14 cicilan terutang."""
        contract = _make_contract(
            total_ots=15_000_000, installment_amount=1_100_000, remaining_tenor_months=2
        )
        assert effective_remaining_tenor(contract) == 14
        offer = calculate_refinance_offer(contract, POLICY)
        assert offer.recommended_new_tenor_months == 14 + 7
        # Dengan perilaku lama (basis 2 bulan) cicilannya akan jadi jutaan —
        # jauh di atas cicilan sekarang. Sekarang harus lebih ringan.
        assert offer.recommended_new_installment < contract.installment_amount

    def test_amortizes_principal_not_gross_obligation(self):
        """Koreksi #1: yang diamortisasi ulang adalah pokok terutang, bukan
        total_ots yang sudah mengandung bunga belum jatuh tempo — kalau bruto
        dipakai, bunga baru ditumpuk di atas bunga lama."""
        gross = _make_contract(total_ots=15_000_000, principal_ots=0.0)
        with_principal = _make_contract(total_ots=15_000_000, principal_ots=13_000_000)
        assert amortizable_principal(gross) == 15_000_000       # fallback
        assert amortizable_principal(with_principal) == 13_000_000
        # Tenor identik (dihitung dari total_ots bruto di kedua kasus), jadi
        # perbedaan cicilan murni berasal dari pokok yang benar.
        offer_gross = calculate_refinance_offer(gross, POLICY)
        offer_principal = calculate_refinance_offer(with_principal, POLICY)
        assert offer_principal.recommended_new_tenor_months == offer_gross.recommended_new_tenor_months
        assert offer_principal.recommended_new_installment < offer_gross.recommended_new_installment

    def test_offer_type_is_refinance(self):
        offer = calculate_refinance_offer(_make_contract(), POLICY)
        assert offer.offer_type == OfferType.REFINANCE
        assert offer.contract_nos == ["C001"]

    def test_current_installment_is_carried_for_comparison(self):
        """Tanpa angka pembanding, "cicilan baru" tidak punya makna dan
        guardrail sisi nasabah tidak bisa diuji."""
        offer = calculate_refinance_offer(_make_contract(installment_amount=1_100_000), POLICY)
        assert offer.current_installment_total == pytest.approx(1_100_000)


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
        expected_rate = max(
            min(weighted * (1 - POLICY.max_haircut_pct), min(0.20, 0.30)),
            POLICY.min_rate_floor,
        )
        assert offer.recommended_new_rate == pytest.approx(round(expected_rate, 4))

    def test_rate_never_exceeds_cheapest_existing_contract(self):
        """Rata-rata tertimbang bisa lebih tinggi dari salah satu kontrak,
        sehingga melebur justru MENAIKKAN bunga pinjaman termurah nasabah
        (kasus nyata: 12,24% + 37,69% -> 19,24%, naik 57%). Nasabah tahu
        rate-nya sendiri — "satu rate lebih ringan" yang ternyata lebih mahal
        adalah cara tercepat kehilangan kepercayaan."""
        cheap = _make_contract(contract_no="C001", total_ots=2_000_000, interest_rate=0.1224)
        pricey = _make_contract(contract_no="C002", total_ots=20_000_000, interest_rate=0.3769)
        offer = calculate_consolidation_offer([cheap, pricey], POLICY)
        assert offer.recommended_new_rate <= 0.1224 + 5e-5


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
    """Guardrail menguji DUA sisi: lender (NPV membaik) dan nasabah (tawaran
    benar-benar keringanan). Sisi nasabah tidak ada sebelum audit 2026-07-30,
    sehingga 100% tawaran lolos sambil 80%-nya menaikkan cicilan nasabah."""

    @staticmethod
    def _offer(**overrides) -> RestructureOffer:
        base = dict(
            offer_type=OfferType.REFINANCE, contract_nos=["C001"], cust_id="CUST01",
            total_ots_combined=10_000_000, recommended_new_tenor_months=24,
            recommended_new_rate=0.15, recommended_new_installment=700_000,
            npv_baseline=7_000_000, npv_restructured=8_000_000,
            npv_restructured_risk_adjusted=8_000_000,
            current_installment_total=1_000_000,
            total_remaining_current=20_000_000, total_new_schedule=16_800_000,
        )
        base.update(overrides)
        return RestructureOffer(**base)

    def test_fails_when_npv_not_better(self):
        result = apply_guardrail(self._offer(npv_restructured_risk_adjusted=6_000_000), POLICY)
        assert result.is_guardrail_passed is False
        assert any("NPV" in r for r in result.rejection_reasons)

    def test_npv_compared_on_risk_adjusted_basis_not_raw(self):
        """Perilaku lama membandingkan npv_restructured MENTAH terhadap
        npv_baseline yang sudah didiskon recovery_score (~70%), sehingga
        praktis tidak bisa gagal. Di sini yang mentah tampak menang
        (9jt > 7jt) tapi yang risk-adjusted kalah — harus DITOLAK."""
        result = apply_guardrail(
            self._offer(npv_restructured=9_000_000, npv_restructured_risk_adjusted=3_150_000),
            POLICY,
        )
        assert result.is_guardrail_passed is False

    def test_passes_when_better_for_both_sides(self):
        result = apply_guardrail(self._offer(), POLICY)
        assert result.is_guardrail_passed is True
        assert result.rejection_reasons == []

    def test_fails_when_installment_goes_up(self):
        """Kasus paling merusak di data lama: 79,9% tawaran mengusulkan cicilan
        LEBIH TINGGI dan tetap lolos."""
        result = apply_guardrail(self._offer(recommended_new_installment=1_500_000), POLICY)
        assert result.is_guardrail_passed is False
        assert any("cicilan baru" in r for r in result.rejection_reasons)

    def test_fails_when_installment_reduction_is_token(self):
        """Turun Rp1.411/bulan (kasus nyata) secara teknis "lebih rendah" tapi
        tidak mungkin dijual sebagai keringanan."""
        result = apply_guardrail(self._offer(recommended_new_installment=998_589), POLICY)
        assert result.is_guardrail_passed is False

    def test_fails_when_total_repayment_balloons(self):
        result = apply_guardrail(
            self._offer(total_remaining_current=10_000_000, total_new_schedule=30_000_000),
            POLICY,
        )
        assert result.is_guardrail_passed is False
        assert any("total bayar" in r for r in result.rejection_reasons)

    def test_moderate_total_increase_is_allowed(self):
        """Total bayar naik sedikit itu harga wajar dari tenor lebih panjang —
        yang dilarang hanya lonjakan tidak proporsional."""
        result = apply_guardrail(
            self._offer(total_remaining_current=15_000_000, total_new_schedule=16_800_000),
            POLICY,
        )
        assert result.is_guardrail_passed is True

    def test_fails_when_current_installment_unknown(self):
        """Tanpa pembanding, klaim "lebih ringan" tidak bisa dibuktikan —
        tolak, jangan diam-diam diloloskan."""
        result = apply_guardrail(self._offer(current_installment_total=0.0), POLICY)
        assert result.is_guardrail_passed is False

    def test_full_payoff_takeover_skips_installment_check(self):
        """Aset menutup seluruh kewajiban — tidak ada cicilan baru sama sekali,
        jadi tidak ada "cicilan lebih ringan" yang bisa dibandingkan."""
        result = apply_guardrail(
            self._offer(
                offer_type=OfferType.TAKEOVER,
                recommended_new_tenor_months=0, recommended_new_installment=0.0,
                total_remaining_current=10_000_000, total_new_schedule=10_000_000,
            ),
            POLICY,
        )
        assert result.is_guardrail_passed is True


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

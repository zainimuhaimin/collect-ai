"""
Restructuring Offer Calculator — Fase 1 (rule-based, deterministik)
CollectAI — Restructuring Recommendation Engine

SATU-SATUNYA salinan modul ini (app/shared/). Dulu ada 3 copy fisik (root,
app/backend/ml/, dan rencana app/machine-learning/business_rules/) yang
harus disinkronkan manual tiap ada revisi logika — sekarang app/backend/
dan app/machine-learning/ SAMA-SAMA meng-import dari sini, tidak ada lagi
salinan. Jangan copy-paste file ini ke tempat lain; import langsung
`from shared.restructuring_offer_calculator import ...` (lihat masing-masing
caller untuk cara wiring sys.path ke app/).

Modul ini HANYA menghitung angka tawaran secara deterministik, dan TIDAK
BOLEH mengimpor apapun dari app/backend/ (FastAPI dll) atau
app/machine-learning/ (config/settings.py dll) — kalau perlu policy dari
config masing-masing app, caller yang membangun `RestructurePolicy(...)`
lalu meneruskannya ke sini, bukan modul ini yang menariknya sendiri.

Model ML acceptance probability adalah lapisan TERPISAH yang baru
dibangun di Fase 2, setelah restructuring_history terkumpul cukup data
(lihat TASK-55 di restructuring-engine-tasks.md).

PENTING: apply_guardrail() adalah lapisan yang PERMANEN. Fase 2 nanti
hanya mengganti cara MERANKING kandidat (expected value = P(accept) x
npv_restructured), bukan menghapus guardrail ini.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ── POLICY CONFIG (harus sinkron dengan config/settings.py) ─────────

@dataclass(frozen=True)
class RestructurePolicy:
    max_haircut_pct: float = 0.40              # turun maks 40% relatif dari rate asal
    min_rate_floor: float = 0.09               # floor absolut ~cost of fund + margin
    max_tenor_extension_months: int = 24
    max_tenor_extension_ratio: float = 0.50    # atau maks 50% dari sisa tenor asli
    min_dpd_for_restructure: int = 30
    max_dpd_for_restructure: int = 180
    max_restructure_per_customer: int = 2
    asset_value_min_ratio: float = 0.50        # nilai aset min. tutup 50% OTS
    appraisal_max_age_months: int = 3
    consolidation_min_active_contracts: int = 2
    discount_rate_annual: float = 0.12         # dipakai utk NPV, BUKAN bunga kontrak


# ── INPUT DATA CONTRACTS ──────────────────────────────────────────────

@dataclass
class ContractInput:
    contract_no: str
    cust_id: str
    product_type: str
    total_ots: float
    interest_rate: float            # annual, decimal, mis. 0.24 = 24% p.a.
    remaining_tenor_months: int
    installment_amount: float
    dpd_current: int
    risk_segment: str               # 'Cannot Pay' | 'Self Cure' | "Won't Pay"
    recovery_score: float
    self_cure_probability: float
    closed_via_restructure: bool = False


@dataclass
class CustomerContext:
    cust_id: str
    b_list_status: str              # 'Y' / 'N'
    restructure_count: int
    active_contract_count: int


@dataclass
class AssetAppraisal:
    contract_no: str
    appraised_value: float
    appraisal_date: date


class OfferType(str, Enum):
    REFINANCE = "REFINANCE"
    CONSOLIDATE = "CONSOLIDATE"
    TAKEOVER = "TAKEOVER"


@dataclass
class RestructureOffer:
    offer_type: OfferType
    contract_nos: list[str]
    cust_id: str
    total_ots_combined: float
    recommended_new_tenor_months: int
    recommended_new_rate: float
    recommended_new_installment: float
    recovery_from_asset: float = 0.0
    npv_baseline: float = 0.0
    npv_restructured: float = 0.0
    is_guardrail_passed: bool = False
    rejection_reasons: list[str] = field(default_factory=list)


# ── ELIGIBILITY — TIERED, BUKAN GATE BINER ──────────────────────────────
# AUTO           → lolos semua kriteria standar, daily batch boleh mendorong
#                  ke collector secara otomatis (proaktif).
# MANUAL_REVIEW  → angka TETAP DIHITUNG. Dipakai saat backend query on-demand
#                  per customer — CS/supervisor bisa lihat opsinya, tapi perlu
#                  approval sebelum benar-benar ditawarkan ke nasabah.
# BLOCKED        → data tidak valid/tidak cukup untuk dihitung sama sekali.
#                  Ini SATU-SATUNYA tier yang tidak menghasilkan angka.

class EligibilityTier(str, Enum):
    AUTO = "AUTO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass
class EligibilityResult:
    tier: EligibilityTier
    reasons: list[str] = field(default_factory=list)


def classify_eligibility(
    contract: ContractInput, customer: CustomerContext, policy: RestructurePolicy
) -> EligibilityResult:
    # ── BLOCKED: murni masalah data/status kontrak, BUKAN judgment bisnis ──
    blocked_reasons: list[str] = []
    if contract.closed_via_restructure:
        blocked_reasons.append("kontrak sudah ditutup lewat restrukturisasi sebelumnya")
    if contract.interest_rate is None or contract.interest_rate <= 0:
        blocked_reasons.append("interest_rate tidak valid — tidak bisa hitung amortisasi")
    if contract.total_ots is None or contract.total_ots <= 0:
        blocked_reasons.append("total_ots tidak valid")

    if blocked_reasons:
        return EligibilityResult(tier=EligibilityTier.BLOCKED, reasons=blocked_reasons)

    # ── MANUAL_REVIEW: judgment bisnis — angka tetap dihitung di bawah ──────
    review_reasons: list[str] = []
    if contract.risk_segment != "Cannot Pay":
        review_reasons.append(f"risk_segment '{contract.risk_segment}' bukan target standar")
    if customer.b_list_status == "Y":
        review_reasons.append("nasabah B_LIST — butuh approval manual")
    if contract.self_cure_probability >= 0.70:
        review_reasons.append("self_cure_probability tinggi — pertimbangkan biarkan self-cure")
    if not (policy.min_dpd_for_restructure <= contract.dpd_current <= policy.max_dpd_for_restructure):
        review_reasons.append(
            f"DPD {contract.dpd_current} di luar window standar "
            f"({policy.min_dpd_for_restructure}-{policy.max_dpd_for_restructure})"
        )
    if customer.restructure_count >= policy.max_restructure_per_customer:
        review_reasons.append(f"restructure_count ({customer.restructure_count}) sudah mencapai batas standar")

    if review_reasons:
        return EligibilityResult(tier=EligibilityTier.MANUAL_REVIEW, reasons=review_reasons)

    return EligibilityResult(tier=EligibilityTier.AUTO, reasons=[])


# ── AMORTISASI & NPV HELPER ────────────────────────────────────────────

def calculate_installment(principal: float, annual_rate: float, tenor_months: int) -> float:
    """Reducing-balance / annuity. Kalau produk pakai flat rate, ganti fungsi
    ini di implementasi final — jangan campur dua metode dalam satu engine."""
    if tenor_months <= 0:
        return principal
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / tenor_months
    factor = (1 + monthly_rate) ** tenor_months
    return principal * monthly_rate * factor / (factor - 1)


def npv_of_installments(installment: float, tenor_months: int, annual_discount_rate: float) -> float:
    monthly_discount = annual_discount_rate / 12
    return sum(installment / ((1 + monthly_discount) ** m) for m in range(1, tenor_months + 1))


# ── CABANG 1: REFINANCE ────────────────────────────────────────────────

def calculate_refinance_offer(contract: ContractInput, policy: RestructurePolicy) -> RestructureOffer:
    tenor_ext = min(
        policy.max_tenor_extension_months,
        int(contract.remaining_tenor_months * policy.max_tenor_extension_ratio),
    )
    new_tenor = contract.remaining_tenor_months + tenor_ext
    new_rate = max(contract.interest_rate * (1 - policy.max_haircut_pct), policy.min_rate_floor)
    new_installment = calculate_installment(contract.total_ots, new_rate, new_tenor)

    npv_baseline = (
        npv_of_installments(contract.installment_amount, contract.remaining_tenor_months, policy.discount_rate_annual)
        * contract.recovery_score
    )
    npv_restructured = npv_of_installments(new_installment, new_tenor, policy.discount_rate_annual)

    return RestructureOffer(
        offer_type=OfferType.REFINANCE,
        contract_nos=[contract.contract_no],
        cust_id=contract.cust_id,
        total_ots_combined=contract.total_ots,
        recommended_new_tenor_months=new_tenor,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
    )


# ── CABANG 2: CONSOLIDATE ───────────────────────────────────────────────

def calculate_consolidation_offer(
    contracts: list[ContractInput], policy: RestructurePolicy
) -> Optional[RestructureOffer]:
    if len(contracts) < policy.consolidation_min_active_contracts:
        return None

    total_ots = sum(c.total_ots for c in contracts)
    weighted_rate = sum(c.total_ots * c.interest_rate for c in contracts) / total_ots
    longest_tenor = max(c.remaining_tenor_months for c in contracts)

    tenor_ext = min(policy.max_tenor_extension_months, int(longest_tenor * policy.max_tenor_extension_ratio))
    new_tenor = longest_tenor + tenor_ext
    new_rate = max(weighted_rate * (1 - policy.max_haircut_pct), policy.min_rate_floor)
    new_installment = calculate_installment(total_ots, new_rate, new_tenor)

    npv_baseline = sum(
        npv_of_installments(c.installment_amount, c.remaining_tenor_months, policy.discount_rate_annual)
        * c.recovery_score
        for c in contracts
    )
    npv_restructured = npv_of_installments(new_installment, new_tenor, policy.discount_rate_annual)

    return RestructureOffer(
        offer_type=OfferType.CONSOLIDATE,
        contract_nos=[c.contract_no for c in contracts],
        cust_id=contracts[0].cust_id,
        total_ots_combined=round(total_ots, 2),
        recommended_new_tenor_months=new_tenor,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
    )


# ── CABANG 3: TAKEOVER ──────────────────────────────────────────────────

def calculate_takeover_offer(
    contract: ContractInput,
    appraisal: AssetAppraisal,
    policy: RestructurePolicy,
    today: Optional[date] = None,
) -> Optional[RestructureOffer]:
    today = today or date.today()
    appraisal_age_months = (today.year - appraisal.appraisal_date.year) * 12 + (
        today.month - appraisal.appraisal_date.month
    )
    if appraisal_age_months > policy.appraisal_max_age_months:
        return None  # appraisal basi — perlu re-appraisal dulu

    if appraisal.appraised_value / contract.total_ots < policy.asset_value_min_ratio:
        return None  # nilai aset tidak cukup signifikan menutup OTS

    recovery_from_asset = min(appraisal.appraised_value, contract.total_ots)
    sisa_ots = contract.total_ots - recovery_from_asset

    if sisa_ots <= 0:
        return RestructureOffer(
            offer_type=OfferType.TAKEOVER,
            contract_nos=[contract.contract_no],
            cust_id=contract.cust_id,
            total_ots_combined=contract.total_ots,
            recommended_new_tenor_months=0,
            recommended_new_rate=0.0,
            recommended_new_installment=0.0,
            recovery_from_asset=round(recovery_from_asset, 2),
            npv_baseline=contract.total_ots * contract.recovery_score,
            npv_restructured=recovery_from_asset,
        )

    new_rate = max(contract.interest_rate * (1 - policy.max_haircut_pct), policy.min_rate_floor)
    new_installment = calculate_installment(sisa_ots, new_rate, contract.remaining_tenor_months)

    npv_baseline = contract.total_ots * contract.recovery_score
    npv_restructured = recovery_from_asset + npv_of_installments(
        new_installment, contract.remaining_tenor_months, policy.discount_rate_annual
    )

    return RestructureOffer(
        offer_type=OfferType.TAKEOVER,
        contract_nos=[contract.contract_no],
        cust_id=contract.cust_id,
        total_ots_combined=contract.total_ots,
        recommended_new_tenor_months=contract.remaining_tenor_months,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        recovery_from_asset=round(recovery_from_asset, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
    )


# ── GUARDRAIL — LAPISAN TERAKHIR, PERMANEN ──────────────────────────────

def apply_guardrail(offer: RestructureOffer) -> RestructureOffer:
    reasons: list[str] = []
    if offer.npv_restructured <= offer.npv_baseline:
        reasons.append("npv_restructured tidak lebih baik dari npv_baseline")

    offer.is_guardrail_passed = len(reasons) == 0
    offer.rejection_reasons = reasons
    return offer


# ── ORCHESTRATOR ─────────────────────────────────────────────────────────

@dataclass
class RestructuringAssessment:
    """Hasil lengkap untuk satu customer/kontrak — ini yang diserialisasi
    jadi response API buat backend, baik dari hasil batch maupun on-demand."""
    cust_id: str
    contract_no: str
    eligibility_tier: EligibilityTier
    eligibility_reasons: list[str]
    offers: list[RestructureOffer] = field(default_factory=list)


def assess_restructuring_options(
    contract: ContractInput,
    customer: CustomerContext,
    policy: RestructurePolicy,
    sibling_contracts: Optional[list[ContractInput]] = None,
    appraisal: Optional[AssetAppraisal] = None,
    today: Optional[date] = None,
) -> RestructuringAssessment:
    eligibility = classify_eligibility(contract, customer, policy)

    if eligibility.tier == EligibilityTier.BLOCKED:
        # Satu-satunya kasus tidak ada angka sama sekali — data tidak valid.
        return RestructuringAssessment(
            cust_id=contract.cust_id, contract_no=contract.contract_no,
            eligibility_tier=eligibility.tier, eligibility_reasons=eligibility.reasons, offers=[],
        )

    # AUTO maupun MANUAL_REVIEW tetap dihitung angkanya — bedanya cuma
    # apakah backend boleh mendorongnya otomatis atau harus lewat approval dulu.
    candidates: list[RestructureOffer] = [calculate_refinance_offer(contract, policy)]

    if sibling_contracts:
        consolidation = calculate_consolidation_offer([contract] + sibling_contracts, policy)
        if consolidation:
            candidates.append(consolidation)

    if appraisal:
        takeover = calculate_takeover_offer(contract, appraisal, policy, today)
        if takeover:
            candidates.append(takeover)

    candidates = [apply_guardrail(o) for o in candidates]
    passed = [o for o in candidates if o.is_guardrail_passed]

    # Ranking Fase 1: NPV gain terbesar.
    # Fase 2 (setelah ada model acceptance): ganti key ini dengan
    # expected_value = acceptance_probability(o) * o.npv_restructured
    passed.sort(key=lambda o: (o.npv_restructured - o.npv_baseline), reverse=True)

    return RestructuringAssessment(
        cust_id=contract.cust_id, contract_no=contract.contract_no,
        eligibility_tier=eligibility.tier, eligibility_reasons=eligibility.reasons, offers=passed,
    )


if __name__ == "__main__":
    # Contoh pakai — sekaligus jadi smoke test manual
    policy = RestructurePolicy()

    # Kasus 1: memenuhi semua kriteria standar → tier AUTO
    contract_auto = ContractInput(
        contract_no="C001", cust_id="CUST01", product_type="Kredit Motor",
        total_ots=15_000_000, interest_rate=0.24, remaining_tenor_months=18,
        installment_amount=1_100_000, dpd_current=45, risk_segment="Cannot Pay",
        recovery_score=0.35, self_cure_probability=0.20,
    )
    customer_auto = CustomerContext(cust_id="CUST01", b_list_status="N", restructure_count=0, active_contract_count=1)
    print("=== Kasus AUTO ===")
    print(assess_restructuring_options(contract_auto, customer_auto, policy))

    # Kasus 2: DPD masih terlalu dini (10 hari) → tier MANUAL_REVIEW,
    # tapi angka tetap dihitung — ini yang tadinya hilang total di versi lama
    contract_review = ContractInput(
        contract_no="C002", cust_id="CUST02", product_type="Kredit Motor",
        total_ots=15_000_000, interest_rate=0.24, remaining_tenor_months=18,
        installment_amount=1_100_000, dpd_current=10, risk_segment="Cannot Pay",
        recovery_score=0.35, self_cure_probability=0.20,
    )
    customer_review = CustomerContext(cust_id="CUST02", b_list_status="N", restructure_count=0, active_contract_count=1)
    print("\n=== Kasus MANUAL_REVIEW (DPD masih dini) ===")
    print(assess_restructuring_options(contract_review, customer_review, policy))

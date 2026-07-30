"""Restructuring Offer Calculator — wiring ML ke modul bersama.

Implementasi asli ada di app/shared/restructuring_offer_calculator.py (SATU
sumber kebenaran, dipakai juga oleh app/backend/). File ini re-export semua
simbol publiknya supaya kode ML tetap bisa `from src.restructuring_offer_calculator
import ...` — konsisten dengan file lain di src/ (feature_engineering.py,
business_rules.py, dst) — TANPA menyimpan salinan logika sendiri.

(TASK-51 di restructuring-engine-tasks.md awalnya menyebut folder
`business_rules/` terpisah, tapi itu bentrok secara penamaan dengan
src/business_rules.py yang sudah ada — jadi ditaruh di src/ langsung
dengan nama yang tidak ambigu.)

Tambahan khusus ML: `restructuring_policy_from_settings()` — membangun
RestructurePolicy dari config/settings.py (TASK-49), supaya nilai kebijakan
hanya perlu diubah di satu tempat (settings.py), bukan di-hardcode ulang di
tiap pipeline yang memanggil assess_restructuring_options().
"""
from __future__ import annotations

import os
import sys

# app/ (parent dari machine-learning/ dan backend/) harus ada di sys.path
# supaya `shared` bisa diimport dari sini.
_ML_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.dirname(_ML_ROOT)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
if _ML_ROOT not in sys.path:
    sys.path.insert(0, _ML_ROOT)

from shared.restructuring_offer_calculator import (  # noqa: E402,F401
    AssetAppraisal,
    ContractInput,
    CustomerContext,
    EligibilityResult,
    EligibilityTier,
    OfferType,
    RestructureOffer,
    RestructurePolicy,
    RestructuringAssessment,
    amortizable_principal,
    apply_guardrail,
    assess_restructuring_options,
    calculate_consolidation_offer,
    calculate_installment,
    calculate_refinance_offer,
    calculate_takeover_offer,
    classify_eligibility,
    effective_remaining_tenor,
    npv_of_installments,
    restructured_recovery_probability,
)

from config.settings import (  # noqa: E402
    MAX_HAIRCUT_PCT,
    MIN_RATE_FLOOR,
    MAX_TENOR_EXTENSION_MONTHS,
    MAX_TENOR_EXTENSION_RATIO,
    MIN_DPD_FOR_RESTRUCTURE,
    MAX_DPD_FOR_RESTRUCTURE,
    MAX_RESTRUCTURE_PER_CUSTOMER,
    ASSET_VALUE_MIN_RATIO,
    APPRAISAL_MAX_AGE_MONTHS,
    CONSOLIDATION_MIN_ACTIVE_CONTRACTS,
    RESTRUCTURE_DISCOUNT_RATE_ANNUAL,
    MIN_INSTALLMENT_REDUCTION_PCT,
    MAX_TOTAL_REPAYMENT_RATIO,
    RESTRUCTURE_RECOVERY_UPLIFT_PCT,
    MAX_RESTRUCTURED_RECOVERY,
)


def restructuring_policy_from_settings() -> RestructurePolicy:
    """Bangun RestructurePolicy dari config/settings.py — panggil ini di
    setiap pipeline ML yang butuh policy, JANGAN instansiasi
    `RestructurePolicy()` polos (itu cuma starting-point default modul,
    bukan angka yang sudah di-approve finance/risk)."""
    return RestructurePolicy(
        max_haircut_pct=MAX_HAIRCUT_PCT,
        min_rate_floor=MIN_RATE_FLOOR,
        max_tenor_extension_months=MAX_TENOR_EXTENSION_MONTHS,
        max_tenor_extension_ratio=MAX_TENOR_EXTENSION_RATIO,
        min_dpd_for_restructure=MIN_DPD_FOR_RESTRUCTURE,
        max_dpd_for_restructure=MAX_DPD_FOR_RESTRUCTURE,
        max_restructure_per_customer=MAX_RESTRUCTURE_PER_CUSTOMER,
        asset_value_min_ratio=ASSET_VALUE_MIN_RATIO,
        appraisal_max_age_months=APPRAISAL_MAX_AGE_MONTHS,
        consolidation_min_active_contracts=CONSOLIDATION_MIN_ACTIVE_CONTRACTS,
        discount_rate_annual=RESTRUCTURE_DISCOUNT_RATE_ANNUAL,
        min_installment_reduction_pct=MIN_INSTALLMENT_REDUCTION_PCT,
        max_total_repayment_ratio=MAX_TOTAL_REPAYMENT_RATIO,
        restructure_recovery_uplift_pct=RESTRUCTURE_RECOVERY_UPLIFT_PCT,
        max_restructured_recovery=MAX_RESTRUCTURED_RECOVERY,
    )

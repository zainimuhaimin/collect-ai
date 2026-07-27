"""Eligibility Classifier — wiring ML ke modul bersama.

TASK-50 (restructuring-engine-tasks.md) awalnya minta file ini di
`business_rules/restructuring_eligibility.py`, tapi lokasi itu bentrok
penamaan dengan src/business_rules.py yang sudah ada — ditaruh di src/
langsung, konsisten dengan file lain (feature_engineering.py, cbs_builder.py,
dst). Implementasi asli `classify_eligibility()` ada di
app/shared/restructuring_offer_calculator.py (satu-satunya sumber, dipakai
juga oleh app/backend/) — file ini murni re-export tanpa duplikasi logika.
"""
from __future__ import annotations

from src.restructuring_offer_calculator import (  # noqa: F401
    EligibilityResult,
    EligibilityTier,
    classify_eligibility,
)

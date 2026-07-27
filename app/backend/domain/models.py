"""
Domain models — dataclass murni, TIDAK bergantung ke FastAPI/Pydantic/DB apapun.
Ini yang membuat domain/ dan ml/ bisa dites tanpa perlu jalankan server sama sekali.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Customer:
    cust_id: str
    name: str
    b_list_status: str            # 'Y' / 'N'
    restructure_count: int
    active_contract_count: int
    behavioral_grade: str


@dataclass
class Contract:
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
class RestructuringOfferRecord:
    """Satu baris restructuring_recommendation_output — dipakai untuk
    validasi transisi status (bukan hasil kalkulasi ml/, itu tetap
    RestructureOffer dari shared/restructuring_offer_calculator.py)."""
    restructure_group_id: str
    cust_id: str
    offer_type: str
    offer_status: str            # GENERATED | OFFERED | ACCEPTED | REJECTED | EXPIRED
    generated_date: date
    expiry_date: Optional[date]
    response_date: Optional[date] = None

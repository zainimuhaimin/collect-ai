from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── TASK-D: list Contract (filter/search/paginasi) ───────────────────────


class ContractListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_no": "CTR-00029-1",
                "cust_id": "CUST-00029",
                "cust_name": "Budi Santoso",
                "product_type": "Personal Loan",
                "dpd_current": 45,
                "outstanding": "Rp 12.500.000",
                "risk_segment": "Cannot Pay",
            }
        }
    )

    contract_no: str
    cust_id: str
    cust_name: str = Field(description="customer_master.cust_name, fallback ke cust_id kalau NULL")
    product_type: str
    dpd_current: int
    outstanding: str = Field(description="Total OTS (prnc_ots + intr_ots), format 'Rp N'")
    risk_segment: Optional[str] = Field(description="Nilai apa adanya dari ai_intelligence_output")


class ContractPageInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"showing_from": 1, "showing_to": 20, "total_contracts": 722, "total_pages": 37}}
    )

    showing_from: int
    showing_to: int
    total_contracts: int
    total_pages: int


class ContractListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contracts": [
                    {
                        "contract_no": "CTR-00029-1",
                        "cust_id": "CUST-00029",
                        "product_type": "Personal Loan",
                        "dpd_current": 45,
                        "outstanding": "Rp 12.500.000",
                        "risk_segment": "Cannot Pay",
                    }
                ],
                "page_info": {"showing_from": 1, "showing_to": 20, "total_contracts": 722, "total_pages": 37},
            }
        }
    )

    contracts: List[ContractListItem]
    page_info: ContractPageInfo


# ── TASK-D: Contract Detail (7 bagian, digabung 1 payload) ───────────────


class OutstandingBreakdown(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"principal": 15000000.0, "interest": 1500000.0, "total": 16500000.0}}
    )

    principal: float
    interest: float
    total: float


class AiScoringSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recovery_score": 0.35,
                "risk_segment": "Cannot Pay",
                "self_cure_probability": 0.20,
                "roll_forward_risk": 0.45,
                "ptp_success_probability": 0.30,
                "nba_recommendation": "Deskcoll",
                "confidence_level": 0.60,
                "scoring_date": "2026-07-21",
            }
        }
    )

    recovery_score: float
    risk_segment: Optional[str] = Field(description="Nilai apa adanya, TIDAK diterjemahkan")
    self_cure_probability: float
    roll_forward_risk: float
    ptp_success_probability: float
    nba_recommendation: Optional[str]
    confidence_level: float
    scoring_date: Optional[str]


class PaymentHistoryItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "due_date": "2026-06-05",
                "actual_pay_date": "2026-06-07",
                "payment_amount": 1100000.0,
                "pay_status": "Paid",
                "delay_days": 2,
                "recovery_source": "WA",
            }
        }
    )

    due_date: Optional[str]
    actual_pay_date: Optional[str]
    payment_amount: float
    pay_status: Optional[str]
    delay_days: Optional[int]
    recovery_source: Optional[str]


class RestructuringStatusSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restructure_group_id": "RG-CUST-00029-2026-07-21-1",
                "offer_status": "GENERATED",
                "eligibility_tier": "MANUAL_REVIEW",
            }
        }
    )

    restructure_group_id: str
    offer_status: str
    eligibility_tier: str


class ContractDetailSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_no": "CTR-00029-1",
                "cust_id": "CUST-00029",
                "product_type": "Personal Loan",
                "cycle": "C1",
                "prev_cycle": "C0",
                "closed_via_restructure": False,
                "new_contract_no": None,
                "loan_amount": 15000000.0,
                "installment_amount": 1100000.0,
                "interest_rate": 0.24,
                "maturity_date": "2028-01-05",
                "remaining_tenor_months": 18,
                "dpd_current": 45,
                "overdue_installment_count": 2,
                "late_fee_amount": 50000.0,
                "ambc": 1200000.0,
                "outstanding": {"principal": 15000000.0, "interest": 1500000.0, "total": 16500000.0},
                "ai_scoring": {
                    "recovery_score": 0.35,
                    "risk_segment": "Cannot Pay",
                    "self_cure_probability": 0.20,
                    "roll_forward_risk": 0.45,
                    "ptp_success_probability": 0.30,
                    "nba_recommendation": "Deskcoll",
                    "confidence_level": 0.60,
                    "scoring_date": "2026-07-21",
                },
                "payment_history": [
                    {
                        "due_date": "2026-06-05",
                        "actual_pay_date": "2026-06-07",
                        "payment_amount": 1100000.0,
                        "pay_status": "Paid",
                        "delay_days": 2,
                        "recovery_source": "WA",
                    }
                ],
                "restructuring_status": {
                    "restructure_group_id": "RG-CUST-00029-2026-07-21-1",
                    "offer_status": "GENERATED",
                    "eligibility_tier": "MANUAL_REVIEW",
                },
            }
        }
    )

    contract_no: str
    cust_id: str
    cust_name: str = Field(description="customer_master.cust_name, fallback ke cust_id kalau NULL")
    product_type: str
    cycle: Optional[str]
    prev_cycle: Optional[str]
    closed_via_restructure: bool
    new_contract_no: Optional[str]
    loan_amount: float
    installment_amount: float
    interest_rate: float
    maturity_date: Optional[str]
    remaining_tenor_months: int
    dpd_current: int
    overdue_installment_count: int
    late_fee_amount: float
    ambc: float
    outstanding: OutstandingBreakdown
    ai_scoring: Optional[AiScoringSchema] = Field(description="None kalau kontrak belum pernah discoring")
    payment_history: List[PaymentHistoryItem] = Field(description="Maks 12 baris terakhir, ORDER BY due_date DESC")
    restructuring_status: Optional[RestructuringStatusSchema] = Field(
        description="None kalau kontrak ini belum pernah masuk grup restrukturisasi manapun"
    )


class ActivityLogEntrySchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "LKP-000123",
                "icon": "sms",
                "title": "SMS — Bayar",
                "timestamp": "12 Oct 2023",
                "description": "Kontak via SMS, hasil: Bayar",
                "tone": "default",
            }
        }
    )

    id: str
    icon: str = Field(description="Nama icon material, diturunkan dari treatment_type")
    title: str
    timestamp: Optional[str] = None
    description: Optional[str] = Field(
        default=None,
        description="Kalimat deskriptif turunan dari treatment_type/result_code/ptp_status baris "
        "lkp_interaction ini — None hanya kalau datanya sendiri memang tidak ada",
    )
    tone: str = Field(description="'danger' kalau ptp_status kontrak ini BROKEN, selain itu 'default'")

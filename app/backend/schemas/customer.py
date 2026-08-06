from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# NOTE: CustomerSummary/CustomerDetail (bentuk lama, pre-TASK-C) sudah
# dihapus — GET /customers dan GET /customers/{cust_id} di-reshape TOTAL
# (lihat frontend-layout-upgrade-tasks.md), tidak ada konsumen lama yang
# masih butuh bentuk itu.


# ── TASK-C: list Customer (filter/search/paginasi) ──────────────────────


class CustomerListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cust_id": "CUST-00029",
                "name": "Indah Anggriawan",
                "active_contract_count": 2,
                "behavioral_grade": "B",
                "b_list_status": "N",
                "priority": "High",
            }
        }
    )

    cust_id: str
    name: str = Field(description="customer_master.cust_name, fallback ke cust_id kalau NULL")
    active_contract_count: int = Field(description="customer_behavioral_standing.active_contract_count")
    behavioral_grade: str = Field(description="customer_behavioral_standing.behavioral_grade")
    b_list_status: str = Field(description="'Y' | 'N' — customer_behavioral_standing.b_list_status")
    priority: str = Field(
        description="'Critical' | 'High' | 'Medium' — level Customer: MAX() priority di antara "
        "SEMUA kontrak aktif (belum closed_via_restructure) milik customer ini, BUKAN dari 1 "
        "kontrak yang dipilih arbitrer. 'Medium' kalau customer tidak punya kontrak aktif sama "
        "sekali. Lihat repositories/priority.py + CustomerRepository._CUSTOMER_LIST_BASE_CTE."
    )


class CustomerPageInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"showing_from": 1, "showing_to": 20, "total_customers": 500, "total_pages": 25}}
    )

    showing_from: int
    showing_to: int
    total_customers: int
    total_pages: int


class CustomerListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customers": [
                    {
                        "cust_id": "CUST-00029",
                        "name": "Indah Anggriawan",
                        "active_contract_count": 2,
                        "behavioral_grade": "B",
                        "b_list_status": "N",
                        "priority": "High",
                    }
                ],
                "page_info": {"showing_from": 1, "showing_to": 20, "total_customers": 500, "total_pages": 25},
            }
        }
    )

    customers: List[CustomerListItem]
    page_info: CustomerPageInfo


# ── TASK-C: Customer Detail 360° view ────────────────────────────────────


class CustomerProfileSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cust_id": "CUST-00029",
                "name": "Indah Anggriawan",
                "initials": "IA",
                "outstanding_balance": "Rp 20.876.317",
                "risk_segment": "Cannot Pay",
                "risk_score": 35,
                "recovery_score": 0.35,
                "self_cure_probability": 0.20,
                "roll_forward_risk": 0.45,
                "ptp_success_probability": 0.30,
                "nba_recommendation": "Deskcoll",
                "behavioral_grade": "B",
                "b_list_status": "N",
                "restructure_count": 0,
                "active_contract_count": 1,
            }
        }
    )

    cust_id: str
    name: str
    initials: str = Field(description="Dihitung dari `name` — lihat core/text_utils.py:compute_initials()")
    outstanding_balance: str = Field(description="Total OTS di-SUM dari SEMUA kontrak aktif customer, format 'Rp N'")
    risk_segment: Optional[str] = Field(description="Nilai APA ADANYA dari ai_intelligence_output, TIDAK diterjemahkan")
    risk_score: int = Field(description="recovery_score * 100, dibulatkan (0-100)")
    recovery_score: float
    self_cure_probability: float
    roll_forward_risk: float
    ptp_success_probability: float
    nba_recommendation: Optional[str]
    behavioral_grade: str
    b_list_status: str
    restructure_count: int
    active_contract_count: int


class CustomerContractItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_no": "CTR-00029-1",
                "product_type": "Personal Loan",
                "dpd_current": 45,
                "outstanding": "Rp 12.500.000",
                "risk_segment": "Cannot Pay",
            }
        }
    )

    contract_no: str
    product_type: str
    dpd_current: int
    outstanding: str = Field(description="Format 'Rp N'")
    risk_segment: Optional[str] = Field(description="Nilai apa adanya dari ai_intelligence_output")

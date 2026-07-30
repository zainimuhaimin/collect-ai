from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RestructuringGroupItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restructure_group_id": "RG-CUST-00029-2026-07-21-1",
                "cust_id": "CUST-00029",
                "contract_nos": ["CTR-00029-1"],
                "offer_type": "REFINANCE",
                "eligibility_tier": "MANUAL_REVIEW",
                "eligibility_reasons": "DPD 10 di luar window standar (30-180)",
                "npv_baseline": 3496908.62,
                "npv_restructured": 11760742.87,
                "generated_date": "2026-07-21",
                "offer_status": "GENERATED",
            }
        }
    )

    restructure_group_id: str
    cust_id: str
    contract_nos: List[str] = Field(description="Bisa >1 untuk offer_type CONSOLIDATE")
    offer_type: str
    eligibility_tier: str
    eligibility_reasons: Optional[str]
    npv_baseline: Optional[float]
    npv_restructured: Optional[float]
    npv_restructured_risk_adjusted: Optional[float] = Field(
        default=None,
        description="npv_restructured * recovery_score, untuk display — None untuk grup batch ML "
        "(belum dipersist di restructuring_recommendation_output, lihat domain/models.py)",
    )
    total_remaining_current: Optional[float] = Field(
        default=None, description="Total tagihan tersisa di jadwal saat ini, tanpa diskonto — None untuk grup batch ML"
    )
    total_new_schedule: Optional[float] = Field(
        default=None, description="Total tagihan di jadwal baru, tanpa diskonto — None untuk grup batch ML"
    )
    generated_date: str
    offer_status: str = Field(description="GENERATED | OFFERED | ACCEPTED | REJECTED | EXPIRED")


class RestructuringGroupPageInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"showing_from": 1, "showing_to": 20, "total_groups": 92, "total_pages": 5}}
    )

    showing_from: int
    showing_to: int
    total_groups: int
    total_pages: int


class RestructuringGroupListResponse(BaseModel):
    """GET /restructuring-groups — dipaginasi sama seperti Customer/Contract
    list (page/page_size), bukan lagi array mentah semua baris sekaligus."""

    groups: List[RestructuringGroupItem]
    page_info: RestructuringGroupPageInfo


class RestructuringGroupActionResult(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restructure_group_id": "RG-CUST-00029-2026-07-21-1",
                "cust_id": "CUST-00029",
                "offer_type": "REFINANCE",
                "offer_status": "OFFERED",
                "generated_date": "2026-07-21",
                "expiry_date": "2026-08-04",
            }
        }
    )

    restructure_group_id: str
    cust_id: str
    offer_type: str
    offer_status: str
    generated_date: str
    expiry_date: Optional[str]

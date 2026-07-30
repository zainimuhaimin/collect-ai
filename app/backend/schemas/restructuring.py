from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RestructureOfferSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "offer_type": "REFINANCE",
                "contract_nos": ["CTR-00029-1"],
                "recommended_new_tenor_months": 21,
                "recommended_new_rate": 0.1376,
                "recommended_new_installment": 623681.04,
                "recovery_from_asset": 0.0,
                "npv_baseline": 3496908.62,
                "npv_restructured": 11760742.87,
                "npv_restructured_risk_adjusted": 4116260.00,
                "total_remaining_current": 19800000.0,
                "total_new_schedule": 13097301.84,
                "is_guardrail_passed": True,
            }
        }
    )

    offer_type: str = Field(description="REFINANCE | CONSOLIDATE | TAKEOVER")
    contract_nos: List[str] = Field(description="Kontrak yang tercakup tawaran ini (>1 untuk CONSOLIDATE)")
    recommended_new_tenor_months: int
    recommended_new_rate: float = Field(description="Rate tahunan baru, decimal (0.1376 = 13.76% p.a.)")
    recommended_new_installment: float
    recovery_from_asset: float = Field(description="Hanya terisi untuk TAKEOVER (nilai appraisal yang menutup OTS)")
    npv_baseline: float = Field(description="NPV kalau kontrak TIDAK direstrukturisasi (sudah risk-adjusted)")
    npv_restructured: float = Field(
        description="NPV kalau tawaran ini diambil, RAW (belum risk-adjusted) — dipakai internal untuk "
        "ranking/guardrail, BUKAN untuk perbandingan display (pakai npv_restructured_risk_adjusted untuk itu)"
    )
    npv_restructured_risk_adjusted: float = Field(
        description="npv_restructured * recovery_score — untuk display, supaya perbandingan dengan "
        "npv_baseline (yang sudah risk-adjusted) apple-to-apple (asumsi risiko yang sama di kedua sisi)"
    )
    total_remaining_current: float = Field(
        description="Total tagihan tersisa di jadwal SAAT INI (installment x sisa tenor), tanpa diskonto sama sekali"
    )
    total_new_schedule: float = Field(
        description="Total tagihan di bawah jadwal BARU (installment baru x tenor baru), tanpa diskonto sama sekali"
    )
    is_guardrail_passed: bool = Field(
        description="Selalu True untuk offer yang muncul di response ini — offer yang gagal guardrail "
        "(npv_restructured <= npv_baseline) sudah difilter sebelum sampai ke sini"
    )


class RestructuringAssessmentSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cust_id": "CUST-00029",
                "contract_no": "CTR-00029-1",
                "eligibility_tier": "MANUAL_REVIEW",
                "eligibility_reasons": ["DPD 10 di luar window standar (30-180)"],
                "offers": [
                    {
                        "offer_type": "REFINANCE",
                        "contract_nos": ["CTR-00029-1"],
                        "recommended_new_tenor_months": 21,
                        "recommended_new_rate": 0.1376,
                        "recommended_new_installment": 623681.04,
                        "recovery_from_asset": 0.0,
                        "npv_baseline": 3496908.62,
                        "npv_restructured": 11760742.87,
                        "npv_restructured_risk_adjusted": 4116260.00,
                        "total_remaining_current": 19800000.0,
                        "total_new_schedule": 13097301.84,
                        "is_guardrail_passed": True,
                    }
                ],
                "source": "ON_DEMAND",
            }
        }
    )

    cust_id: str
    contract_no: str
    eligibility_tier: str = Field(description="AUTO | MANUAL_REVIEW | BLOCKED — lihat deskripsi endpoint")
    eligibility_reasons: List[str] = Field(
        description="Kosong untuk AUTO. Alasan kenapa MANUAL_REVIEW/BLOCKED untuk 2 tier lainnya."
    )
    offers: List[RestructureOfferSchema] = Field(
        description="TETAP terisi untuk AUTO maupun MANUAL_REVIEW. HANYA kosong untuk BLOCKED "
        "(data kontrak tidak valid untuk dihitung sama sekali)."
    )
    restructure_group_id: Optional[str] = Field(
        default=None,
        description="Group restructuring_recommendation_output TERBARU milik customer ini, kalau "
        "sudah ada (dari batch ML atau approval supervisor). None kalau ini murni preview on-demand "
        "tanpa group yang bisa direspons customer.",
    )
    can_respond: bool = Field(
        default=False,
        description="True kalau restructure_group_id di atas berstatus OFFERED — customer boleh "
        "accept/reject lewat POST .../customer-response.",
    )
    customer_response: Optional[str] = Field(
        default=None,
        description="'ACCEPTED' | 'REJECTED' kalau customer sudah pernah merespons group di atas, else None.",
    )
    source: str = "ON_DEMAND"


class CustomerResponseRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"response": "ACCEPTED"}})

    response: str = Field(description="ACCEPTED atau REJECTED (case-insensitive)")


class CustomerResponseResultSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "restructure_group_id": "RG-CUST-00029-2026-07-21-1",
                "cust_id": "CUST-00029",
                "response": "ACCEPTED",
                "message": "Respons customer tercatat",
            }
        }
    )

    restructure_group_id: str
    cust_id: str
    response: str
    message: str

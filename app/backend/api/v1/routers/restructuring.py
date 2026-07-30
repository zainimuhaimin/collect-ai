from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_restructuring_service
from schemas.restructuring import (
    CustomerResponseRequest,
    CustomerResponseResultSchema,
    RestructureOfferSchema,
    RestructuringAssessmentSchema,
)
from services.restructuring_service import RestructuringService

router = APIRouter(prefix="/customers", tags=["restructuring"])

_ERROR_CODE_TO_STATUS = {
    "NOT_FOUND": 404,
    "FORBIDDEN": 403,
    "INVALID_STATE": 409,
    "EXPIRED": 410,
}


@router.get(
    "/{cust_id}/restructuring-options",
    response_model=RestructuringAssessmentSchema,
    summary="Hitung opsi restrukturisasi on-demand",
    description="""
Menghitung tawaran restrukturisasi (REFINANCE/CONSOLIDATE/TAKEOVER) untuk
kontrak utama customer ini, langsung dari data terkini (bukan cache batch).

**`eligibility_tier`** menentukan apa yang boleh dilakukan frontend:
- **AUTO** — lolos semua kriteria standar. `offers` terisi, boleh langsung ditawarkan.
- **MANUAL_REVIEW** — `offers` TETAP terisi, tapi butuh approval supervisor dulu
  sebelum ditawarkan ke customer (lihat `eligibility_reasons` untuk alasannya).
- **BLOCKED** — data kontrak tidak valid (interest_rate/total_ots kosong, atau kontrak
  sudah pernah direstrukturisasi). `offers` SELALU kosong untuk tier ini — satu-satunya
  tier yang tidak menghasilkan angka sama sekali.
""",
    responses={404: {"description": "cust_id tidak punya kontrak aktif untuk dinilai"}},
)
def get_restructuring_options(
    cust_id: str, service: RestructuringService = Depends(get_restructuring_service)
):
    assessment = service.get_options_for_customer(cust_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Data kontrak untuk {cust_id} tidak ditemukan")

    offer_ref = service.get_active_offer_reference(cust_id)
    customer_response = (
        offer_ref.offer_status if offer_ref and offer_ref.offer_status in ("ACCEPTED", "REJECTED") else None
    )

    return RestructuringAssessmentSchema(
        cust_id=assessment.cust_id,
        contract_no=assessment.contract_no,
        eligibility_tier=assessment.eligibility_tier.value,
        eligibility_reasons=assessment.eligibility_reasons,
        offers=[
            RestructureOfferSchema(
                offer_type=o.offer_type.value,
                contract_nos=o.contract_nos,
                recommended_new_tenor_months=o.recommended_new_tenor_months,
                recommended_new_rate=o.recommended_new_rate,
                recommended_new_installment=o.recommended_new_installment,
                recovery_from_asset=o.recovery_from_asset,
                npv_baseline=o.npv_baseline,
                npv_restructured=o.npv_restructured,
                npv_restructured_risk_adjusted=o.npv_restructured_risk_adjusted,
                total_remaining_current=o.total_remaining_current,
                total_new_schedule=o.total_new_schedule,
                is_guardrail_passed=o.is_guardrail_passed,
            )
            for o in assessment.offers
        ],
        restructure_group_id=offer_ref.restructure_group_id if offer_ref else None,
        can_respond=bool(offer_ref and offer_ref.offer_status == "OFFERED"),
        customer_response=customer_response,
        source="ON_DEMAND",
    )


@router.post(
    "/{cust_id}/restructuring-options/{restructure_group_id}/customer-response",
    response_model=CustomerResponseResultSchema,
    summary="Catat keputusan customer (accept/reject)",
    description="""
Mencatat respons CUSTOMER atas satu tawaran yang statusnya sudah **OFFERED**
— endpoint ini TERPISAH dari approval supervisor (yang mengurus transisi
GENERATED→OFFERED untuk tier MANUAL_REVIEW, belum tersedia di sini).

Tawaran harus `OFFERED` (bukan `GENERATED`/sudah direspons/`EXPIRED`) dan
`restructure_group_id` harus milik `cust_id` yang sama.

**Eksekusi kontrak baru TIDAK terjadi di sini** — kalau `response=ACCEPTED`,
sistem core banking terpisah (`app/core-banking/`, jalankan
`python originator.py`) yang memantau `offer_status='ACCEPTED'` dan
mencairkan kontrak baru secara independen.
""",
    responses={
        403: {"description": "restructure_group_id ini bukan milik cust_id yang diminta"},
        404: {"description": "cust_id atau restructure_group_id tidak ditemukan"},
        409: {"description": "Tawaran belum OFFERED (masih GENERATED) atau sudah direspons sebelumnya"},
        410: {"description": "Tawaran sudah melewati expiry_date"},
    },
)
def submit_customer_response(
    cust_id: str,
    restructure_group_id: str,
    body: CustomerResponseRequest,
    service: RestructuringService = Depends(get_restructuring_service),
):
    result = service.submit_customer_response(cust_id, restructure_group_id, body.response)
    if not result.ok:
        status_code = _ERROR_CODE_TO_STATUS.get(result.error_code, 400)
        raise HTTPException(status_code=status_code, detail=result.error)

    return CustomerResponseResultSchema(
        restructure_group_id=restructure_group_id,
        cust_id=cust_id,
        response=body.response.upper(),
        message="Respons customer tercatat",
    )

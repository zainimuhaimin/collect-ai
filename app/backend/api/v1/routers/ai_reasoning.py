"""AI Reasoning — hyper-personalization level debitur
(ai-reasoning-api-upgrade-tasks.md). GET/POST TERPISAH (bukan 1 endpoint
serba-guna) supaya kontrak REST-nya jelas: GET tidak pernah memanggil Gemini
dan tidak pernah berbiaya, aman dipanggil setiap Customer Detail dibuka; POST
adalah aksi eksplisit dari klik tombol yang bisa memicu panggilan berbayar.

BELUM ada Depends(get_current_user) di endpoint ini (temuan #15/risiko §10
dokumen — ditunda secara sadar, bukan lupa). Pengaman biaya yang TIDAK
menyentuh pola auth (cache exact-match, guard RUNNING, cap harian) tetap
aktif di AiReasoningService.generate()."""
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_ai_reasoning_service
from schemas.ai_reasoning import AiReasoningResponseSchema
from services.ai_reasoning_service import AiReasoningOutcome, AiReasoningService

router = APIRouter(prefix="/customers", tags=["ai-reasoning"])

_ERROR_STATUS = {
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "RATE_LIMITED": 429,
}
_ERROR_DETAIL = {
    "NOT_FOUND": "cust_id tidak ditemukan",
    "CONFLICT": "Generate lain untuk debitur ini sedang berjalan, tunggu sampai selesai",
    "RATE_LIMITED": "Batas panggilan AI Reasoning harian sudah tercapai",
}


def _to_response(outcome: AiReasoningOutcome) -> AiReasoningResponseSchema:
    if not outcome.ok:
        raise HTTPException(
            status_code=_ERROR_STATUS[outcome.error_code],
            detail=_ERROR_DETAIL[outcome.error_code],
        )
    r = outcome.record
    return AiReasoningResponseSchema(
        status=r.status,
        insufficient_reason=r.insufficient_reason,
        stale=outcome.stale,
        generated_at=r.generated_at.isoformat() if r.generated_at else None,
        prompt_version=r.prompt_version or None,
        model_used=r.model_used,
        summary=r.summary,
        customer_treatment_strategy=r.customer_treatment_strategy,
        key_factors=r.key_factors,
        primary_nba_action=r.primary_nba_action,
        primary_nba_rationale=r.primary_nba_rationale,
        nba_agreement=r.nba_agreement,
        per_contract_focus=r.per_contract_focus,
        consistency_note=r.consistency_note,
        analyzed_contract_nos=r.analyzed_contract_nos,
    )


@router.get(
    "/{cust_id}/ai-reasoning",
    response_model=AiReasoningResponseSchema,
    summary="Baca hasil AI Reasoning ter-cache (tidak pernah memanggil Gemini)",
    description="Selalu 200 — status di body membedakan NONE (belum pernah digenerate) / "
    "DISABLED (fitur mati, AI_REASONING_ENABLED=false) / OK / FALLBACK / FAILED / "
    "INSUFFICIENT_DATA. `stale=true` kalau hasil ini dihitung dari komposisi kontrak yang "
    "sudah berubah sejak digenerate (skor baru/kontrak baru/kontrak ditutup) — frontend tetap "
    "menampilkannya (lebih baik hasil basi yang ditandai daripada kosong tiba-tiba), tombol "
    "Generate tetap tersedia untuk memperbarui.",
    responses={404: {"description": "cust_id tidak ditemukan"}},
)
def get_ai_reasoning(cust_id: str, service: AiReasoningService = Depends(get_ai_reasoning_service)):
    return _to_response(service.get_status(cust_id))


@router.post(
    "/{cust_id}/ai-reasoning",
    response_model=AiReasoningResponseSchema,
    summary="Generate AI Reasoning untuk 1 debitur (grain DEBITUR, bukan kontrak)",
    description="Merekonsiliasi SEMUA kontrak aktif debitur ini jadi satu strategi penanganan "
    "(ai-reasoning-api-upgrade-tasks.md §1). Idempotent secara efek: kalau cache masih valid "
    "untuk komposisi kontrak SAAT INI, langsung mengembalikan cache tanpa memanggil Gemini lagi. "
    "409 kalau ada generate lain untuk debitur ini yang masih berjalan (guard konkurensi "
    "berbasis baris DB, tahan multi-worker) — BUKAN error, klien boleh retry setelah beberapa saat. "
    "429 kalau batas panggilan harian tercapai. Timeout klien untuk route ini WAJIB di-override "
    "ke ~30 detik (lebih lama dari default 10 detik global) — panggilan Gemini butuh waktu.",
    responses={
        404: {"description": "cust_id tidak ditemukan"},
        409: {"description": "Generate lain untuk debitur ini sedang berjalan"},
        429: {"description": "Batas panggilan AI Reasoning harian tercapai"},
    },
)
def generate_ai_reasoning(cust_id: str, service: AiReasoningService = Depends(get_ai_reasoning_service)):
    return _to_response(service.generate(cust_id))

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from core.config import settings
from core.dependencies import (
    get_ai_intelligence_sync_service,
    get_ai_reasoning_repository,
    get_current_user,
    get_governance_service,
)
from domain.models import CbsWeight, User
from repositories.interfaces import IAiReasoningRepository
from schemas.ai_intelligence_sync import SyncStartResponse, SyncStatusResponse
from schemas.governance import (
    AiReasoningHealthSchema,
    CbsWeightSchema,
    LlmSystemPromptSchema,
    ModelConfigResponse,
    ModelHealthSchema,
    OperationalLogEntrySchema,
    ScoringModelHealthSchema,
)
from services.ai_intelligence_sync_service import AiIntelligenceSyncService
from services.ai_reasoning_prompt import PROMPT_VERSION, build_instruction
from services.governance_service import GovernanceService

router = APIRouter(prefix="/ai-intelligence", tags=["ai-intelligence"])


def _build_ai_reasoning_health_schema(ai_reasoning_repo: IAiReasoningRepository) -> AiReasoningHealthSchema:
    snapshot = ai_reasoning_repo.get_health_snapshot()
    available = settings.ai_reasoning_enabled and snapshot.total_7d > 0
    if not settings.ai_reasoning_enabled:
        note = "Fitur AI Reasoning belum dinyalakan (AI_REASONING_ENABLED=false)."
    elif snapshot.total_7d == 0:
        note = "Belum ada aktivitas generate AI Reasoning dalam 7 hari terakhir."
    else:
        ok_count = round(snapshot.success_rate_7d * snapshot.total_7d)
        note = f"{ok_count}/{snapshot.total_7d} generate dalam 7 hari terakhir berhasil (OK/FALLBACK)."
    return AiReasoningHealthSchema(
        available=available,
        note=note,
        last_generated_at=snapshot.last_generated_at.isoformat() if snapshot.last_generated_at else None,
        total_7d=snapshot.total_7d,
        success_rate_7d=snapshot.success_rate_7d,
    )


def _build_model_health_schema(
    service: GovernanceService, ai_reasoning_repo: IAiReasoningRepository
) -> ModelHealthSchema:
    health = service.get_model_health()
    scoring_model = None
    if health:
        scoring_model = ScoringModelHealthSchema(
            run_date=health.run_date.isoformat() if health.run_date else None,
            auc=health.auc,
            calibration_gap=health.calibration_gap,
            n_critical_drift=health.n_critical_drift,
            n_warning_drift=health.n_warning_drift,
            retrain_triggered=health.retrain_triggered,
            champion_version=health.champion_version,
        )
    return ModelHealthSchema(
        scoring_model=scoring_model,
        ai_reasoning=_build_ai_reasoning_health_schema(ai_reasoning_repo),
    )


@router.get(
    "/model-config",
    response_model=ModelConfigResponse,
    summary="Konfigurasi AI Intelligence — Bobot CBS + Model Health (fase 1)",
    description="""
TASK-F fase 1 SAJA: Bobot CBS (`model_governance_config`, seed dari
`app/machine-learning/config/settings.py` kalau tabel masih kosong) + Model
Health gabungan (scoring model dari `model_monitoring_log`, AI Reasoning
masih placeholder karena `ai_reasoning_output` belum dibangun).

**Risk & Sub-model Threshold** dan **Restructuring Policy** SENGAJA tidak ada
di sini — dihapus dari scope fase ini (lihat frontend-layout-upgrade-tasks.md
TASK-F).
""",
)
def get_model_config(
    service: GovernanceService = Depends(get_governance_service),
    ai_reasoning_repo: IAiReasoningRepository = Depends(get_ai_reasoning_repository),
):
    weights = service.get_cbs_weights()
    return ModelConfigResponse(
        cbs_weights=[CbsWeightSchema(label=w.label, weight=w.weight, description=w.description) for w in weights],
        model_health=_build_model_health_schema(service, ai_reasoning_repo),
    )


@router.get(
    "/llm-system-prompt",
    response_model=LlmSystemPromptSchema,
    summary="Teks system instruction yang dikirim ke Gemini (AI Reasoning)",
    description="""
Teks persis yang dikirim sebagai `system_instruction` di setiap panggilan
Gemini untuk fitur AI Reasoning (lihat `services/ai_reasoning_prompt.py::build_instruction()`
dan `ai-reasoning-prompt-spec.md` di root repo untuk kontrak lengkapnya).

**Read-only untuk saat ini** — belum ada `config_key` di `model_governance_config`
untuk prompt ini, jadi belum bisa diedit lewat UI tanpa deploy kode baru.
""",
)
def get_llm_system_prompt():
    return LlmSystemPromptSchema(prompt_version=PROMPT_VERSION, system_instruction=build_instruction())


@router.put(
    "/weighting-parameters",
    response_model=List[CbsWeightSchema],
    summary="Simpan Bobot CBS baru",
    description="Body: array 4 bobot `{label, weight, description}` — `label` harus cocok dengan "
    "yang dikembalikan GET /model-config. `sum(weight)` HARUS = 100 (toleransi ±0.01). Menulis ke "
    "`model_governance_config` + insert audit `WEIGHTING_UPDATE`. Tidak ada gate role (RBAC ditunda, "
    "lihat TASK-A) — `Depends(get_current_user)` di sini hanya untuk audit trail.",
    responses={400: {"description": "sum(weight) != 100"}},
)
def update_weighting_parameters(
    body: List[CbsWeightSchema],
    service: GovernanceService = Depends(get_governance_service),
    current_user: User = Depends(get_current_user),
):
    weights = [CbsWeight(label=w.label, weight=w.weight, description=w.description) for w in body]
    result = service.update_weights(weights, current_user.username)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error)
    return [CbsWeightSchema(label=w.label, weight=w.weight, description=w.description) for w in result.weights]


@router.get(
    "/operational-log",
    response_model=List[OperationalLogEntrySchema],
    summary="Audit log perubahan konfigurasi AI Intelligence",
    description="Terbaru dulu, dibatasi 5 baris (widget sekilas, bukan log viewer — tidak ada "
    "pagination by design). `status` selalu 'Success' untuk saat ini — backend ini tidak punya "
    "jalur kegagalan setelah validasi (400) lolos.",
)
def get_operational_log(service: GovernanceService = Depends(get_governance_service)):
    entries = service.list_operational_log()
    return [
        OperationalLogEntrySchema(timestamp=e.timestamp.isoformat(), action=e.action, user=e.user, status=e.status)
        for e in entries
    ]


# ── Sync AI Intelligence: training-if-missing + scoring (background job) ──


@router.post(
    "/sync",
    response_model=SyncStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger training (kalau champion belum ada) + scoring semua model type",
    description="""
Untuk tiap model_type (`recovery`/`self_cure`/`roll_forward`/`ptp_success`)
yang BELUM punya champion (dicek dari `app/machine-learning/models/registry.json`),
latih dulu (subprocess `pipelines/train_*.py`) sebelum menjalankan
`pipelines/daily_scoring.py` (1 kali, menghasilkan ke-4 skor sekaligus).
Berjalan di background thread — endpoint ini langsung return `202` tanpa
menunggu selesai, poll `GET /ai-intelligence/sync/status` untuk progress.

Tidak ada gate role (siapa saja yang login boleh memicu). Hanya 1 job boleh
jalan bersamaan — panggilan kedua saat masih `running` -> `409`, TIDAK
di-antre/queue.
""",
    responses={409: {"description": "Sync lain sedang berjalan"}},
)
def start_ai_intelligence_sync(
    service: AiIntelligenceSyncService = Depends(get_ai_intelligence_sync_service),
    current_user: User = Depends(get_current_user),
):
    started, job_id_or_error = service.start_sync()
    if not started:
        raise HTTPException(status_code=409, detail=job_id_or_error)
    return SyncStartResponse(job_id=job_id_or_error, status="running")


@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    summary="Status job Sync AI Intelligence (training + scoring) + kapan terakhir di-scoring",
    description="`last_scored_at` dihitung REAL-TIME (`MAX(updated_at)` di `ai_intelligence_output`) "
    "tiap panggilan — independen dari status job, ini yang membackup label semacam "
    "\"Terakhir di-scoring: ...\" di frontend biarpun belum pernah ada job Sync yang jalan lewat "
    "endpoint ini sama sekali (mis. scoring dijalankan manual di luar backend).",
)
def get_ai_intelligence_sync_status(
    service: AiIntelligenceSyncService = Depends(get_ai_intelligence_sync_service),
):
    return SyncStatusResponse(**service.get_status())

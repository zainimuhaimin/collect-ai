"""Business logic AI Reasoning (ai-reasoning-api-upgrade-tasks.md). Router
TIDAK PERNAH tahu soal HTTPException — service mengembalikan AiReasoningOutcome
dengan error_code, router yang menerjemahkannya jadi status HTTP (Catatan #1
backend-architecture-tasks.md, pola yang sama dengan RestructuringGroupService)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from core.config import settings
from domain.models import AiReasoningRecord
from repositories.interfaces import IAiReasoningRepository, IContractRepository, ICustomerRepository
from schemas.ai_reasoning import GeminiReasoningOutputSchema
from services.ai_reasoning_gate import data_sufficiency
from services.ai_reasoning_payload import available_models, build_payload, compute_source_signature
from services.ai_reasoning_prompt import NBA_ACTIONS, PROMPT_VERSION, build_instruction, build_response_schema, parse_response_text
from services.gemini_client import GeminiClient, GeminiError

_CACHE_HIT_STATUSES = ("OK", "FALLBACK")


@dataclass
class AiReasoningOutcome:
    """ok=False HANYA untuk kasus yang benar-benar HTTP-worthy (404/409/429) —
    semua kondisi bisnis lain (DISABLED, belum pernah digenerate,
    INSUFFICIENT_DATA, FALLBACK) tetap ok=True dengan `status` di dalam
    `record`, supaya endpoint tetap 200 dan frontend merender state yang
    sesuai (lihat §8.2 dokumen: INSUFFICIENT_DATA bukan error)."""
    ok: bool
    record: Optional[AiReasoningRecord] = None
    stale: bool = False
    error_code: Optional[str] = None   # NOT_FOUND | CONFLICT | RATE_LIMITED


def _placeholder(cust_id: str, status: str) -> AiReasoningRecord:
    return AiReasoningRecord(cust_id=cust_id, source_signature="", prompt_version=PROMPT_VERSION, status=status)


def _error_code_for(exc: Exception) -> str:
    if isinstance(exc, GeminiError):
        return f"gemini_{exc.kind}"
    if isinstance(exc, ValidationError):
        return "invalid_llm_output"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_llm_json"
    return "unknown"


class AiReasoningService:
    def __init__(
        self,
        customer_repository: ICustomerRepository,
        contract_repository: IContractRepository,
        ai_reasoning_repository: IAiReasoningRepository,
        gemini_client: Optional[GeminiClient] = None,
    ):
        self._customers = customer_repository
        self._contracts = contract_repository
        self._ai_reasoning = ai_reasoning_repository
        self._gemini = gemini_client

    # ── GET /customers/{cust_id}/ai-reasoning ──────────────────────────

    def get_status(self, cust_id: str) -> AiReasoningOutcome:
        if not self._customers.exists(cust_id):
            return AiReasoningOutcome(ok=False, error_code="NOT_FOUND")
        if not settings.ai_reasoning_enabled:
            return AiReasoningOutcome(ok=True, record=_placeholder(cust_id, "DISABLED"))

        latest = self._ai_reasoning.get_latest(cust_id, PROMPT_VERSION)
        if latest is None:
            return AiReasoningOutcome(ok=True, record=_placeholder(cust_id, "NONE"))

        active_contracts = self._contracts.list_active_contracts_for_customer(cust_id)
        current_signature = compute_source_signature(active_contracts)
        stale = latest.source_signature != current_signature and latest.status in _CACHE_HIT_STATUSES
        return AiReasoningOutcome(ok=True, record=latest, stale=stale)

    # ── POST /customers/{cust_id}/ai-reasoning ─────────────────────────

    def generate(self, cust_id: str, force: bool = False) -> AiReasoningOutcome:
        if not self._customers.exists(cust_id):
            return AiReasoningOutcome(ok=False, error_code="NOT_FOUND")
        if not settings.ai_reasoning_enabled:
            return AiReasoningOutcome(ok=True, record=_placeholder(cust_id, "DISABLED"))

        active_contracts = self._contracts.list_active_contracts_for_customer(cust_id)
        signature = compute_source_signature(active_contracts)
        contract_nos = [c.contract_no for c in active_contracts]

        if not force:
            cached = self._ai_reasoning.get_cached(cust_id, signature, PROMPT_VERSION)
            if cached is not None and cached.status in _CACHE_HIT_STATUSES:
                return AiReasoningOutcome(ok=True, record=cached, stale=False)

        if self._ai_reasoning.count_generated_today() >= settings.ai_reasoning_daily_call_limit:
            return AiReasoningOutcome(ok=False, error_code="RATE_LIMITED")

        if not self._ai_reasoning.try_claim_running(cust_id, signature, PROMPT_VERSION):
            return AiReasoningOutcome(ok=False, error_code="CONFLICT")

        behavioral = self._customers.get_behavioral_raw(cust_id)
        sufficient, reason = data_sufficiency(behavioral, active_contracts)
        if not sufficient:
            record = AiReasoningRecord(
                cust_id=cust_id, source_signature=signature, prompt_version=PROMPT_VERSION,
                status="INSUFFICIENT_DATA", insufficient_reason=reason,
                analyzed_contract_nos=contract_nos,
            )
            self._ai_reasoning.save_result(record)
            self._log_audit(cust_id, record.status, {"reason": reason})
            return AiReasoningOutcome(ok=True, record=record)

        payload = build_payload(cust_id, behavioral, active_contracts)
        payload_bytes = len(json.dumps(payload, default=str).encode("utf-8"))

        try:
            if self._gemini is None:
                raise GeminiError("Gemini client belum dikonfigurasi", kind="http")
            result = self._gemini.generate(build_instruction(), payload, build_response_schema())
            parsed = GeminiReasoningOutputSchema.model_validate(parse_response_text(result.text))
            record = AiReasoningRecord(
                cust_id=cust_id, source_signature=signature, prompt_version=PROMPT_VERSION,
                status="OK", model_used=result.model_used, generated_at=datetime.now(),
                summary=parsed.summary,
                customer_treatment_strategy=parsed.customer_treatment_strategy,
                key_factors=parsed.key_factors,
                primary_nba_action=parsed.primary_nba_action,
                primary_nba_rationale=parsed.primary_nba_rationale,
                nba_agreement=parsed.nba_agreement,
                per_contract_focus=[f.model_dump() for f in parsed.per_contract_focus],
                consistency_note=parsed.consistency_note,
                analyzed_contract_nos=contract_nos,
                latency_ms=result.latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                payload_bytes=payload_bytes,
            )
        except (GeminiError, ValidationError, json.JSONDecodeError) as exc:
            record = self._build_fallback_or_failed(cust_id, signature, active_contracts, exc, payload_bytes)

        self._ai_reasoning.save_result(record)
        self._log_audit(cust_id, record.status, {"error_code": record.error_code} if record.error_code else {})
        return AiReasoningOutcome(ok=True, record=record)

    # ── Internal ────────────────────────────────────────────────────────

    def _build_fallback_or_failed(self, cust_id, signature, active_contracts, exc, payload_bytes) -> AiReasoningRecord:
        # Fallback rule-based dari kontrak dengan OTS aktif terbesar — pola
        # yang sama dipakai get_customer_profile() untuk memilih "kontrak
        # utama" (§5 dokumen: template dari risk_segment + nba_recommendation
        # yang SUDAH ADA, bukan LLM baru).
        primary = max(active_contracts, key=lambda c: c.principal_ots + c.interest_ots, default=None)
        contract_nos = [c.contract_no for c in active_contracts]
        error_code = _error_code_for(exc)

        if primary is None or primary.ai_scoring is None:
            return AiReasoningRecord(
                cust_id=cust_id, source_signature=signature, prompt_version=PROMPT_VERSION,
                status="FAILED", error_code=error_code, payload_bytes=payload_bytes,
                analyzed_contract_nos=contract_nos,
            )

        nba = primary.ai_scoring.nba_recommendation
        risk_segment = primary.ai_scoring.risk_segment or "belum diketahui"
        summary = (
            f"[Template otomatis — bukan hasil analisa AI] Kontrak utama debitur ini "
            f"berstatus risiko '{risk_segment}' dengan rekomendasi sistem saat ini: {nba or 'belum ada'}."
        )
        return AiReasoningRecord(
            cust_id=cust_id, source_signature=signature, prompt_version=PROMPT_VERSION,
            status="FALLBACK", error_code=error_code, generated_at=datetime.now(),
            summary=summary,
            customer_treatment_strategy=(
                "Analisa AI tidak tersedia saat ini — gunakan rekomendasi rule-based "
                "per kontrak sebagai acuan sementara, dan koordinasikan manual kalau "
                "debitur ini punya lebih dari satu kontrak."
            ),
            primary_nba_action=nba if nba in NBA_ACTIONS else None,
            consistency_note="Ini template otomatis dari data yang sudah ada, bukan hasil rekonsiliasi AI.",
            analyzed_contract_nos=contract_nos,
            payload_bytes=payload_bytes,
        )

    def _log_audit(self, cust_id: str, status: str, extra: dict) -> None:
        try:
            self._ai_reasoning.log_reasoning_event(cust_id, status, extra)
        except Exception as exc:
            print(f"[ai-reasoning-audit] tidak bisa mencatat untuk {cust_id}: {exc!r}")


def build_gemini_client() -> Optional[GeminiClient]:
    """None kalau ai_reasoning_enabled=False ATAU belum ada key sama sekali —
    generate() tidak akan pernah mencoba memanggilnya karena flag dicek lebih
    dulu, ini murni jaring pengaman kedua."""
    if not settings.ai_reasoning_enabled or not settings.google_ai_studio_api_keys:
        return None
    return GeminiClient(
        api_keys=settings.google_ai_studio_api_keys,
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_key_attempts=settings.ai_reasoning_max_key_rotation_attempts,
    )

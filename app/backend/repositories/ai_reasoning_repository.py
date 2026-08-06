"""Implementasi IAiReasoningRepository berbasis Postgres.

Guard konkurensi (`try_claim_running`) memakai pola INSERT ... ON CONFLICT ...
DO UPDATE ... WHERE yang SAMA dengan
restructuring_offer_repository.py::update_offer_status() — kondisi race-
condition-safe-nya ada DI DALAM statement SQL itu sendiri, bukan cek-lalu-
tulis terpisah di Python."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import AiReasoningHealthSnapshot, AiReasoningRecord
from repositories.interfaces import IAiReasoningRepository

# Baris 'RUNNING' yang lebih tua dari ini dianggap macet (mis. proses backend
# mati di tengah panggilan Gemini) dan boleh diklaim ulang. Nilainya jauh di
# atas worst-case (gemini_timeout_seconds x ai_reasoning_max_key_rotation_attempts
# = 25s x 3 = 75s) supaya tidak pernah menyenggol panggilan yang masih sah.
_STALE_RUNNING_AFTER_SECONDS = 120

_COLUMNS = """
    cust_id, source_signature, prompt_version, status, insufficient_reason,
    model_used, generated_at, summary, customer_treatment_strategy, key_factors,
    primary_nba_action, primary_nba_rationale, nba_agreement, per_contract_focus,
    consistency_note, analyzed_contract_nos, latency_ms, prompt_tokens,
    completion_tokens, total_tokens, error_code, payload_bytes, created_at
"""


def _row_to_record(row) -> AiReasoningRecord:
    return AiReasoningRecord(
        cust_id=row.cust_id,
        source_signature=row.source_signature,
        prompt_version=row.prompt_version,
        status=row.status,
        insufficient_reason=row.insufficient_reason,
        model_used=row.model_used,
        generated_at=row.generated_at,
        summary=row.summary,
        customer_treatment_strategy=row.customer_treatment_strategy,
        key_factors=row.key_factors or [],
        primary_nba_action=row.primary_nba_action,
        primary_nba_rationale=row.primary_nba_rationale,
        nba_agreement=row.nba_agreement,
        per_contract_focus=row.per_contract_focus or [],
        consistency_note=row.consistency_note,
        analyzed_contract_nos=row.analyzed_contract_nos or [],
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        error_code=row.error_code,
        payload_bytes=row.payload_bytes,
        created_at=row.created_at,
    )


class AiReasoningRepository(IAiReasoningRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_cached(
        self, cust_id: str, source_signature: str, prompt_version: str
    ) -> Optional[AiReasoningRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {_COLUMNS} FROM ai_reasoning_output "
                    "WHERE cust_id = :cust_id AND source_signature = :source_signature "
                    "AND prompt_version = :prompt_version"
                ),
                {"cust_id": cust_id, "source_signature": source_signature, "prompt_version": prompt_version},
            ).fetchone()
        return _row_to_record(row) if row else None

    def get_latest(self, cust_id: str, prompt_version: str) -> Optional[AiReasoningRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {_COLUMNS} FROM ai_reasoning_output "
                    "WHERE cust_id = :cust_id AND prompt_version = :prompt_version "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"cust_id": cust_id, "prompt_version": prompt_version},
            ).fetchone()
        return _row_to_record(row) if row else None

    def try_claim_running(self, cust_id: str, source_signature: str, prompt_version: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    "INSERT INTO ai_reasoning_output "
                    "(cust_id, source_signature, prompt_version, status, created_at) "
                    "VALUES (:cust_id, :source_signature, :prompt_version, 'RUNNING', now()) "
                    "ON CONFLICT (cust_id, source_signature, prompt_version) DO UPDATE "
                    "SET status = 'RUNNING', created_at = now() "
                    "WHERE ai_reasoning_output.status != 'RUNNING' "
                    "   OR ai_reasoning_output.created_at < now() - make_interval(secs => :stale_after) "
                    "RETURNING id"
                ),
                {
                    "cust_id": cust_id,
                    "source_signature": source_signature,
                    "prompt_version": prompt_version,
                    "stale_after": _STALE_RUNNING_AFTER_SECONDS,
                },
            )
            claimed = result.fetchone() is not None
        return claimed

    def save_result(self, record: AiReasoningRecord) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ai_reasoning_output SET "
                    "status = :status, insufficient_reason = :insufficient_reason, "
                    "model_used = :model_used, generated_at = :generated_at, "
                    "summary = :summary, customer_treatment_strategy = :customer_treatment_strategy, "
                    "key_factors = CAST(:key_factors AS JSONB), "
                    "primary_nba_action = :primary_nba_action, "
                    "primary_nba_rationale = :primary_nba_rationale, nba_agreement = :nba_agreement, "
                    "per_contract_focus = CAST(:per_contract_focus AS JSONB), "
                    "consistency_note = :consistency_note, "
                    "analyzed_contract_nos = CAST(:analyzed_contract_nos AS JSONB), "
                    "latency_ms = :latency_ms, prompt_tokens = :prompt_tokens, "
                    "completion_tokens = :completion_tokens, total_tokens = :total_tokens, "
                    "error_code = :error_code, payload_bytes = :payload_bytes "
                    "WHERE cust_id = :cust_id AND source_signature = :source_signature "
                    "AND prompt_version = :prompt_version"
                ),
                {
                    "cust_id": record.cust_id,
                    "source_signature": record.source_signature,
                    "prompt_version": record.prompt_version,
                    "status": record.status,
                    "insufficient_reason": record.insufficient_reason,
                    "model_used": record.model_used,
                    "generated_at": record.generated_at,
                    "summary": record.summary,
                    "customer_treatment_strategy": record.customer_treatment_strategy,
                    "key_factors": json.dumps(record.key_factors),
                    "primary_nba_action": record.primary_nba_action,
                    "primary_nba_rationale": record.primary_nba_rationale,
                    "nba_agreement": record.nba_agreement,
                    "per_contract_focus": json.dumps(record.per_contract_focus),
                    "consistency_note": record.consistency_note,
                    "analyzed_contract_nos": json.dumps(record.analyzed_contract_nos),
                    "latency_ms": record.latency_ms,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "total_tokens": record.total_tokens,
                    "error_code": record.error_code,
                    "payload_bytes": record.payload_bytes,
                },
            )

    def count_generated_today(self) -> int:
        with self._engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM ai_reasoning_output "
                        "WHERE created_at::date = CURRENT_DATE AND status != 'RUNNING'"
                    )
                ).scalar_one()
            )

    def get_health_snapshot(self) -> AiReasoningHealthSnapshot:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT MAX(generated_at) AS last_generated_at, "
                    "count(*) FILTER (WHERE created_at >= now() - interval '7 days' AND status != 'RUNNING') AS total_7d, "
                    "count(*) FILTER (WHERE created_at >= now() - interval '7 days' AND status IN ('OK','FALLBACK')) AS ok_7d "
                    "FROM ai_reasoning_output"
                )
            ).fetchone()
        total_7d = int(row.total_7d or 0)
        return AiReasoningHealthSnapshot(
            last_generated_at=row.last_generated_at,
            total_7d=total_7d,
            success_rate_7d=(int(row.ok_7d or 0) / total_7d) if total_7d > 0 else None,
        )

    def log_reasoning_event(self, cust_id: str, status: str, detail: dict) -> None:
        payload = dict(detail or {})
        payload["status"] = status
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO model_governance_audit_log (action, performed_by, detail) "
                        "VALUES ('AI_REASONING_GENERATE', :performed_by, CAST(:detail AS JSONB))"
                    ),
                    {"performed_by": f"system (ai-reasoning:{cust_id})", "detail": json.dumps(payload, default=str)},
                )
        except Exception as exc:
            # Audit adalah efek samping, bukan tujuan generate() — sama
            # prinsipnya dengan ai_intelligence_sync_repository.py::log_sync_event.
            print(f"[ai-reasoning-audit] gagal mencatat untuk {cust_id}: {exc!r}")

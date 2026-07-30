"""Implementasi IAiIntelligenceSyncRepository berbasis Postgres.

Baca `ai_intelligence_output.updated_at` (untuk `last_scored_at` di
GET /ai-intelligence/sync/status), plus tulis jejak tiap job Sync ke
model_governance_audit_log. Job-state yang sedang berjalan
(training/scoring in-progress) tetap murni in-memory — lihat
services/ai_intelligence_sync_service.py."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from repositories.interfaces import IAiIntelligenceSyncRepository


class AiIntelligenceSyncRepository(IAiIntelligenceSyncRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_last_scored_at(self) -> Optional[datetime]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT MAX(updated_at) AS last_scored_at FROM ai_intelligence_output")
            ).fetchone()
        return row.last_scored_at if row else None

    def log_sync_event(self, action: str, status: str, detail: dict) -> None:
        payload = dict(detail or {})
        payload["status"] = status
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO model_governance_audit_log (action, performed_by, detail) "
                        "VALUES (:action, :performed_by, CAST(:detail AS JSONB))"
                    ),
                    {
                        "action": action,
                        # Sync dijalankan oleh job background, bukan atas nama
                        # sesi user tertentu (service-nya tidak punya akses ke
                        # current_user) — dicatat sebagai aktor sistem, jangan
                        # ditebak jadi 'admin'.
                        "performed_by": "system (sync)",
                        "detail": json.dumps(payload, default=str),
                    },
                )
        except Exception as exc:
            # Audit adalah efek samping, bukan tujuan job Sync. Kalau insert
            # gagal, job yang sudah sukses TIDAK boleh dilaporkan gagal —
            # cukup dicatat ke stderr supaya tetap terlihat.
            print(f"[sync-audit] gagal mencatat '{action}' ke audit log: {exc!r}")

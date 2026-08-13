"""Implementasi IGovernanceConfigRepository (TASK-F fase 1: Bobot CBS)
berbasis Postgres — tabel BARU milik app/backend/ sendiri
(model_governance_config, model_governance_audit_log; lihat
db/schema_governance.sql), TIDAK overlap dengan tabel app/machine-learning/.

model_monitoring_log (Model Health) TETAP dibaca read-only dari tabel ML yang
sudah ada — repository ini cuma baca baris terbaru, tidak pernah menulis ke
tabel itu (yang menulis adalah pipelines/weekly_mlops.py, di luar backend).
"""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import CbsWeight, GovernanceAuditEntry, ModelHealthSnapshot
from repositories.interfaces import IGovernanceConfigRepository

_CBS_WEIGHTS_CONFIG_KEY = "cbs_weights"

# Operational Log di page AI Intelligence — widget sekilas, bukan log viewer
# tersendiri. Tabel ini bertambah tanpa batas (tiap Sync + tiap perubahan
# bobot menulis baris baru), jadi dibatasi di query (bukan di frontend) supaya
# payload-nya tidak ikut membesar seiring waktu. TIDAK ada pagination by design
# — kalau butuh riwayat lengkap, baca langsung dari
# model_governance_audit_log.
_OPERATIONAL_LOG_LIMIT = 5

# Default/seed pertama kali tabel model_governance_config masih kosong — nilai
# SAMA dengan app/machine-learning/config/settings.py (WEIGHT_PAYMENT_RATE=0.30
# dkk, di sini dalam skala 0..100 bukan 0..1). Sengaja di-hardcode di sini
# (bukan import modul ml/) supaya app/backend/ tidak punya dependency lintas-app
# yang tidak perlu — satu-satunya modul yang memang sengaja dipakai bersama
# backend & ML adalah app/shared/. settings.py TETAP jadi sumber "nilai awal
# yang benar", tabel Postgres ini yang jadi sumber kebenaran operasional
# setelah baris pertama ditulis (lihat frontend-layout-upgrade-tasks.md TASK-F
# "Implikasi arsitektur").
_DEFAULT_CBS_WEIGHTS = [
    {
        "label": "WEIGHT_PAYMENT_RATE",
        "weight": 30.0,
        "description": 'Pengaruh "rajin bayar tepat waktu" ke behavioral_grade.',
    },
    {
        "label": "WEIGHT_PTP_RELIABILITY",
        "weight": 25.0,
        "description": 'Pengaruh "bisa dipegang janji bayarnya".',
    },
    {
        "label": "WEIGHT_INTERACTION",
        "weight": 20.0,
        "description": 'Pengaruh "responsif saat dihubungi".',
    },
    {
        "label": "WEIGHT_DELAY_SCORE",
        "weight": 25.0,
        "description": "Pengaruh tren keterlambatan.",
    },
]


class GovernanceConfigRepository(IGovernanceConfigRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_cbs_weights(self) -> List[CbsWeight]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_value FROM model_governance_config WHERE config_key = :k"),
                {"k": _CBS_WEIGHTS_CONFIG_KEY},
            ).fetchone()

            if row is None:
                # Baris belum pernah ditulis -> seed sekali dari default, supaya
                # panggilan berikutnya (termasuk GET lagi) baca dari Postgres,
                # bukan diam-diam mengembalikan konstanta Python tiap kali.
                conn.execute(
                    text(
                        "INSERT INTO model_governance_config (config_key, config_value) "
                        "VALUES (:k, CAST(:v AS JSONB)) ON CONFLICT (config_key) DO NOTHING"
                    ),
                    {"k": _CBS_WEIGHTS_CONFIG_KEY, "v": json.dumps(_DEFAULT_CBS_WEIGHTS)},
                )
                conn.commit()
                weights_raw = _DEFAULT_CBS_WEIGHTS
            else:
                weights_raw = row.config_value

        return [CbsWeight(label=w["label"], weight=float(w["weight"]), description=w["description"]) for w in weights_raw]

    def save_cbs_weights(self, weights: List[CbsWeight], performed_by: Optional[str]) -> List[CbsWeight]:
        payload = [{"label": w.label, "weight": w.weight, "description": w.description} for w in weights]
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO model_governance_config (config_key, config_value, updated_at) "
                    "VALUES (:k, CAST(:v AS JSONB), now()) "
                    "ON CONFLICT (config_key) DO UPDATE SET config_value = CAST(:v AS JSONB), updated_at = now()"
                ),
                {"k": _CBS_WEIGHTS_CONFIG_KEY, "v": json.dumps(payload)},
            )
            conn.execute(
                text(
                    "INSERT INTO model_governance_audit_log (action, performed_by, detail) "
                    "VALUES ('WEIGHTING_UPDATE', :performed_by, CAST(:detail AS JSONB))"
                ),
                {"performed_by": performed_by, "detail": json.dumps(payload)},
            )
        return weights

    def get_model_health(self) -> Optional[ModelHealthSnapshot]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT run_date, auc, calibration_gap, n_critical_drift, n_warning_drift, "
                    "retrain_triggered, champion_version FROM model_monitoring_log "
                    "ORDER BY run_date DESC, created_at DESC LIMIT 1"
                )
            ).fetchone()
        if row is None:
            return None
        return ModelHealthSnapshot(
            run_date=row.run_date,
            auc=float(row.auc) if row.auc is not None else None,
            calibration_gap=float(row.calibration_gap) if row.calibration_gap is not None else None,
            n_critical_drift=int(row.n_critical_drift or 0),
            n_warning_drift=int(row.n_warning_drift or 0),
            retrain_triggered=bool(row.retrain_triggered or False),
            champion_version=row.champion_version,
        )

    def list_operational_log(self) -> List[GovernanceAuditEntry]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT action, performed_by, performed_at, detail->>'status' AS status "
                    "FROM model_governance_audit_log ORDER BY performed_at DESC LIMIT :limit"
                ),
                {"limit": _OPERATIONAL_LOG_LIMIT},
            ).fetchall()
        return [
            GovernanceAuditEntry(
                timestamp=r.performed_at,
                action=r.action,
                user=r.performed_by,
                # Job Sync menuliskan status sebenarnya (Success/Failed) ke
                # dalam `detail`; entri lain (mis. WEIGHTING_UPDATE) hanya
                # ditulis setelah operasinya commit, jadi default "Success"
                # untuk baris tanpa field itu memang benar.
                status=r.status or "Success",
            )
            for r in rows
        ]

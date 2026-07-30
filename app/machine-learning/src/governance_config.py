"""Baca Bobot CBS dari `model_governance_config` — tabel milik app/backend/
(lihat app/backend/db/schema_governance.sql, diisi lewat
PUT /ai-intelligence/weighting-parameters), supaya slider di halaman AI
Intelligence benar-benar mengubah cara CBS dihitung, bukan cuma tersimpan
tanpa efek ke pipeline.

`config/settings.py` (WEIGHT_PAYMENT_RATE dkk) TETAP jadi fallback kalau
tabel/baris belum ada atau DB tidak bisa diakses (mis. unit test tanpa DB,
atau instalasi baru sebelum backend pernah dijalankan sekali) — lihat
frontend-layout-upgrade-tasks.md TASK-F "Implikasi arsitektur".
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    DB_URL,
    WEIGHT_PAYMENT_RATE,
    WEIGHT_PTP_RELIABILITY,
    WEIGHT_INTERACTION,
    WEIGHT_DELAY_SCORE,
)

logger = logging.getLogger(__name__)

_CBS_WEIGHTS_CONFIG_KEY = "cbs_weights"

# Sama seperti _DEFAULT_CBS_WEIGHTS di app/backend/repositories/governance_repository.py
# (dalam skala 0..1 di sini, backend menyimpan dalam skala 0..100/persen).
_SETTINGS_DEFAULTS = {
    "WEIGHT_PAYMENT_RATE": WEIGHT_PAYMENT_RATE,
    "WEIGHT_PTP_RELIABILITY": WEIGHT_PTP_RELIABILITY,
    "WEIGHT_INTERACTION": WEIGHT_INTERACTION,
    "WEIGHT_DELAY_SCORE": WEIGHT_DELAY_SCORE,
}


def get_cbs_weights() -> dict:
    """Return dict {label: weight_decimal_0_to_1}, ke-4 label SELALU ada.

    Kegagalan apapun (tabel belum ada, DB tidak bisa diakses, baris cuma
    berisi sebagian label) jatuh balik ke default settings.py per-label —
    caller tidak perlu tahu/peduli sumbernya dari mana, dan pipeline tidak
    pernah gagal gara-gara governance config tidak tersedia.
    """
    weights = dict(_SETTINGS_DEFAULTS)
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(DB_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_value FROM model_governance_config WHERE config_key = :k"),
                {"k": _CBS_WEIGHTS_CONFIG_KEY},
            ).fetchone()

        if row is not None:
            raw = row.config_value
            if isinstance(raw, str):
                raw = json.loads(raw)
            for item in raw:
                label = item.get("label")
                if label in weights and item.get("weight") is not None:
                    weights[label] = float(item["weight"]) / 100.0
    except Exception:
        logger.warning(
            "Gagal baca model_governance_config.cbs_weights, pakai default settings.py",
            exc_info=True,
        )

    return weights

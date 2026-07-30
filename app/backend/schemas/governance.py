from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CbsWeightSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "WEIGHT_PAYMENT_RATE",
                "weight": 30.0,
                "description": 'Pengaruh "rajin bayar tepat waktu" ke behavioral_grade.',
            }
        }
    )

    label: str = Field(description="Key stabil, cocok dengan app/machine-learning/config/settings.py (mis. WEIGHT_PAYMENT_RATE)")
    weight: float = Field(description="0..100 (persen) — total ke-4 bobot HARUS = 100")
    description: str


class ScoringModelHealthSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_date": "2026-07-21",
                "auc": None,
                "calibration_gap": None,
                "n_critical_drift": 9,
                "n_warning_drift": 5,
                "retrain_triggered": False,
                "champion_version": "v1",
            }
        }
    )

    run_date: Optional[str]
    auc: Optional[float]
    calibration_gap: Optional[float]
    n_critical_drift: int
    n_warning_drift: int
    retrain_triggered: bool
    champion_version: Optional[str]


class AiReasoningHealthPlaceholder(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "available": False,
                "note": "Menunggu ai_reasoning_output — lihat ai-reasoning-api-upgrade-tasks.md",
            }
        }
    )

    available: bool = False
    note: str = "Menunggu ai_reasoning_output — lihat ai-reasoning-api-upgrade-tasks.md"


class ModelHealthSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scoring_model": {
                    "run_date": "2026-07-21",
                    "auc": None,
                    "calibration_gap": None,
                    "n_critical_drift": 9,
                    "n_warning_drift": 5,
                    "retrain_triggered": False,
                    "champion_version": "v1",
                },
                "ai_reasoning": {
                    "available": False,
                    "note": "Menunggu ai_reasoning_output — lihat ai-reasoning-api-upgrade-tasks.md",
                },
            }
        }
    )

    scoring_model: Optional[ScoringModelHealthSchema] = Field(
        description="None kalau model_monitoring_log belum pernah ada baris sama sekali"
    )
    ai_reasoning: AiReasoningHealthPlaceholder = Field(
        description="Placeholder — tabel ai_reasoning_output belum dibangun, di luar scope TASK-F fase 1"
    )


class ModelConfigResponse(BaseModel):
    """GET /ai-intelligence/model-config — TASK-F fase 1 SAJA (Bobot CBS +
    Model Health). Risk & Sub-model Threshold dan Restructuring Policy
    SENGAJA tidak ada di sini — lihat frontend-layout-upgrade-tasks.md TASK-F
    ("DIHAPUS dari scope")."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cbs_weights": [
                    {
                        "label": "WEIGHT_PAYMENT_RATE",
                        "weight": 30.0,
                        "description": 'Pengaruh "rajin bayar tepat waktu" ke behavioral_grade.',
                    }
                ],
                "model_health": {
                    "scoring_model": {
                        "run_date": "2026-07-21",
                        "auc": None,
                        "calibration_gap": None,
                        "n_critical_drift": 9,
                        "n_warning_drift": 5,
                        "retrain_triggered": False,
                        "champion_version": "v1",
                    },
                    "ai_reasoning": {
                        "available": False,
                        "note": "Menunggu ai_reasoning_output — lihat ai-reasoning-api-upgrade-tasks.md",
                    },
                },
            }
        }
    )

    cbs_weights: List[CbsWeightSchema]
    model_health: ModelHealthSchema


class OperationalLogEntrySchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-07-21T17:07:29",
                "action": "WEIGHTING_UPDATE",
                "user": "admin",
                "status": "Success",
            }
        }
    )

    timestamp: str
    action: str
    user: Optional[str]
    status: str = "Success"

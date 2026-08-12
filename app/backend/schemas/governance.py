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


class AiReasoningHealthSchema(BaseModel):
    """`ai_reasoning_output` sudah dibangun — ini bukan placeholder lagi.
    `available` = fitur menyala (AI_REASONING_ENABLED=true) DAN sudah pernah
    ada minimal 1 hasil non-RUNNING dalam 7 hari terakhir. `success_rate_7d`
    None kalau belum ada aktivitas sama sekali dalam 7 hari (bukan 0% — beda
    makna, sama prinsipnya dengan kenapa payload AI Reasoning membedakan
    'tidak ada data' dari '0')."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "available": True,
                "note": "7/9 generate dalam 7 hari terakhir berhasil (OK/FALLBACK).",
                "last_generated_at": "2026-08-05T10:00:00",
                "total_7d": 9,
                "success_rate_7d": 0.7778,
            }
        }
    )

    available: bool
    note: str
    last_generated_at: Optional[str] = None
    total_7d: int = 0
    success_rate_7d: Optional[float] = None


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
                    "available": True,
                    "note": "7/9 generate dalam 7 hari terakhir berhasil (OK/FALLBACK).",
                    "last_generated_at": "2026-08-05T10:00:00",
                    "total_7d": 9,
                    "success_rate_7d": 0.7778,
                },
            }
        }
    )

    scoring_model: Optional[ScoringModelHealthSchema] = Field(
        description="None kalau model_monitoring_log belum pernah ada baris sama sekali"
    )
    ai_reasoning: AiReasoningHealthSchema = Field(
        description="Kesehatan fitur AI Reasoning — lihat AiReasoningHealthSchema"
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
                        "available": True,
                        "note": "7/9 generate dalam 7 hari terakhir berhasil (OK/FALLBACK).",
                        "last_generated_at": "2026-08-05T10:00:00",
                        "total_7d": 9,
                        "success_rate_7d": 0.7778,
                    },
                },
            }
        }
    )

    cbs_weights: List[CbsWeightSchema]
    model_health: ModelHealthSchema


class LlmSystemPromptSchema(BaseModel):
    """GET /ai-intelligence/llm-system-prompt — teks instruksi persis yang
    dikirim ke Gemini di setiap panggilan AI Reasoning (lihat
    services/ai_reasoning_prompt.py::build_instruction()). Read-only untuk
    saat ini — mengedit prompt lewat UI butuh menyimpannya di
    model_governance_config dulu (belum ada config_key untuk ini), jadi
    endpoint ini sengaja hanya GET."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt_version": "v2",
                "system_instruction": "Anda analis kredit yang membantu petugas collection...",
            }
        }
    )

    prompt_version: str
    system_instruction: str


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

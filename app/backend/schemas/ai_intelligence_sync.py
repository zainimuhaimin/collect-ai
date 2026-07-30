from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SyncStepSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"model_type": "recovery", "action": "train_then_score", "status": "done"},
        }
    )

    model_type: str = Field(description="recovery | self_cure | roll_forward | ptp_success | daily_scoring")
    action: str = Field(
        description="'train_then_score' | 'score_only' untuk 4 model_type sub-model; "
        "'score' untuk langkah daily_scoring gabungan di akhir"
    )
    status: str = Field(description="'pending' | 'running' | 'done' | 'failed'")


class SyncStartResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"job_id": "b6c1e6b2-2f3a-4a3a-9c1a-8f9b6b6b6b6b", "status": "running"},
        }
    )

    job_id: str
    status: str = "running"


class SyncStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "running",
                "started_at": "2026-07-27T10:00:00",
                "finished_at": None,
                "steps": [
                    {"model_type": "recovery", "action": "train_then_score", "status": "done"},
                    {"model_type": "self_cure", "action": "train_then_score", "status": "running"},
                    {"model_type": "roll_forward", "action": "train_then_score", "status": "pending"},
                    {"model_type": "ptp_success", "action": "train_then_score", "status": "pending"},
                    {"model_type": "daily_scoring", "action": "score", "status": "pending"},
                ],
                "last_scored_at": "2026-07-26T23:10:04",
                "error": None,
            }
        }
    )

    status: str = Field(description="'idle' | 'running' | 'completed' | 'failed'")
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    steps: List[SyncStepSchema]
    last_scored_at: Optional[str] = Field(
        description="MAX(updated_at) ai_intelligence_output, dihitung REAL-TIME tiap panggilan — "
        "independen dari status job (tetap terisi walau tidak ada job yang sedang/pernah berjalan "
        "lewat endpoint ini)"
    )
    error: Optional[str] = Field(description="Detail error (termasuk tail stderr) kalau status=='failed'")

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class DpdBucketSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"bucket": "C1", "settled": 68, "active_ptp": 0, "broken": 5, "total": 73}}
    )

    bucket: str = Field(description="C0 (1-30) | C1 (31-60) | C2 (61-90) | C3+ (90+); dpd_current=0 tidak masuk bucket")
    settled: int
    active_ptp: int
    broken: int
    total: int


class ChannelEfficiencySchema(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"treatment_type": "WA", "contact_success_rate": 0.88}})

    treatment_type: str
    contact_success_rate: float = Field(description="0..1 — baris pertama (list diurutkan DESC) = channel paling responsif")


class DashboardSummarySchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kpis": {
                    "total_outstanding": 7843298735.03,
                    "active_delinquent_accounts": 446,
                    "ptp_keep_rate": 0.82,
                    "manual_review_pending": 740,
                },
                "dpd_buckets": [{"bucket": "C0", "settled": 188, "active_ptp": 70, "broken": 0, "total": 258}],
                "contactability_funnel": {"total_attempts": 1449, "contacted": 1238, "ptp_obtained": 358},
                "channel_efficiency": [{"treatment_type": "WA", "contact_success_rate": 0.88}],
                "restructuring_pipeline_snapshot": {
                    "GENERATED": 740,
                    "OFFERED": 5,
                    "ACCEPTED": 1,
                    "REJECTED": 0,
                    "EXPIRED": 0,
                },
                "risk_segment_distribution": {"Cannot Pay": 7, "Self-cure": 13, "Won't Pay": 68, "Can Pay": 633},
                "sync_note": "Data terakhir disinkronkan: 21 Jul 2026 17:07",
            }
        }
    )

    kpis: Dict[str, float] = Field(
        description="total_outstanding, active_delinquent_accounts, ptp_keep_rate, manual_review_pending "
        "— lihat DashboardRepository untuk definisi tiap angka. ptp_keep_rate = KEPT / (KEPT + BROKEN) dari "
        "lkp_interaction.ptp_status, trailing 30 hari relatif ke action_date terbaru (PTP = promise-to-pay)"
    )
    dpd_buckets: List[DpdBucketSchema]
    contactability_funnel: Dict[str, int] = Field(description="total_attempts -> contacted -> ptp_obtained")
    channel_efficiency: List[ChannelEfficiencySchema]
    restructuring_pipeline_snapshot: Dict[str, int] = Field(
        description="Jumlah offer per offer_status (GENERATED/OFFERED/ACCEPTED/REJECTED/EXPIRED)"
    )
    risk_segment_distribution: Dict[str, int] = Field(
        description="Jumlah kontrak per risk_segment (skor TERBARU per kontrak), nilai apa adanya dari DB"
    )
    sync_note: str

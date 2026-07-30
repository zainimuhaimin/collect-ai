from fastapi import APIRouter, Depends

from core.dependencies import get_dashboard_service
from schemas.dashboard import ChannelEfficiencySchema, DashboardSummarySchema, DpdBucketSchema
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummarySchema,
    summary="Ringkasan Dashboard",
    description="""
KPI + DPD Buckets + Contactability Funnel + Channel Efficiency + Restructuring
Pipeline Snapshot + Risk Segment Distribution + sync note, semua dihitung
langsung dari tabel yang sama dipakai app/machine-learning/ (TASK-B).

`broken_ptp_priorities` SENGAJA tidak ada di sini lagi — sudah pindah jadi
filter chip di list Customer & list Contract (lihat tag `customers`/`contracts`).
""",
)
def get_dashboard_summary(service: DashboardService = Depends(get_dashboard_service)):
    summary = service.get_summary()
    return DashboardSummarySchema(
        kpis=summary.kpis,
        dpd_buckets=[
            DpdBucketSchema(bucket=b.bucket, settled=b.settled, active_ptp=b.active_ptp, broken=b.broken, total=b.total)
            for b in summary.dpd_buckets
        ],
        contactability_funnel=summary.contactability_funnel,
        channel_efficiency=[
            ChannelEfficiencySchema(treatment_type=c.treatment_type, contact_success_rate=c.contact_success_rate)
            for c in summary.channel_efficiency
        ],
        restructuring_pipeline_snapshot=summary.restructuring_pipeline_snapshot,
        risk_segment_distribution=summary.risk_segment_distribution,
        sync_note=summary.sync_note,
    )

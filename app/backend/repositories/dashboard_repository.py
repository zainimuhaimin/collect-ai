"""Implementasi IDashboardRepository (TASK-B) — agregat lintas tabel murni
untuk 1 endpoint laporan `GET /dashboard/summary`. Semua angka dihitung
langsung dari tabel yang sama dipakai app/machine-learning/, tidak ada
tabel/materialized view baru untuk ini.

Beberapa pilihan yang TIDAK dispesifikasi presisi di
frontend-layout-upgrade-tasks.md (didokumentasikan di sini, bukan ditebak
diam-diam):

- KPI dipilih 4: total outstanding (kontrak yang belum closed_via_restructure),
  jumlah akun delinquent aktif (dpd_current>=1), PTP keep rate, dan jumlah
  offer restrukturisasi yang masih menunggu approval manual.
- "PTP Keep Rate bulan ini": KEPT / (KEPT + BROKEN) dari lkp_interaction.ptp_status.
  Data bersifat historis/sintetis (batch terakhir bisa beberapa siklus di
  belakang tanggal berjalan), jadi "bulan ini" dihitung relatif ke data, bukan
  ke tanggal sistem. Dua detail yang penting dan pernah salah:
  * Window-nya dihitung dari `promise_date`, BUKAN `action_date`. Yang jatuh
    tempo (dan karena itu bisa dinilai ditepati/tidak) adalah janjinya, bukan
    tanggal janji itu dibuat.
  * Anchor-nya `max(promise_date)` DI ANTARA baris yang sudah resolved, bukan
    max seluruh tabel. Sebuah PTP baru selalu berstatus OPEN sampai
    promise_date-nya lewat, jadi ujung tabel selalu berisi PTP yang belum
    bisa dinilai; anchor ke max global membuat window jatuh seluruhnya di
    daerah OPEN/NULL dan rate-nya permanen 0.
- DPD buckets: C0 1-30 / C1 31-60 / C2 61-90 / C3+ 90+ (dpd_current=0 /lancar
  TIDAK masuk hitungan bucket manapun, sesuai definisi literal di task doc).
  Cross-tab settled/active_ptp/broken pakai ptp_status TERBARU per kontrak:
  OPEN -> active_ptp, BROKEN -> broken, selain itu (NULL/KEPT) -> settled.
- channel_efficiency: breakdown PER channel (treatment_type), diurutkan
  contact_success_rate DESC — baris pertama otomatis "channel paling
  responsif" tanpa perlu field terpisah.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import ChannelEfficiencyRow, DashboardSummary, DpdBucketRow
from repositories.interfaces import IDashboardRepository

_ALL_OFFER_STATUSES = ["GENERATED", "OFFERED", "ACCEPTED", "REJECTED", "EXPIRED"]
_ALL_DPD_BUCKETS = ["C0", "C1", "C2", "C3+"]


class DashboardRepository(IDashboardRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_summary(self) -> DashboardSummary:
        with self._engine.connect() as conn:
            total_outstanding = conn.execute(
                text(
                    "SELECT COALESCE(SUM(COALESCE(prnc_ots,0) + COALESCE(intr_ots,0)), 0) "
                    "FROM contract_snapshot WHERE COALESCE(closed_via_restructure, FALSE) = FALSE"
                )
            ).scalar_one()

            active_delinquent = conn.execute(
                text("SELECT count(*) FROM contract_snapshot WHERE dpd_current >= 1")
            ).scalar_one()

            ptp_row = conn.execute(
                text(
                    "WITH resolved AS ("
                    "  SELECT promise_date, ptp_status FROM lkp_interaction"
                    "  WHERE ptp_status IN ('KEPT','BROKEN') AND promise_date IS NOT NULL"
                    ") "
                    "SELECT count(*) FILTER (WHERE ptp_status = 'KEPT') AS kept, "
                    "count(*) AS total FROM resolved "
                    "WHERE promise_date >= (SELECT max(promise_date) FROM resolved) - INTERVAL '30 days'"
                )
            ).fetchone()
            ptp_keep_rate = (
                float(ptp_row.kept) / float(ptp_row.total)
                if ptp_row and ptp_row.total
                else 0.0
            )

            manual_review_pending = conn.execute(
                text(
                    "SELECT count(*) FROM restructuring_recommendation_output "
                    "WHERE eligibility_tier = 'MANUAL_REVIEW' AND offer_status IN ('GENERATED', 'OFFERED')"
                )
            ).scalar_one()

            bucket_rows = conn.execute(
                text(
                    """
                    WITH latest_ptp AS (
                        SELECT DISTINCT ON (contract_no) contract_no, ptp_status
                        FROM lkp_interaction ORDER BY contract_no, action_date DESC
                    ),
                    bucketed AS (
                        SELECT
                            CASE
                                WHEN cs.dpd_current BETWEEN 1 AND 30 THEN 'C0'
                                WHEN cs.dpd_current BETWEEN 31 AND 60 THEN 'C1'
                                WHEN cs.dpd_current BETWEEN 61 AND 90 THEN 'C2'
                                WHEN cs.dpd_current > 90 THEN 'C3+'
                            END AS bucket,
                            lp.ptp_status AS ptp_status
                        FROM contract_snapshot cs
                        LEFT JOIN latest_ptp lp ON lp.contract_no = cs.contract_no
                        WHERE cs.dpd_current >= 1
                    )
                    SELECT bucket,
                        count(*) FILTER (WHERE ptp_status = 'BROKEN') AS broken,
                        count(*) FILTER (WHERE ptp_status = 'OPEN') AS active_ptp,
                        count(*) FILTER (WHERE ptp_status IS NULL OR ptp_status = 'KEPT') AS settled,
                        count(*) AS total
                    FROM bucketed
                    WHERE bucket IS NOT NULL
                    GROUP BY bucket
                    """
                )
            ).fetchall()

            funnel_row = conn.execute(
                text(
                    "SELECT count(*) AS total_attempts, "
                    "count(*) FILTER (WHERE contact_success_flag) AS contacted, "
                    "count(*) FILTER (WHERE ptp_status IS NOT NULL) AS ptp_obtained "
                    "FROM lkp_interaction"
                )
            ).fetchone()

            channel_rows = conn.execute(
                text(
                    """
                    SELECT treatment_type,
                        count(*) FILTER (WHERE contact_success_flag) AS success,
                        count(*) AS total
                    FROM lkp_interaction
                    WHERE treatment_type IS NOT NULL
                    GROUP BY treatment_type
                    ORDER BY (count(*) FILTER (WHERE contact_success_flag))::float / NULLIF(count(*), 0) DESC
                    """
                )
            ).fetchall()

            pipeline_rows = conn.execute(
                text("SELECT offer_status, count(*) FROM restructuring_recommendation_output GROUP BY offer_status")
            ).fetchall()

            risk_rows = conn.execute(
                text(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (contract_no) contract_no, risk_segment
                        FROM ai_intelligence_output ORDER BY contract_no, scoring_date DESC
                    )
                    SELECT risk_segment, count(*) FROM latest GROUP BY risk_segment
                    """
                )
            ).fetchall()

            last_sync = conn.execute(text("SELECT max(updated_at) FROM ai_intelligence_output")).scalar_one()

        bucket_by_key = {r.bucket: r for r in bucket_rows}
        dpd_buckets = [
            DpdBucketRow(
                bucket=b,
                settled=int(bucket_by_key[b].settled) if b in bucket_by_key else 0,
                active_ptp=int(bucket_by_key[b].active_ptp) if b in bucket_by_key else 0,
                broken=int(bucket_by_key[b].broken) if b in bucket_by_key else 0,
                total=int(bucket_by_key[b].total) if b in bucket_by_key else 0,
            )
            for b in _ALL_DPD_BUCKETS
        ]

        channel_efficiency = [
            ChannelEfficiencyRow(
                treatment_type=r.treatment_type,
                contact_success_rate=(float(r.success) / float(r.total)) if r.total else 0.0,
            )
            for r in channel_rows
        ]

        pipeline_by_status = {r.offer_status: int(r.count) for r in pipeline_rows}
        restructuring_pipeline_snapshot = {s: pipeline_by_status.get(s, 0) for s in _ALL_OFFER_STATUSES}

        risk_segment_distribution = {r.risk_segment: int(r.count) for r in risk_rows if r.risk_segment}

        sync_note = (
            f"Data terakhir disinkronkan: {last_sync.strftime('%d %b %Y %H:%M')}"
            if last_sync
            else "Data terakhir disinkronkan: belum pernah"
        )

        return DashboardSummary(
            kpis={
                "total_outstanding": float(total_outstanding),
                "active_delinquent_accounts": float(active_delinquent),
                "ptp_keep_rate": ptp_keep_rate,
                "manual_review_pending": float(manual_review_pending),
            },
            dpd_buckets=dpd_buckets,
            contactability_funnel={
                "total_attempts": int(funnel_row.total_attempts or 0),
                "contacted": int(funnel_row.contacted or 0),
                "ptp_obtained": int(funnel_row.ptp_obtained or 0),
            },
            channel_efficiency=channel_efficiency,
            restructuring_pipeline_snapshot=restructuring_pipeline_snapshot,
            risk_segment_distribution=risk_segment_distribution,
            sync_note=sync_note,
        )

"""Implementasi IRestructuringOfferRepository berbasis Postgres.

Offer-nya SENDIRI dihasilkan oleh batch ML (pipelines/restructuring_runner.py)
atau endpoint on-demand — repository ini HANYA baca status offer dan
mencatat keputusan customer (accept/reject). Tidak pernah menghitung ulang
angka tawaran (itu murni tugas ml.restructuring_offer_calculator).

TASK-E (frontend-layout-upgrade-tasks.md) menambahkan queue approval
supervisor (list_offers/update_offer_status) — tabel yang dibaca/ditulis
TETAP restructuring_recommendation_output yang sama, plus 1 tabel audit baru
(restructuring_approval_log, lihat db/schema_governance.sql)."""
from __future__ import annotations

import os
import sys
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import RestructuringGroupSummary, RestructuringOfferRecord
from repositories.interfaces import IRestructuringOfferRepository

# Angka risk-adjusted di bawah HARUS memakai asumsi yang sama dengan engine
# yang meloloskan tawarannya — kalau di-hardcode ulang di sini, UI akan
# menampilkan angka yang bertentangan dengan yang lolos guardrail.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from shared.restructuring_offer_calculator import (  # noqa: E402
    RestructurePolicy,
    restructured_recovery_probability,
)

_DISPLAY_POLICY = RestructurePolicy()

_SELECT = """
    SELECT restructure_group_id, cust_id, offer_type, offer_status,
           generated_date, expiry_date, response_date
    FROM restructuring_recommendation_output
    WHERE restructure_group_id = :group_id
"""

# Per-group derived stats for the Round 4 #6 display-only fields, computed from
# data that's ALREADY stored (recovery_score per contract in ai_intelligence_output,
# installment_amount/maturity_date in contract_snapshot) rather than re-running the
# calculator — restructuring_recommendation_output itself never stored recovery_score
# or a per-contract schedule, only the aggregate npv_baseline/npv_restructured.
# Sisa kewajiban dihitung dari JUMLAH CICILAN YANG MASIH TERUTANG
# (total_ots / installment), bukan dari jarak ke maturity_date. Dua alasan:
#  1. Harus cocok dengan effective_remaining_tenor() di shared calculator —
#     itu basis yang dipakai engine saat menghitung & meloloskan tawaran ini.
#     Versi maturity_date rata-rata menaksir 7,3 bulan terlalu rendah pada
#     nasabah menunggak, jadi "total saat ini" akan tampak jauh lebih kecil
#     dari kenyataan dan membuat tawaran seolah menaikkan total bayar.
#  2. Versi lama memakai CURRENT_DATE, sehingga "total saat ini" MENYUSUT tiap
#     hari setelah offer dibuat (offer berlaku 14 hari) — angka pembanding yang
#     bergerak sendiri, membuat manfaat tawaran tampak makin besar tanpa ada
#     yang berubah.
_GROUP_CONTRACT_STATS_CTE = """(
    SELECT
        rgm.restructure_group_id,
        AVG(aio.recovery_score) AS avg_recovery_score,
        SUM(
            COALESCE(cs.installment_amount, 0) *
            GREATEST(
                1,
                ROUND(
                    (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0))
                    / NULLIF(cs.installment_amount, 0)
                )
            )
        ) AS total_remaining_current
    FROM restructuring_group_map rgm
    LEFT JOIN contract_snapshot cs ON cs.contract_no = rgm.contract_no
    LEFT JOIN ai_intelligence_output aio ON aio.contract_no = rgm.contract_no
    GROUP BY rgm.restructure_group_id
)"""


def _row_to_record(row) -> RestructuringOfferRecord:
    return RestructuringOfferRecord(
        restructure_group_id=row.restructure_group_id,
        cust_id=row.cust_id,
        offer_type=row.offer_type,
        offer_status=row.offer_status,
        generated_date=row.generated_date,
        expiry_date=row.expiry_date,
        response_date=row.response_date,
    )


def _row_to_summary(row) -> RestructuringGroupSummary:
    """Dipakai bersama list_offers()/get_offer_summary() — bentuk row-nya SAMA
    (beda hanya jumlah baris), supaya 2 query itu tidak bisa diam-diam
    menghasilkan mapping yang berbeda."""
    npv_restructured = float(row.npv_restructured) if row.npv_restructured is not None else None
    avg_recovery_score = float(row.avg_recovery_score) if row.avg_recovery_score is not None else None
    return RestructuringGroupSummary(
        restructure_group_id=row.restructure_group_id,
        cust_id=row.cust_id,
        contract_nos=list(row.contract_nos or []),
        offer_type=row.offer_type,
        eligibility_tier=row.eligibility_tier,
        eligibility_reasons=row.eligibility_reasons,
        npv_baseline=float(row.npv_baseline) if row.npv_baseline is not None else None,
        npv_restructured=npv_restructured,
        generated_date=row.generated_date,
        offer_status=row.offer_status,
        # Dihitung dari data yang sudah tersimpan (recommended_new_installment/
        # tenor selalu ada; recovery_score & jadwal saat ini butuh join ke
        # ai_intelligence_output/contract_snapshot via restructuring_group_map)
        # — bukan re-run kalkulator, murni proyeksi dari row yang sama.
        # Bukan avg_recovery_score mentah: yang relevan adalah peluang jadwal
        # BARU terbayar, yang justru lebih tinggi karena cicilannya terjangkau
        # — asumsi itu hidup di satu tempat (shared calculator), bukan
        # digandakan di sini. Dengan avg_recovery_score mentah, angka ini akan
        # selalu di bawah npv_baseline dan tampak seperti tawaran yang merugi
        # padahal guardrail meloloskannya.
        npv_restructured_risk_adjusted=(
            round(npv_restructured * restructured_recovery_probability(avg_recovery_score, _DISPLAY_POLICY), 2)
            if npv_restructured is not None and avg_recovery_score is not None
            else None
        ),
        total_remaining_current=(
            float(row.total_remaining_current) if row.total_remaining_current is not None else None
        ),
        total_new_schedule=(
            round(float(row.recommended_new_installment) * float(row.recommended_new_tenor), 2)
            if row.recommended_new_installment is not None and row.recommended_new_tenor is not None
            else None
        ),
    )


class RestructuringOfferRepository(IRestructuringOfferRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_offer(self, restructure_group_id: str) -> Optional[RestructuringOfferRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(text(_SELECT), {"group_id": restructure_group_id}).fetchone()
        return _row_to_record(row) if row else None

    def find_latest_for_customer(self, cust_id: str) -> Optional[RestructuringOfferRecord]:
        # Dipakai GET /customers/{id}/restructuring-options (on-demand assessment)
        # untuk tahu apakah customer ini SUDAH punya group persisted dari batch
        # ML/approval supervisor — kalau ada, frontend butuh restructure_group_id-nya
        # untuk bisa memanggil endpoint customer-response. Kalau tidak ada baris sama
        # sekali, on-demand assessment murni informational (belum ada yang bisa
        # direspons customer).
        query = """
            SELECT restructure_group_id, cust_id, offer_type, offer_status,
                   generated_date, expiry_date, response_date
            FROM restructuring_recommendation_output
            WHERE cust_id = :cust_id
            ORDER BY generated_date DESC
            LIMIT 1
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(query), {"cust_id": cust_id}).fetchone()
        return _row_to_record(row) if row else None

    def record_customer_response(
        self, restructure_group_id: str, response: str, response_date: date
    ) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE restructuring_recommendation_output "
                    "SET offer_status = :status, response_date = :response_date "
                    "WHERE restructure_group_id = :group_id"
                ),
                {"status": response, "response_date": response_date, "group_id": restructure_group_id},
            )
        return result.rowcount > 0

    def list_offers(
        self,
        statuses: List[str],
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RestructuringGroupSummary], int]:
        search_sql = ""
        params = {"statuses": statuses}
        if search:
            search_sql = "AND (rro.restructure_group_id ILIKE :search OR rro.cust_id ILIKE :search)"
            params["search"] = f"%{search}%"

        base_from = """
            FROM restructuring_recommendation_output rro
            JOIN customer_master cm ON cm.cust_id = rro.cust_id
        """
        where_clause = f"WHERE rro.offer_status = ANY(:statuses) {search_sql}"

        with self._engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(DISTINCT rro.restructure_group_id) {base_from} {where_clause}"), params
            ).scalar_one()

            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        rro.restructure_group_id,
                        rro.cust_id,
                        rro.offer_type,
                        rro.eligibility_tier,
                        rro.eligibility_reasons,
                        rro.npv_baseline,
                        rro.npv_restructured,
                        rro.recommended_new_installment,
                        rro.recommended_new_tenor,
                        rro.generated_date,
                        rro.offer_status,
                        gcs.avg_recovery_score,
                        gcs.total_remaining_current,
                        COALESCE(
                            array_agg(rgm.contract_no ORDER BY rgm.contract_no) FILTER (WHERE rgm.contract_no IS NOT NULL),
                            ARRAY[]::varchar[]
                        ) AS contract_nos
                    {base_from}
                    LEFT JOIN restructuring_group_map rgm ON rgm.restructure_group_id = rro.restructure_group_id
                    LEFT JOIN {_GROUP_CONTRACT_STATS_CTE} gcs ON gcs.restructure_group_id = rro.restructure_group_id
                    {where_clause}
                    GROUP BY rro.restructure_group_id, rro.cust_id, rro.offer_type, rro.eligibility_tier,
                             rro.eligibility_reasons, rro.npv_baseline, rro.npv_restructured,
                             rro.recommended_new_installment, rro.recommended_new_tenor,
                             rro.generated_date, rro.offer_status,
                             gcs.avg_recovery_score, gcs.total_remaining_current
                    ORDER BY rro.generated_date DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {**params, "limit": page_size, "offset": (page - 1) * page_size},
            ).fetchall()

        return [_row_to_summary(r) for r in rows], total

    def get_offer_summary(self, restructure_group_id: str) -> Optional[RestructuringGroupSummary]:
        query = f"""
            SELECT
                rro.restructure_group_id,
                rro.cust_id,
                rro.offer_type,
                rro.eligibility_tier,
                rro.eligibility_reasons,
                rro.npv_baseline,
                rro.npv_restructured,
                rro.recommended_new_installment,
                rro.recommended_new_tenor,
                rro.generated_date,
                rro.offer_status,
                gcs.avg_recovery_score,
                gcs.total_remaining_current,
                COALESCE(
                    array_agg(rgm.contract_no ORDER BY rgm.contract_no) FILTER (WHERE rgm.contract_no IS NOT NULL),
                    ARRAY[]::varchar[]
                ) AS contract_nos
            FROM restructuring_recommendation_output rro
            LEFT JOIN restructuring_group_map rgm ON rgm.restructure_group_id = rro.restructure_group_id
            LEFT JOIN {_GROUP_CONTRACT_STATS_CTE} gcs ON gcs.restructure_group_id = rro.restructure_group_id
            WHERE rro.restructure_group_id = :group_id
            GROUP BY rro.restructure_group_id, rro.cust_id, rro.offer_type, rro.eligibility_tier,
                     rro.eligibility_reasons, rro.npv_baseline, rro.npv_restructured,
                     rro.recommended_new_installment, rro.recommended_new_tenor,
                     rro.generated_date, rro.offer_status,
                     gcs.avg_recovery_score, gcs.total_remaining_current
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(query), {"group_id": restructure_group_id}).fetchone()
        return _row_to_summary(row) if row else None

    def update_offer_status(
        self, restructure_group_id: str, new_status: str, action: str, performed_by: Optional[str]
    ) -> bool:
        # Guard "offer_status = 'GENERATED'" ada DI DALAM UPDATE itu sendiri
        # (bukan cek-lalu-update terpisah) — satu-satunya cara aman dari race
        # condition 2 supervisor approve/reject bersamaan. Insert audit HANYA
        # terjadi kalau UPDATE benar-benar mengubah baris (rowcount > 0),
        # 1 transaksi supaya keduanya konsisten (tidak ada audit "hantu" untuk
        # transisi yang sebenarnya gagal).
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE restructuring_recommendation_output "
                    "SET offer_status = :new_status "
                    "WHERE restructure_group_id = :group_id AND offer_status = 'GENERATED'"
                ),
                {"new_status": new_status, "group_id": restructure_group_id},
            )
            if result.rowcount > 0:
                conn.execute(
                    text(
                        "INSERT INTO restructuring_approval_log "
                        "(restructure_group_id, action, performed_by) "
                        "VALUES (:group_id, :action, :performed_by)"
                    ),
                    {"group_id": restructure_group_id, "action": action, "performed_by": performed_by},
                )
        return result.rowcount > 0

"""Implementasi ICustomerRepository berbasis Postgres — DB yang sama dipakai
app/machine-learning/ (satu sumber kebenaran: customer_master +
customer_behavioral_standing)."""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import Customer, CustomerBehavioralRaw, CustomerListRow, CustomerProfile
from repositories.interfaces import ICustomerRepository
from repositories.priority import PRIORITY_CASE_SQL

_SELECT = """
    SELECT
        cm.cust_id,
        cm.cust_name,
        cbs.b_list_status,
        cbs.restructure_count,
        cbs.active_contract_count,
        cbs.behavioral_grade
    FROM customer_master cm
    LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
"""


def _row_to_customer(row) -> Customer:
    # customer_master.cust_name sudah ada & selalu terisi di data saat ini
    # (lihat migrasi TASK-6) — tetap COALESCE ke cust_id sebagai fallback
    # defensif kalau suatu saat ada baris NULL.
    return Customer(
        cust_id=row.cust_id,
        name=row.cust_name or row.cust_id,
        b_list_status=row.b_list_status or "N",
        restructure_count=int(row.restructure_count or 0),
        active_contract_count=int(row.active_contract_count or 0),
        behavioral_grade=row.behavioral_grade or "D",
    )


# ── TASK-C: list Customer dengan filter chip/search/paginasi ────────────
#
# "Primary contract" (khusus filter `dpd_30_plus`, TIDAK lagi diekspos di
# response) = kontrak aktif (belum closed_via_restructure) dengan total_ots
# terbesar — konsep yang SAMA dengan
# ContractRepository.get_primary_contract_for_customer.
#
# `priority` SEKARANG level-Customer, BUKAN dari 1 kontrak yang dipilih
# arbitrer lagi (lihat catatan lama di bawah — sudah diperbaiki): dihitung
# per-kontrak aktif pakai PRIORITY_CASE_SQL yang sama dipakai ContractRepository,
# di-rank numerik (Critical=3 > High=2 > Medium=1), lalu diambil MAX per
# cust_id dan dipetakan balik ke label. Customer tanpa kontrak aktif sama
# sekali default ke 'Medium' (COALESCE priority_rank -> 1), sama seperti
# default branch PRIORITY_CASE_SQL.
_CUSTOMER_LIST_BASE_CTE = f"""
    WITH primary_contract AS (
        SELECT DISTINCT ON (cs.cust_id)
            cs.cust_id,
            cs.dpd_current
        FROM contract_snapshot cs
        WHERE COALESCE(cs.closed_via_restructure, FALSE) = FALSE
        ORDER BY cs.cust_id, (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0)) DESC
    ),
    latest_score AS (
        SELECT DISTINCT ON (contract_no) contract_no, risk_segment
        FROM ai_intelligence_output
        ORDER BY contract_no, scoring_date DESC
    ),
    contract_priority AS (
        SELECT
            cs.cust_id,
            CASE ({PRIORITY_CASE_SQL})
                WHEN 'Critical' THEN 3
                WHEN 'High' THEN 2
                ELSE 1
            END AS priority_rank
        FROM contract_snapshot cs
        LEFT JOIN latest_score ls ON ls.contract_no = cs.contract_no
        WHERE COALESCE(cs.closed_via_restructure, FALSE) = FALSE
    ),
    customer_priority AS (
        SELECT cust_id, MAX(priority_rank) AS priority_rank
        FROM contract_priority
        GROUP BY cust_id
    ),
    base AS (
        SELECT
            cm.cust_id AS cust_id,
            COALESCE(cm.cust_name, cm.cust_id) AS name,
            COALESCE(cbs.active_contract_count, 0) AS active_contract_count,
            COALESCE(cbs.behavioral_grade, 'D') AS behavioral_grade,
            COALESCE(cbs.b_list_status, 'N') AS b_list_status,
            COALESCE(pc.dpd_current, 0) AS dpd_current,
            CASE COALESCE(cpr.priority_rank, 1)
                WHEN 3 THEN 'Critical'
                WHEN 2 THEN 'High'
                ELSE 'Medium'
            END AS priority
        FROM customer_master cm
        LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
        LEFT JOIN primary_contract pc ON pc.cust_id = cm.cust_id
        LEFT JOIN customer_priority cpr ON cpr.cust_id = cm.cust_id
    )
"""

# 75th percentile ambc dihitung on-the-fly dari seluruh contract_snapshot —
# ambang "high_ambc" bukan angka tetap yang di-hardcode (lihat catatan TASK-C
# di frontend-layout-upgrade-tasks.md: "ambang tertentu", tidak dispesifikkan
# presisi). Dipilih 75th percentile sebagai default yang wajar: gampang
# diretune belakangan kalau product owner mau ambang lain.
_AMBC_THRESHOLD_SQL = """
    (SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY ambc)
     FROM contract_snapshot WHERE ambc IS NOT NULL)
"""

_CUSTOMER_FILTER_SQL = {
    "all": "TRUE",
    "dpd_30_plus": "b.dpd_current >= 30",
    # EXISTS-style (sama pola dengan broken_ptp/high_ambc di bawah), konsisten
    # dengan definisi priority level-Customer yang baru: customer PUNYA
    # (bukan "adalah") minimal 1 kontrak aktif berprioritas High/Critical.
    # Pakai kembali PRIORITY_CASE_SQL yang sama dipakai customer_priority CTE
    # di atas supaya 2 tempat itu tidak bisa diam-diam beda logika.
    "high_priority": f"""
        EXISTS (
            SELECT 1 FROM contract_snapshot cs4
            LEFT JOIN latest_score ls4 ON ls4.contract_no = cs4.contract_no
            WHERE cs4.cust_id = b.cust_id
            AND COALESCE(cs4.closed_via_restructure, FALSE) = FALSE
            AND ({PRIORITY_CASE_SQL}) IN ('High', 'Critical')
        )
    """,
    # "Punya kontrak yang..." — di level Customer sengaja jadi EXISTS
    # (agregat), beda dengan level Contract yang murni per-baris (TASK-D).
    "broken_ptp": """
        EXISTS (
            SELECT 1 FROM contract_snapshot cs2
            WHERE cs2.cust_id = b.cust_id
            AND (
                SELECT li.ptp_status FROM lkp_interaction li
                WHERE li.contract_no = cs2.contract_no
                ORDER BY li.action_date DESC LIMIT 1
            ) = 'BROKEN'
        )
    """,
    "high_ambc": f"""
        EXISTS (
            SELECT 1 FROM contract_snapshot cs3
            WHERE cs3.cust_id = b.cust_id AND cs3.ambc > {_AMBC_THRESHOLD_SQL}
        )
    """,
}


def _row_to_customer_list_row(row) -> CustomerListRow:
    return CustomerListRow(
        cust_id=row.cust_id,
        name=row.name,
        active_contract_count=int(row.active_contract_count or 0),
        behavioral_grade=row.behavioral_grade or "D",
        b_list_status=row.b_list_status or "N",
        priority=row.priority,
    )


class CustomerRepository(ICustomerRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def list_customers(self) -> List[Customer]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(_SELECT + " ORDER BY cm.cust_id")).fetchall()
        return [_row_to_customer(r) for r in rows]

    def get_customer(self, cust_id: str) -> Optional[Customer]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SELECT + " WHERE cm.cust_id = :cust_id"), {"cust_id": cust_id}
            ).fetchone()
        return _row_to_customer(row) if row else None

    def exists(self, cust_id: str) -> bool:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM customer_master WHERE cust_id = :cust_id"),
                {"cust_id": cust_id},
            ).fetchone()
        return row is not None

    def get_behavioral_raw(self, cust_id: str) -> Optional[CustomerBehavioralRaw]:
        # LEFT JOIN + kolom cbs.* mentah (TANPA COALESCE) — beda sengaja dari
        # _SELECT di atas yang dipakai get_customer_profile()/_row_to_customer().
        # active_contract_count/total_active_ots aman di-default 0 (schema-nya
        # NOT NULL DEFAULT 0, jadi 0 di sana memang berarti nol, bukan "tidak
        # ada data" — beda dengan behavioral_grade/ptp_reliability_index/
        # collection_sensitivity/b_list_status yang NULL berarti belum dihitung.
        query = """
            SELECT
                cm.cust_id,
                (cbs.cust_id IS NOT NULL) AS has_cbs_row,
                cbs.behavioral_grade,
                cbs.ptp_reliability_index,
                cbs.collection_sensitivity,
                cbs.b_list_status,
                cbs.active_contract_count,
                cbs.total_active_ots,
                cbs.update_timestamp
            FROM customer_master cm
            LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
            WHERE cm.cust_id = :cust_id
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(query), {"cust_id": cust_id}).fetchone()
        if not row:
            return None
        return CustomerBehavioralRaw(
            cust_id=row.cust_id,
            has_cbs_row=bool(row.has_cbs_row),
            behavioral_grade=row.behavioral_grade,
            ptp_reliability_index=(
                float(row.ptp_reliability_index) if row.ptp_reliability_index is not None else None
            ),
            collection_sensitivity=row.collection_sensitivity,
            b_list_status=row.b_list_status,
            active_contract_count=int(row.active_contract_count or 0),
            total_active_ots=float(row.total_active_ots or 0),
            cbs_as_of=row.update_timestamp,
        )

    def list_customers_page(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[CustomerListRow], int]:
        where_sql = _CUSTOMER_FILTER_SQL.get(filter_key, _CUSTOMER_FILTER_SQL["all"])
        params = {"limit": page_size, "offset": (page - 1) * page_size}
        search_sql = ""
        if search:
            search_sql = "AND b.cust_id ILIKE :search"
            params["search"] = f"%{search}%"

        filtered_sql = (
            _CUSTOMER_LIST_BASE_CTE
            + f" SELECT * FROM base b WHERE {where_sql} {search_sql}"
        )

        with self._engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM ({filtered_sql}) t"), params
            ).scalar_one()
            rows = conn.execute(
                text(filtered_sql + " ORDER BY b.cust_id LIMIT :limit OFFSET :offset"),
                params,
            ).fetchall()

        return [_row_to_customer_list_row(r) for r in rows], int(total)

    def get_customer_profile(self, cust_id: str) -> Optional[CustomerProfile]:
        # outstanding_balance HARUS total dari SEMUA kontrak aktif (SUM lewat
        # `ots`), bukan cuma kontrak dengan OTS terbesar — `pc` di bawah tetap
        # dipertahankan hanya untuk memilih kontrak mana yang jadi acuan skor
        # ai_intelligence_output (risk_segment/recovery_score/dst tetap level
        # 1 kontrak "utama", beda concern dari total outstanding).
        query = """
            SELECT
                cm.cust_id,
                cm.cust_name,
                cbs.b_list_status,
                cbs.restructure_count,
                cbs.active_contract_count,
                cbs.behavioral_grade,
                ots.total_ots,
                ai.risk_segment,
                ai.recovery_score,
                ai.self_cure_probability,
                ai.roll_forward_risk,
                ai.ptp_success_probability,
                ai.nba_recommendation
            FROM customer_master cm
            LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(COALESCE(prnc_ots, 0) + COALESCE(intr_ots, 0)), 0) AS total_ots
                FROM contract_snapshot
                WHERE cust_id = cm.cust_id AND COALESCE(closed_via_restructure, FALSE) = FALSE
            ) ots ON TRUE
            LEFT JOIN LATERAL (
                SELECT contract_no
                FROM contract_snapshot
                WHERE cust_id = cm.cust_id AND COALESCE(closed_via_restructure, FALSE) = FALSE
                ORDER BY (COALESCE(prnc_ots, 0) + COALESCE(intr_ots, 0)) DESC
                LIMIT 1
            ) pc ON TRUE
            LEFT JOIN LATERAL (
                SELECT risk_segment, recovery_score, self_cure_probability,
                       roll_forward_risk, ptp_success_probability, nba_recommendation
                FROM ai_intelligence_output
                WHERE contract_no = pc.contract_no
                ORDER BY scoring_date DESC
                LIMIT 1
            ) ai ON TRUE
            WHERE cm.cust_id = :cust_id
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(query), {"cust_id": cust_id}).fetchone()
        if not row:
            return None

        return CustomerProfile(
            cust_id=row.cust_id,
            name=row.cust_name or row.cust_id,
            outstanding_balance=float(row.total_ots or 0),
            risk_segment=row.risk_segment,
            recovery_score=float(row.recovery_score) if row.recovery_score is not None else 0.0,
            self_cure_probability=(
                float(row.self_cure_probability) if row.self_cure_probability is not None else 0.0
            ),
            roll_forward_risk=(
                float(row.roll_forward_risk) if row.roll_forward_risk is not None else 0.0
            ),
            ptp_success_probability=(
                float(row.ptp_success_probability) if row.ptp_success_probability is not None else 0.0
            ),
            nba_recommendation=row.nba_recommendation,
            behavioral_grade=row.behavioral_grade or "D",
            b_list_status=row.b_list_status or "N",
            restructure_count=int(row.restructure_count or 0),
            active_contract_count=int(row.active_contract_count or 0),
        )

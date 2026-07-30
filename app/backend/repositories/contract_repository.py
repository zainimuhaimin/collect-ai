"""Implementasi IContractRepository berbasis Postgres — DB yang sama dipakai
app/machine-learning/ (contract_snapshot + skor terbaru dari
ai_intelligence_output)."""
from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import (
    ActivityLogEntry,
    AiScoringSnapshot,
    Contract,
    ContractDetail,
    ContractListRow,
    PaymentHistoryEntry,
    RestructuringStatusSnapshot,
)
from repositories.interfaces import IContractRepository
from repositories.priority import PRIORITY_CASE_SQL

_SELECT = """
    SELECT
        cs.contract_no,
        cs.cust_id,
        cs.product_type,
        cs.prnc_ots,
        cs.intr_ots,
        cs.interest_rate,
        cs.installment_amount,
        cs.dpd_current,
        cs.maturity_date,
        cs.closed_via_restructure,
        latest.recovery_score,
        latest.self_cure_probability,
        latest.risk_segment
    FROM contract_snapshot cs
    LEFT JOIN LATERAL (
        SELECT recovery_score, self_cure_probability, risk_segment
        FROM ai_intelligence_output
        WHERE contract_no = cs.contract_no
        ORDER BY scoring_date DESC
        LIMIT 1
    ) latest ON TRUE
"""


def _remaining_tenor_months(maturity_date, today: Optional[date] = None) -> int:
    if maturity_date is None:
        return 0
    today = today or date.today()
    days = (maturity_date - today).days
    return max(0, round(days / 30))


def _row_to_contract(row) -> Contract:
    principal_ots = float(row.prnc_ots or 0)
    total_ots = principal_ots + float(row.intr_ots or 0)
    return Contract(
        contract_no=row.contract_no,
        cust_id=row.cust_id,
        product_type=row.product_type or "Unknown",
        total_ots=total_ots,
        principal_ots=principal_ots,
        interest_rate=float(row.interest_rate) if row.interest_rate is not None else 0.0,
        remaining_tenor_months=_remaining_tenor_months(row.maturity_date),
        installment_amount=float(row.installment_amount or 0.0),
        dpd_current=int(row.dpd_current or 0),
        # Belum pernah discoring hari ini -> default konservatif "Can Pay"
        # (bukan "Cannot Pay") supaya classify_eligibility() jatuh ke
        # MANUAL_REVIEW, bukan diam-diam AUTO-approve kontrak yang belum
        # ada skornya sama sekali.
        risk_segment=row.risk_segment or "Can Pay",
        recovery_score=float(row.recovery_score) if row.recovery_score is not None else 0.0,
        self_cure_probability=(
            float(row.self_cure_probability) if row.self_cure_probability is not None else 0.0
        ),
        closed_via_restructure=bool(row.closed_via_restructure or False),
    )


# ── TASK-D: list Contract dengan filter chip/search/paginasi ────────────
# Sama seperti list Customer (TASK-C) tapi murni per-baris — tidak ada
# agregasi "kontrak yang..." di sini karena ambc/ptp_status memang atribut
# kontrak, bukan atribut customer.
_CONTRACT_LIST_BASE_CTE = f"""
    WITH latest_score AS (
        SELECT DISTINCT ON (contract_no) contract_no, risk_segment
        FROM ai_intelligence_output
        ORDER BY contract_no, scoring_date DESC
    ),
    latest_ptp AS (
        SELECT DISTINCT ON (contract_no) contract_no, ptp_status
        FROM lkp_interaction
        ORDER BY contract_no, action_date DESC
    ),
    base AS (
        SELECT
            cs.contract_no AS contract_no,
            cs.cust_id AS cust_id,
            COALESCE(cm.cust_name, cs.cust_id) AS cust_name,
            cs.product_type AS product_type,
            COALESCE(cs.dpd_current, 0) AS dpd_current,
            (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0)) AS outstanding,
            ls.risk_segment AS risk_segment,
            cs.ambc AS ambc,
            lp.ptp_status AS ptp_status,
            {PRIORITY_CASE_SQL} AS priority
        FROM contract_snapshot cs
        LEFT JOIN customer_master cm ON cm.cust_id = cs.cust_id
        LEFT JOIN latest_score ls ON ls.contract_no = cs.contract_no
        LEFT JOIN latest_ptp lp ON lp.contract_no = cs.contract_no
    )
"""

_AMBC_THRESHOLD_SQL = """
    (SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY ambc)
     FROM contract_snapshot WHERE ambc IS NOT NULL)
"""

_CONTRACT_FILTER_SQL = {
    "all": "TRUE",
    "dpd_30_plus": "b.dpd_current >= 30",
    "high_priority": "b.priority IN ('High', 'Critical')",
    "broken_ptp": "b.ptp_status = 'BROKEN'",
    "high_ambc": f"b.ambc > {_AMBC_THRESHOLD_SQL}",
}


def _row_to_contract_list_row(row) -> ContractListRow:
    # `priority` cuma ada di query list_contracts_page() (butuh utk filter
    # high_amount) — list_for_customer() tidak menghitungnya (tidak dibutuhkan,
    # tidak diekspos di response endpoint itu), jadi pakai default dataclass
    # ("Medium") kalau kolomnya tidak ada di row ini.
    priority = row._mapping["priority"] if "priority" in row._mapping else "Medium"
    cust_name = row._mapping["cust_name"] if "cust_name" in row._mapping else row.cust_id
    return ContractListRow(
        contract_no=row.contract_no,
        cust_id=row.cust_id,
        product_type=row.product_type or "Unknown",
        dpd_current=int(row.dpd_current or 0),
        outstanding=float(row.outstanding or 0),
        # Belum pernah discoring -> default konservatif "Can Pay", sama seperti
        # _row_to_contract() di atas (lihat komentarnya) — supaya konsisten,
        # bukan diam-diam menampilkan null di list.
        risk_segment=row.risk_segment or "Can Pay",
        priority=priority,
        cust_name=cust_name or row.cust_id,
    )


class ContractRepository(IContractRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_contract(self, contract_no: str) -> Optional[Contract]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SELECT + " WHERE cs.contract_no = :contract_no"),
                {"contract_no": contract_no},
            ).fetchone()
        return _row_to_contract(row) if row else None

    def get_primary_contract_for_customer(self, cust_id: str) -> Optional[Contract]:
        # "Primary" = kontrak aktif (belum closed_via_restructure) dengan
        # total_ots terbesar untuk customer ini.
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    _SELECT
                    + " WHERE cs.cust_id = :cust_id AND COALESCE(cs.closed_via_restructure, FALSE) = FALSE"
                    + " ORDER BY (COALESCE(cs.prnc_ots,0) + COALESCE(cs.intr_ots,0)) DESC LIMIT 1"
                ),
                {"cust_id": cust_id},
            ).fetchone()
        return _row_to_contract(row) if row else None

    def get_sibling_contracts(self, cust_id: str, exclude_contract_no: str) -> List[Contract]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    _SELECT
                    + " WHERE cs.cust_id = :cust_id AND cs.contract_no != :exclude_contract_no"
                ),
                {"cust_id": cust_id, "exclude_contract_no": exclude_contract_no},
            ).fetchall()
        return [_row_to_contract(r) for r in rows]

    def list_for_customer(self, cust_id: str) -> List[ContractListRow]:
        query = """
            SELECT
                cs.contract_no,
                cs.cust_id,
                cs.product_type,
                COALESCE(cs.dpd_current, 0) AS dpd_current,
                (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0)) AS outstanding,
                ls.risk_segment
            FROM contract_snapshot cs
            LEFT JOIN LATERAL (
                SELECT risk_segment FROM ai_intelligence_output
                WHERE contract_no = cs.contract_no
                ORDER BY scoring_date DESC LIMIT 1
            ) ls ON TRUE
            WHERE cs.cust_id = :cust_id
            ORDER BY cs.dpd_current DESC
        """
        with self._engine.connect() as conn:
            rows = conn.execute(text(query), {"cust_id": cust_id}).fetchall()
        return [_row_to_contract_list_row(r) for r in rows]

    def list_contracts_page(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[ContractListRow], int]:
        where_sql = _CONTRACT_FILTER_SQL.get(filter_key, _CONTRACT_FILTER_SQL["all"])
        params = {"limit": page_size, "offset": (page - 1) * page_size}
        search_sql = ""
        if search:
            search_sql = "AND (b.contract_no ILIKE :search OR b.cust_id ILIKE :search)"
            params["search"] = f"%{search}%"

        filtered_sql = (
            _CONTRACT_LIST_BASE_CTE
            + f" SELECT * FROM base b WHERE {where_sql} {search_sql}"
        )

        with self._engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM ({filtered_sql}) t"), params
            ).scalar_one()
            rows = conn.execute(
                text(filtered_sql + " ORDER BY b.contract_no LIMIT :limit OFFSET :offset"),
                params,
            ).fetchall()

        return [_row_to_contract_list_row(r) for r in rows], int(total)

    def get_contract_detail(self, contract_no: str) -> Optional[ContractDetail]:
        query = """
            SELECT
                cs.contract_no, cs.cust_id, cs.product_type, cs.cycle, cs.prev_cycle,
                cs.closed_via_restructure, cs.new_contract_no, cs.loan_amount,
                cs.installment_amount, cs.interest_rate, cs.maturity_date,
                cs.dpd_current, cs.overdue_installment_count, cs.late_fee_amount,
                cs.ambc, cs.prnc_ots, cs.intr_ots,
                COALESCE(cm.cust_name, cs.cust_id) AS cust_name,
                ai.recovery_score, ai.risk_segment, ai.self_cure_probability,
                ai.roll_forward_risk, ai.ptp_success_probability, ai.nba_recommendation,
                ai.confidence_level, ai.scoring_date,
                rs.restructure_group_id, rs.offer_status, rs.eligibility_tier
            FROM contract_snapshot cs
            LEFT JOIN customer_master cm ON cm.cust_id = cs.cust_id
            LEFT JOIN LATERAL (
                SELECT recovery_score, risk_segment, self_cure_probability, roll_forward_risk,
                       ptp_success_probability, nba_recommendation, confidence_level, scoring_date
                FROM ai_intelligence_output
                WHERE contract_no = cs.contract_no
                ORDER BY scoring_date DESC LIMIT 1
            ) ai ON TRUE
            LEFT JOIN LATERAL (
                -- Kontrak bisa pernah masuk >1 restructure_group_id (mis. sudah
                -- pernah ditawari lalu ditawari ulang) — ambil yang generated_date
                -- paling baru (lihat catatan spec TASK-D endpoint #5).
                SELECT rro.restructure_group_id, rro.offer_status, rro.eligibility_tier
                FROM restructuring_group_map rgm
                JOIN restructuring_recommendation_output rro
                    ON rro.restructure_group_id = rgm.restructure_group_id
                WHERE rgm.contract_no = cs.contract_no
                ORDER BY rro.generated_date DESC LIMIT 1
            ) rs ON TRUE
            WHERE cs.contract_no = :contract_no
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(query), {"contract_no": contract_no}).fetchone()
            if not row:
                return None

            payment_rows = conn.execute(
                text(
                    "SELECT due_date, actual_pay_date, payment_amount, pay_status, "
                    "delay_days, recovery_source FROM payment_history "
                    "WHERE contract_no = :contract_no ORDER BY due_date DESC LIMIT 12"
                ),
                {"contract_no": contract_no},
            ).fetchall()

        ai_scoring = None
        if row.scoring_date is not None:
            ai_scoring = AiScoringSnapshot(
                recovery_score=float(row.recovery_score) if row.recovery_score is not None else 0.0,
                risk_segment=row.risk_segment,
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
                confidence_level=float(row.confidence_level) if row.confidence_level is not None else 0.0,
                scoring_date=row.scoring_date,
            )

        restructuring_status = None
        if row.restructure_group_id is not None:
            restructuring_status = RestructuringStatusSnapshot(
                restructure_group_id=row.restructure_group_id,
                offer_status=row.offer_status,
                eligibility_tier=row.eligibility_tier,
            )

        return ContractDetail(
            contract_no=row.contract_no,
            cust_id=row.cust_id,
            cust_name=row.cust_name,
            product_type=row.product_type or "Unknown",
            cycle=row.cycle,
            prev_cycle=row.prev_cycle,
            closed_via_restructure=bool(row.closed_via_restructure or False),
            new_contract_no=row.new_contract_no,
            loan_amount=float(row.loan_amount or 0),
            installment_amount=float(row.installment_amount or 0),
            interest_rate=float(row.interest_rate) if row.interest_rate is not None else 0.0,
            maturity_date=row.maturity_date,
            remaining_tenor_months=_remaining_tenor_months(row.maturity_date),
            dpd_current=int(row.dpd_current or 0),
            overdue_installment_count=int(row.overdue_installment_count or 0),
            late_fee_amount=float(row.late_fee_amount or 0),
            ambc=float(row.ambc or 0),
            principal_ots=float(row.prnc_ots or 0),
            interest_ots=float(row.intr_ots or 0),
            ai_scoring=ai_scoring,
            payment_history=[
                PaymentHistoryEntry(
                    due_date=r.due_date,
                    actual_pay_date=r.actual_pay_date,
                    payment_amount=float(r.payment_amount or 0),
                    pay_status=r.pay_status,
                    delay_days=r.delay_days,
                    recovery_source=r.recovery_source,
                )
                for r in payment_rows
            ],
            restructuring_status=restructuring_status,
        )

    def get_activity_log(self, contract_no: str) -> List[ActivityLogEntry]:
        query = """
            SELECT lkp_id, action_date, treatment_type, result_code, ptp_status
            FROM lkp_interaction
            WHERE contract_no = :contract_no
            ORDER BY action_date DESC
        """
        with self._engine.connect() as conn:
            rows = conn.execute(text(query), {"contract_no": contract_no}).fetchall()
        return [
            ActivityLogEntry(
                lkp_id=r.lkp_id,
                action_date=r.action_date,
                treatment_type=r.treatment_type,
                result_code=r.result_code,
                ptp_status=r.ptp_status,
            )
            for r in rows
        ]

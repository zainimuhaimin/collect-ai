"""Implementasi IContractRepository berbasis Postgres — DB yang sama dipakai
app/machine-learning/ (contract_snapshot + skor terbaru dari
ai_intelligence_output)."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import Contract
from repositories.interfaces import IContractRepository

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
    total_ots = float(row.prnc_ots or 0) + float(row.intr_ots or 0)
    return Contract(
        contract_no=row.contract_no,
        cust_id=row.cust_id,
        product_type=row.product_type or "Unknown",
        total_ots=total_ots,
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

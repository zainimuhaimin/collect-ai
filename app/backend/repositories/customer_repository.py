"""Implementasi ICustomerRepository berbasis Postgres — DB yang sama dipakai
app/machine-learning/ (satu sumber kebenaran: customer_master +
customer_behavioral_standing)."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import Customer
from repositories.interfaces import ICustomerRepository

_SELECT = """
    SELECT
        cm.cust_id,
        cbs.b_list_status,
        cbs.restructure_count,
        cbs.active_contract_count,
        cbs.behavioral_grade
    FROM customer_master cm
    LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
"""


def _row_to_customer(row) -> Customer:
    # customer_master TIDAK punya kolom nama asli (lihat faker/schema) — pakai
    # cust_id sebagai display label daripada mengarang nama palsu.
    return Customer(
        cust_id=row.cust_id,
        name=row.cust_id,
        b_list_status=row.b_list_status or "N",
        restructure_count=int(row.restructure_count or 0),
        active_contract_count=int(row.active_contract_count or 0),
        behavioral_grade=row.behavioral_grade or "D",
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

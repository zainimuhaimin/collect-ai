"""Implementasi IRestructuringOfferRepository berbasis Postgres.

Offer-nya SENDIRI dihasilkan oleh batch ML (pipelines/restructuring_runner.py)
atau endpoint on-demand — repository ini HANYA baca status offer dan
mencatat keputusan customer (accept/reject). Tidak pernah menghitung ulang
angka tawaran (itu murni tugas ml.restructuring_offer_calculator)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import RestructuringOfferRecord
from repositories.interfaces import IRestructuringOfferRepository

_SELECT = """
    SELECT restructure_group_id, cust_id, offer_type, offer_status,
           generated_date, expiry_date, response_date
    FROM restructuring_recommendation_output
    WHERE restructure_group_id = :group_id
"""


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


class RestructuringOfferRepository(IRestructuringOfferRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_offer(self, restructure_group_id: str) -> Optional[RestructuringOfferRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(text(_SELECT), {"group_id": restructure_group_id}).fetchone()
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

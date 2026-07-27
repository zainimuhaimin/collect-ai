"""Test originator.py terhadap Postgres asli (data throwaway, dibersihkan
di teardown) — memverifikasi siklus penuh: offer ACCEPTED -> kontrak baru
dibuat, kontrak lama ditutup (closed_via_restructure + new_contract_no),
dan idempotent (jalan 2x tidak membuat kontrak baru ganda)."""
import os
import sys
from datetime import date

import pytest
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.config import DB_URL  # noqa: E402
from originator import run_contract_origination, _new_contract_no  # noqa: E402

GROUP_ID = "RG-TEST-ORIGINATOR-1"
OLD_CONTRACT_NO = "CTR-TEST-ORIGINATOR-OLD"
CUST_ID = "CUST-TEST-ORIGINATOR"


@pytest.fixture()
def engine():
    return create_engine(DB_URL)


@pytest.fixture()
def seeded_offer(engine):
    today = date.today()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_snapshot "
                "(contract_no, cust_id, dpd_current, prnc_ots, intr_ots, cycle, product_type) "
                "VALUES (:c, :cust, 45, 10000000, 1000000, 'C1', 'Motor') "
                "ON CONFLICT (contract_no) DO NOTHING"
            ),
            {"c": OLD_CONTRACT_NO, "cust": CUST_ID},
        )
        conn.execute(
            text(
                "INSERT INTO restructuring_group_map (restructure_group_id, contract_no, cust_id, inclusion_reason) "
                "VALUES (:g, :c, :cust, 'REFINANCE') "
                "ON CONFLICT (restructure_group_id, contract_no) DO NOTHING"
            ),
            {"g": GROUP_ID, "c": OLD_CONTRACT_NO, "cust": CUST_ID},
        )
        conn.execute(
            text(
                "INSERT INTO restructuring_recommendation_output "
                "(restructure_group_id, cust_id, offer_type, contract_count_included, "
                " total_ots_combined, recommended_new_tenor, recommended_new_rate, "
                " recommended_new_installment, offer_status, generated_date) "
                "VALUES (:g, :cust, 'REFINANCE', 1, 11000000, 24, 0.18, 550000, 'ACCEPTED', :gd) "
                "ON CONFLICT (restructure_group_id) DO UPDATE SET offer_status = 'ACCEPTED'"
            ),
            {"g": GROUP_ID, "cust": CUST_ID, "gd": today},
        )

    yield GROUP_ID

    new_contract_no = _new_contract_no(GROUP_ID)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM restructuring_group_map WHERE restructure_group_id = :g"), {"g": GROUP_ID})
        conn.execute(
            text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = :g"), {"g": GROUP_ID}
        )
        conn.execute(text("DELETE FROM contract_snapshot WHERE contract_no = :c"), {"c": new_contract_no})
        conn.execute(text("DELETE FROM contract_snapshot WHERE contract_no = :c"), {"c": OLD_CONTRACT_NO})


def test_origination_creates_new_contract_and_closes_old(engine, seeded_offer):
    result = run_contract_origination(engine=engine)
    assert result["executed"] >= 1

    new_contract_no = _new_contract_no(GROUP_ID)
    with engine.connect() as conn:
        new_row = conn.execute(
            text("SELECT * FROM contract_snapshot WHERE contract_no = :c"), {"c": new_contract_no}
        ).fetchone()
        old_row = conn.execute(
            text("SELECT closed_via_restructure, new_contract_no FROM contract_snapshot WHERE contract_no = :c"),
            {"c": OLD_CONTRACT_NO},
        ).fetchone()

    assert new_row is not None, "Kontrak baru harus terbuat"
    assert new_row.cust_id == CUST_ID
    assert new_row.dpd_current == 0
    assert new_row.closed_via_restructure is False

    assert old_row.closed_via_restructure is True
    assert old_row.new_contract_no == new_contract_no


def test_origination_is_idempotent(engine, seeded_offer):
    result1 = run_contract_origination(engine=engine)
    result2 = run_contract_origination(engine=engine)

    assert result1["executed"] >= 1
    assert result2["executed"] == 0, "Jalan ke-2 tidak boleh eksekusi ulang (sudah closed_via_restructure)"

    new_contract_no = _new_contract_no(GROUP_ID)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) AS n FROM contract_snapshot WHERE contract_no = :c"), {"c": new_contract_no}
        ).fetchone()
    assert count.n == 1, "Tidak boleh ada kontrak baru duplikat"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

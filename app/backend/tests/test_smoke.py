"""Smoke test — end-to-end lewat TestClient terhadap Postgres ASLI (DB yang
sama dipakai app/machine-learning/), TIDAK ADA mock/in-memory repository.
Fixture yang butuh skenario spesifik (AUTO vs MANUAL_REVIEW) menyisipkan
baris data throwaway lalu membersihkannya di teardown — bukan mengandalkan
data batch yang kebetulan ada di database dev bersama.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from core.config import settings
from main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def engine():
    return create_engine(settings.database_url)


def _seed_customer_and_contract(engine, cust_id, contract_no, dpd_current, risk_segment="Cannot Pay"):
    """Sisipkan 1 customer + 1 contract + 1 skor hari ini, cukup lengkap
    untuk lolos classify_eligibility() dengan kondisi yang terkontrol
    (bukan bergantung data faker yang kebetulan ada)."""
    today = date.today()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO customer_master (cust_id, cust_income_level, cust_segment) "
                "VALUES (:c, '5-10 Juta', 'Medium Risk') ON CONFLICT (cust_id) DO NOTHING"
            ),
            {"c": cust_id},
        )
        conn.execute(
            text(
                "INSERT INTO customer_behavioral_standing "
                "(cust_id, active_contract_count, total_active_ots, behavioral_grade, "
                " recovery_effort_level, b_list_status, restructure_count) "
                "VALUES (:c, 1, 15000000, 'B', 'Mid', 'N', 0) "
                "ON CONFLICT (cust_id) DO UPDATE SET b_list_status = 'N', restructure_count = 0"
            ),
            {"c": cust_id},
        )
        conn.execute(
            text(
                "INSERT INTO contract_snapshot "
                "(contract_no, cust_id, dpd_current, prnc_ots, intr_ots, cycle, product_type, "
                " interest_rate, installment_amount, maturity_date, closed_via_restructure) "
                "VALUES (:ct, :c, :dpd, 15000000, 1500000, 'C1', 'Motor', 0.24, 1100000, :maturity, FALSE) "
                "ON CONFLICT (contract_no) DO UPDATE SET "
                "dpd_current = :dpd, maturity_date = :maturity, closed_via_restructure = FALSE"
            ),
            {"ct": contract_no, "c": cust_id, "dpd": dpd_current, "maturity": today + timedelta(days=18 * 30)},
        )
        conn.execute(
            text(
                "INSERT INTO ai_intelligence_output "
                "(contract_no, cust_id, recovery_score, confidence_level, confidence_category, "
                " risk_segment, nba_recommendation, priority_level, scoring_date, self_cure_probability) "
                "VALUES (:ct, :c, 0.35, 0.60, 'MEDIUM', :seg, 'Deskcoll', 'Medium', :today, 0.20) "
                "ON CONFLICT (contract_no) DO UPDATE SET "
                "risk_segment = :seg, scoring_date = :today, self_cure_probability = 0.20"
            ),
            {"ct": contract_no, "c": cust_id, "seg": risk_segment, "today": today},
        )


def _cleanup_customer_and_contract(engine, cust_id, contract_no):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ai_intelligence_output WHERE contract_no = :ct"), {"ct": contract_no})
        conn.execute(text("DELETE FROM contract_snapshot WHERE contract_no = :ct"), {"ct": contract_no})
        conn.execute(text("DELETE FROM customer_behavioral_standing WHERE cust_id = :c"), {"c": cust_id})
        conn.execute(text("DELETE FROM customer_master WHERE cust_id = :c"), {"c": cust_id})


@pytest.fixture()
def auto_tier_customer(engine):
    cust_id, contract_no = "TEST-CUST-AUTO", "TEST-CTR-AUTO"
    _seed_customer_and_contract(engine, cust_id, contract_no, dpd_current=45)
    yield cust_id
    _cleanup_customer_and_contract(engine, cust_id, contract_no)


@pytest.fixture()
def manual_review_customer(engine):
    # DPD 10 hari -> di luar window standar (30-180) -> MANUAL_REVIEW
    cust_id, contract_no = "TEST-CUST-MANUALREVIEW", "TEST-CTR-MANUALREVIEW"
    _seed_customer_and_contract(engine, cust_id, contract_no, dpd_current=10)
    yield cust_id
    _cleanup_customer_and_contract(engine, cust_id, contract_no)


# ── API 1: Health ─────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/test")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello from backend"}


# ── API 2 & 3: Customers ──────────────────────────────────────────────

def test_list_customers():
    r = client.get("/api/v1/customers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_customer_detail_not_found():
    r = client.get("/api/v1/customers/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_customer_detail_found(auto_tier_customer):
    r = client.get(f"/api/v1/customers/{auto_tier_customer}")
    assert r.status_code == 200
    assert r.json()["cust_id"] == auto_tier_customer


# ── API 4: Restructuring options ──────────────────────────────────────

def test_restructuring_options_auto(auto_tier_customer):
    r = client.get(f"/api/v1/customers/{auto_tier_customer}/restructuring-options")
    assert r.status_code == 200
    body = r.json()
    assert body["eligibility_tier"] == "AUTO"
    assert len(body["offers"]) >= 1


def test_restructuring_options_manual_review(manual_review_customer):
    """DPD 10 hari, di luar window standar -> MANUAL_REVIEW, tapi offers
    TETAP ada. Regression test paling penting di seluruh backend ini —
    JANGAN dihapus/diskip."""
    r = client.get(f"/api/v1/customers/{manual_review_customer}/restructuring-options")
    assert r.status_code == 200
    body = r.json()
    assert body["eligibility_tier"] == "MANUAL_REVIEW"
    assert len(body["offers"]) >= 1, "MANUAL_REVIEW tier harus tetap menghasilkan offer!"


def test_restructuring_options_not_found():
    r = client.get("/api/v1/customers/DOES-NOT-EXIST/restructuring-options")
    assert r.status_code == 404


# ── API 5: Customer response (accept/reject) ─────────────────────────

@pytest.fixture()
def offered_offer(engine):
    group_id = "RG-TEST-SMOKE-CUSTOMER-RESPONSE"
    cust_id = "TEST-CUST-SMOKE"
    today = date.today()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = :g"), {"g": group_id}
        )
        conn.execute(
            text(
                "INSERT INTO restructuring_recommendation_output "
                "(restructure_group_id, cust_id, offer_type, contract_count_included, "
                " offer_status, generated_date, expiry_date) "
                "VALUES (:g, :c, 'REFINANCE', 1, 'OFFERED', :gd, :ed)"
            ),
            {"g": group_id, "c": cust_id, "gd": today, "ed": today + timedelta(days=14)},
        )
    yield {"group_id": group_id, "cust_id": cust_id}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = :g"), {"g": group_id}
        )


def test_customer_response_accept(engine, offered_offer):
    r = client.post(
        f"/api/v1/customers/{offered_offer['cust_id']}/restructuring-options/{offered_offer['group_id']}/customer-response",
        json={"response": "ACCEPTED"},
    )
    assert r.status_code == 200
    assert r.json()["response"] == "ACCEPTED"

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT offer_status, response_date FROM restructuring_recommendation_output WHERE restructure_group_id = :g"),
            {"g": offered_offer["group_id"]},
        ).fetchone()
    assert row.offer_status == "ACCEPTED"
    assert row.response_date == date.today()


def test_customer_response_wrong_customer_forbidden(offered_offer):
    r = client.post(
        f"/api/v1/customers/SOMEONE-ELSE/restructuring-options/{offered_offer['group_id']}/customer-response",
        json={"response": "ACCEPTED"},
    )
    assert r.status_code == 403


def test_customer_response_not_found():
    r = client.post(
        "/api/v1/customers/TEST-CUST-SMOKE/restructuring-options/RG-DOES-NOT-EXIST/customer-response",
        json={"response": "ACCEPTED"},
    )
    assert r.status_code == 404


def test_customer_response_cannot_respond_twice(offered_offer):
    r1 = client.post(
        f"/api/v1/customers/{offered_offer['cust_id']}/restructuring-options/{offered_offer['group_id']}/customer-response",
        json={"response": "ACCEPTED"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/v1/customers/{offered_offer['cust_id']}/restructuring-options/{offered_offer['group_id']}/customer-response",
        json={"response": "REJECTED"},
    )
    assert r2.status_code == 409


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

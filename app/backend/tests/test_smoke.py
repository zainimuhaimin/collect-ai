"""Smoke test — end-to-end lewat TestClient terhadap Postgres ASLI (DB yang
sama dipakai app/machine-learning/), TIDAK ADA mock/in-memory repository.
Fixture yang butuh skenario spesifik (AUTO vs MANUAL_REVIEW) menyisipkan
baris data throwaway lalu membersihkannya di teardown — bukan mengandalkan
data batch yang kebetulan ada di database dev bersama.
"""
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from core.config import settings
from core.security import hash_password
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
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert body["version"] == settings.app_version


# ── API 2 & 3: Customers (TASK-C: reshape jadi filter/search/paginasi) ──

def test_list_customers():
    r = client.get("/api/v1/customers?page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert "customers" in body and "page_info" in body
    assert body["page_info"]["total_pages"] >= 1
    if body["customers"]:
        assert set(body["customers"][0].keys()) == {
            "cust_id", "name", "active_contract_count", "behavioral_grade", "b_list_status", "priority",
        }
        assert body["customers"][0]["priority"] in ("Critical", "High", "Medium")


@pytest.mark.parametrize("filter_key", ["all", "dpd_30_plus", "high_priority", "broken_ptp", "high_ambc"])
def test_list_customers_each_filter_returns_200(filter_key):
    r = client.get(f"/api/v1/customers?filter={filter_key}&page_size=5")
    assert r.status_code == 200
    assert "customers" in r.json()


def test_list_customers_dpd_30_plus_filter_is_correct(engine):
    # dpd_days sudah tidak diekspos di response (TASK-C reshape) — kriteria
    # filternya (dpd_current kontrak UTAMA >= 30) diverifikasi langsung ke DB.
    r = client.get("/api/v1/customers?filter=dpd_30_plus&page_size=50")
    assert r.status_code == 200
    cust_ids = [c["cust_id"] for c in r.json()["customers"]]
    if not cust_ids:
        return
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT ON (cust_id) cust_id, dpd_current FROM contract_snapshot "
                "WHERE cust_id = ANY(:ids) AND COALESCE(closed_via_restructure, FALSE) = FALSE "
                "ORDER BY cust_id, (COALESCE(prnc_ots, 0) + COALESCE(intr_ots, 0)) DESC"
            ),
            {"ids": cust_ids},
        ).fetchall()
    for row in rows:
        assert row.dpd_current >= 30


def test_list_customers_search_matches_cust_id(auto_tier_customer):
    r = client.get(f"/api/v1/customers?search={auto_tier_customer}")
    assert r.status_code == 200
    cust_ids = [c["cust_id"] for c in r.json()["customers"]]
    assert auto_tier_customer in cust_ids


def _seed_multi_priority_customer(engine, cust_id, low_priority_contract_no, high_priority_contract_no):
    """Customer dengan 2 kontrak aktif berprioritas beda — kontrak dengan
    outstanding TERBESAR (yang dulu jadi 'primary contract' arbitrer) sengaja
    dibuat Medium, kontrak KECIL yang Critical. Kalau priority level-Customer
    masih (secara diam-diam) bocor jadi priority 1-kontrak-arbitrer, test ini
    akan gagal mendeteksinya (expect 'Critical', bukan 'Medium')."""
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
                "VALUES (:c, 2, 51000000, 'C', 'Mid', 'N', 0) "
                "ON CONFLICT (cust_id) DO UPDATE SET active_contract_count = 2, b_list_status = 'N'"
            ),
            {"c": cust_id},
        )
        for contract_no, prnc_ots, dpd_current in (
            (low_priority_contract_no, 50_000_000, 0),
            (high_priority_contract_no, 1_000_000, 95),
        ):
            conn.execute(
                text(
                    "INSERT INTO contract_snapshot "
                    "(contract_no, cust_id, dpd_current, prnc_ots, intr_ots, cycle, product_type, "
                    " interest_rate, installment_amount, maturity_date, closed_via_restructure) "
                    "VALUES (:ct, :c, :dpd, :prnc, 0, 'C1', 'Motor', 0.24, 1100000, :maturity, FALSE) "
                    "ON CONFLICT (contract_no) DO UPDATE SET "
                    "dpd_current = :dpd, prnc_ots = :prnc, closed_via_restructure = FALSE"
                ),
                {
                    "ct": contract_no,
                    "c": cust_id,
                    "dpd": dpd_current,
                    "prnc": prnc_ots,
                    "maturity": today + timedelta(days=18 * 30),
                },
            )
        conn.execute(
            text(
                "INSERT INTO ai_intelligence_output "
                "(contract_no, cust_id, recovery_score, confidence_level, confidence_category, "
                " risk_segment, nba_recommendation, priority_level, scoring_date, self_cure_probability) "
                "VALUES (:ct, :c, 0.35, 0.60, 'MEDIUM', 'Can Pay', 'Deskcoll', 'Medium', :today, 0.20) "
                "ON CONFLICT (contract_no) DO UPDATE SET risk_segment = 'Can Pay', scoring_date = :today"
            ),
            {"ct": low_priority_contract_no, "c": cust_id, "today": today},
        )
        conn.execute(
            text(
                "INSERT INTO ai_intelligence_output "
                "(contract_no, cust_id, recovery_score, confidence_level, confidence_category, "
                " risk_segment, nba_recommendation, priority_level, scoring_date, self_cure_probability) "
                "VALUES (:ct, :c, 0.80, 0.60, 'MEDIUM', 'Cannot Pay', 'Deskcoll', 'Critical', :today, 0.05) "
                "ON CONFLICT (contract_no) DO UPDATE SET risk_segment = 'Cannot Pay', scoring_date = :today"
            ),
            {"ct": high_priority_contract_no, "c": cust_id, "today": today},
        )


def _cleanup_multi_priority_customer(engine, cust_id, low_priority_contract_no, high_priority_contract_no):
    with engine.begin() as conn:
        for ct in (low_priority_contract_no, high_priority_contract_no):
            conn.execute(text("DELETE FROM ai_intelligence_output WHERE contract_no = :ct"), {"ct": ct})
            conn.execute(text("DELETE FROM contract_snapshot WHERE contract_no = :ct"), {"ct": ct})
        conn.execute(text("DELETE FROM customer_behavioral_standing WHERE cust_id = :c"), {"c": cust_id})
        conn.execute(text("DELETE FROM customer_master WHERE cust_id = :c"), {"c": cust_id})


@pytest.fixture()
def multi_priority_customer(engine):
    cust_id = "TEST-CUST-MULTIPRIORITY"
    low_ct, high_ct = "TEST-CTR-MULTI-LOW", "TEST-CTR-MULTI-HIGH"
    _seed_multi_priority_customer(engine, cust_id, low_ct, high_ct)
    yield cust_id
    _cleanup_multi_priority_customer(engine, cust_id, low_ct, high_ct)


def test_list_customers_priority_is_max_across_active_contracts(multi_priority_customer):
    r = client.get(f"/api/v1/customers?search={multi_priority_customer}")
    assert r.status_code == 200
    customers = r.json()["customers"]
    assert len(customers) == 1
    assert customers[0]["priority"] == "Critical"


def test_list_customers_high_priority_filter_is_exists_style(multi_priority_customer):
    r = client.get(f"/api/v1/customers?filter=high_priority&search={multi_priority_customer}")
    assert r.status_code == 200
    cust_ids = [c["cust_id"] for c in r.json()["customers"]]
    assert multi_priority_customer in cust_ids


def test_customer_detail_not_found():
    r = client.get("/api/v1/customers/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_customer_detail_found(auto_tier_customer):
    r = client.get(f"/api/v1/customers/{auto_tier_customer}")
    assert r.status_code == 200
    body = r.json()
    assert body["cust_id"] == auto_tier_customer
    # Fixture _seed_customer_and_contract() tidak mengisi customer_master.cust_name
    # -> NULL -> fallback ke cust_id (lihat CustomerRepository.get_customer_profile).
    assert body["name"] == auto_tier_customer
    assert body["risk_segment"] == "Cannot Pay"  # apa adanya dari ai_intelligence_output, lihat fixture
    assert body["outstanding_balance"].startswith("Rp ")
    assert body["initials"]  # dihitung dari `name` (fallback cust_id di fixture ini)


def test_customer_contracts_list(auto_tier_customer):
    r = client.get(f"/api/v1/customers/{auto_tier_customer}/contracts")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[0]["contract_no"] == "TEST-CTR-AUTO"
    assert body[0]["outstanding"].startswith("Rp ")


def test_customer_contracts_list_not_found():
    r = client.get("/api/v1/customers/DOES-NOT-EXIST/contracts")
    assert r.status_code == 404


# ── API: Contract list + detail (TASK-D) ────────────────────────────────

@pytest.mark.parametrize("filter_key", ["all", "dpd_30_plus", "high_priority", "broken_ptp", "high_ambc"])
def test_list_contracts_each_filter_returns_200(filter_key):
    r = client.get(f"/api/v1/contracts?filter={filter_key}&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert "contracts" in body and "page_info" in body


def test_list_contracts_search_matches_contract_no(auto_tier_customer):
    r = client.get("/api/v1/contracts?search=TEST-CTR-AUTO")
    assert r.status_code == 200
    contract_nos = [c["contract_no"] for c in r.json()["contracts"]]
    assert "TEST-CTR-AUTO" in contract_nos


def test_contract_detail_found(auto_tier_customer):
    r = client.get("/api/v1/contracts/TEST-CTR-AUTO")
    assert r.status_code == 200
    body = r.json()
    assert body["contract_no"] == "TEST-CTR-AUTO"
    assert body["cust_id"] == auto_tier_customer
    assert body["ai_scoring"]["risk_segment"] == "Cannot Pay"
    assert "outstanding" in body and set(body["outstanding"].keys()) == {"principal", "interest", "total"}
    assert isinstance(body["payment_history"], list)


def test_contract_detail_not_found():
    r = client.get("/api/v1/contracts/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_contract_activity_log(auto_tier_customer):
    r = client.get("/api/v1/contracts/TEST-CTR-AUTO/activity-log")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── API: Dashboard summary (TASK-B) ──────────────────────────────────────

def test_dashboard_summary():
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "kpis",
        "dpd_buckets",
        "contactability_funnel",
        "channel_efficiency",
        "restructuring_pipeline_snapshot",
        "risk_segment_distribution",
        "sync_note",
    ):
        assert key in body
    assert "broken_ptp_priorities" not in body  # sengaja dihapus, lihat TASK-B


# ── API: Restructuring Approval queue (TASK-E) ──────────────────────────

@pytest.fixture()
def governance_auth_token(engine):
    """User throwaway HANYA untuk audit trail approve/reject & PUT
    weighting-parameters (tidak ada gate role — lihat TASK-A)."""
    username, password = "test.smoke.governance", "testpass123"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})
        conn.execute(
            text("INSERT INTO users (username, password_hash, name, role) VALUES (:u, :p, :n, :r)"),
            {"u": username, "p": hash_password(password), "n": "Smoke Governance", "r": "QA"},
        )
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    token = login.json()["token"]
    yield token
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})


@pytest.fixture()
def generated_restructuring_group(engine):
    group_id, cust_id = "TEST-RG-SMOKE", "TEST-CUST-SMOKE-GOV"
    today = date.today()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM restructuring_approval_log WHERE restructure_group_id = :g"), {"g": group_id})
        conn.execute(
            text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = :g"), {"g": group_id}
        )
        # list_offers()/get_offer_summary() JOIN customer_master (lihat
        # RestructuringOfferRepository) — butuh baris ini supaya group throwaway
        # ini muncul di GET /restructuring-groups (list + search), bukan cuma
        # kebaca lewat get_offer() (approve/reject) yang tidak pakai JOIN itu.
        conn.execute(
            text(
                "INSERT INTO customer_master (cust_id, cust_income_level, cust_segment) "
                "VALUES (:c, '5-10 Juta', 'Medium Risk') ON CONFLICT (cust_id) DO NOTHING"
            ),
            {"c": cust_id},
        )
        conn.execute(
            text(
                "INSERT INTO restructuring_recommendation_output "
                "(restructure_group_id, cust_id, offer_type, contract_count_included, "
                " offer_status, generated_date, expiry_date, eligibility_tier) "
                "VALUES (:g, :c, 'REFINANCE', 1, 'GENERATED', :gd, :ed, 'MANUAL_REVIEW')"
            ),
            {"g": group_id, "c": cust_id, "gd": today, "ed": today + timedelta(days=14)},
        )
    yield group_id
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM restructuring_approval_log WHERE restructure_group_id = :g"), {"g": group_id})
        conn.execute(
            text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = :g"), {"g": group_id}
        )
        conn.execute(text("DELETE FROM customer_master WHERE cust_id = :c"), {"c": cust_id})


def test_restructuring_groups_list_default_is_generated():
    r = client.get("/api/v1/restructuring-groups")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["groups"], list)
    assert "page_info" in body
    assert body["page_info"]["total_pages"] >= 1


def test_restructuring_groups_list_history_statuses():
    r = client.get("/api/v1/restructuring-groups?status=OFFERED,REJECTED")
    assert r.status_code == 200


def test_restructuring_groups_search_matches_group_id(generated_restructuring_group):
    r = client.get(f"/api/v1/restructuring-groups?search={generated_restructuring_group}")
    assert r.status_code == 200
    group_ids = [g["restructure_group_id"] for g in r.json()["groups"]]
    assert generated_restructuring_group in group_ids


def test_restructuring_groups_search_matches_cust_id(generated_restructuring_group, engine):
    with engine.connect() as conn:
        cust_id = conn.execute(
            text("SELECT cust_id FROM restructuring_recommendation_output WHERE restructure_group_id = :g"),
            {"g": generated_restructuring_group},
        ).scalar_one()
    r = client.get(f"/api/v1/restructuring-groups?search={cust_id}")
    assert r.status_code == 200
    group_ids = [g["restructure_group_id"] for g in r.json()["groups"]]
    assert generated_restructuring_group in group_ids


def test_restructuring_groups_search_no_match():
    r = client.get("/api/v1/restructuring-groups?search=DOES-NOT-EXIST-AT-ALL")
    assert r.status_code == 200
    body = r.json()
    assert body["groups"] == []
    assert body["page_info"]["total_groups"] == 0


def test_restructuring_groups_pagination():
    r = client.get("/api/v1/restructuring-groups?status=GENERATED,OFFERED,ACCEPTED,REJECTED,EXPIRED&page=1&page_size=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["groups"]) <= 2
    assert body["page_info"]["showing_from"] in (0, 1)


def test_restructuring_group_detail_found(generated_restructuring_group):
    r = client.get(f"/api/v1/restructuring-groups/{generated_restructuring_group}")
    assert r.status_code == 200
    body = r.json()
    assert body["restructure_group_id"] == generated_restructuring_group
    assert body["offer_status"] == "GENERATED"


def test_restructuring_group_detail_not_found():
    r = client.get("/api/v1/restructuring-groups/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_restructuring_group_approve(engine, generated_restructuring_group, governance_auth_token):
    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    r = client.post(
        f"/api/v1/restructuring-groups/{generated_restructuring_group}/approve", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["offer_status"] == "OFFERED"

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT action, performed_by FROM restructuring_approval_log "
                "WHERE restructure_group_id = :g"
            ),
            {"g": generated_restructuring_group},
        ).fetchone()
    assert row is not None, "Approve harus mencatat audit row di restructuring_approval_log"
    assert row.action == "APPROVE"
    assert row.performed_by == "test.smoke.governance"

    r2 = client.post(
        f"/api/v1/restructuring-groups/{generated_restructuring_group}/approve", headers=headers
    )
    assert r2.status_code == 409


def test_restructuring_group_reject(generated_restructuring_group, governance_auth_token):
    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    r = client.post(f"/api/v1/restructuring-groups/{generated_restructuring_group}/reject", headers=headers)
    assert r.status_code == 200
    assert r.json()["offer_status"] == "REJECTED"


def test_restructuring_group_approve_not_found(governance_auth_token):
    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    r = client.post("/api/v1/restructuring-groups/DOES-NOT-EXIST/approve", headers=headers)
    assert r.status_code == 404


# ── API: AI Intelligence governance (TASK-F fase 1: Bobot CBS) ──────────

def test_ai_intelligence_model_config():
    r = client.get("/api/v1/ai-intelligence/model-config")
    assert r.status_code == 200
    body = r.json()
    assert len(body["cbs_weights"]) == 4
    assert abs(sum(w["weight"] for w in body["cbs_weights"]) - 100) < 0.01
    # ai_reasoning_output sudah dibangun (ai-reasoning-api-upgrade-tasks.md) —
    # bukan placeholder statis lagi, jadi hanya bentuk & tipe field yang
    # dites di sini, bukan nilai pasti (bergantung AI_REASONING_ENABLED dan
    # histori baris 7 hari terakhir, yang bisa berbeda-beda per environment).
    ai_reasoning = body["model_health"]["ai_reasoning"]
    assert isinstance(ai_reasoning["available"], bool)
    assert isinstance(ai_reasoning["note"], str) and ai_reasoning["note"]
    assert "last_generated_at" in ai_reasoning
    assert isinstance(ai_reasoning["total_7d"], int)
    assert ai_reasoning["success_rate_7d"] is None or isinstance(ai_reasoning["success_rate_7d"], float)


def test_ai_intelligence_weighting_parameters_valid_sum(governance_auth_token):
    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    payload = [
        {"label": "WEIGHT_PAYMENT_RATE", "weight": 30, "description": "d"},
        {"label": "WEIGHT_PTP_RELIABILITY", "weight": 25, "description": "d"},
        {"label": "WEIGHT_INTERACTION", "weight": 20, "description": "d"},
        {"label": "WEIGHT_DELAY_SCORE", "weight": 25, "description": "d"},
    ]
    r = client.put("/api/v1/ai-intelligence/weighting-parameters", json=payload, headers=headers)
    assert r.status_code == 200
    assert sum(w["weight"] for w in r.json()) == 100

    log = client.get("/api/v1/ai-intelligence/operational-log")
    assert log.status_code == 200
    assert log.json()[0]["action"] == "WEIGHTING_UPDATE"
    assert log.json()[0]["user"] == "test.smoke.governance"
    assert log.json()[0]["status"] == "Success"


def test_ai_intelligence_weighting_parameters_invalid_sum(governance_auth_token):
    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    payload = [
        {"label": "WEIGHT_PAYMENT_RATE", "weight": 50, "description": "d"},
        {"label": "WEIGHT_PTP_RELIABILITY", "weight": 25, "description": "d"},
        {"label": "WEIGHT_INTERACTION", "weight": 20, "description": "d"},
        {"label": "WEIGHT_DELAY_SCORE", "weight": 25, "description": "d"},
    ]
    r = client.put("/api/v1/ai-intelligence/weighting-parameters", json=payload, headers=headers)
    assert r.status_code == 400


# ── API: AI Intelligence Sync (training-if-missing + scoring, background job) ──
#
# CATATAN: test di bawah ini HANYA menguji wiring endpoint (202 -> 409,
# bentuk response GET status) — subprocess training/scoring di-monkeypatch
# jadi no-op cepat (`_run_script` diganti sleep 0.5 detik), TIDAK menjalankan
# training/scoring ML sungguhan (training 4 model + scoring bisa makan waktu
# menit, tidak layak jadi bagian pytest suite). Verifikasi end-to-end
# SESUNGGUHNYA (POST /ai-intelligence/sync ASLI lalu poll GET /sync/status
# sampai "completed", cek ke-4 model type ke-train + registry.json terisi +
# ai_intelligence_output ke-update) HARUS dilakukan manual terpisah — lambat,
# sengaja tidak dijalankan otomatis di sini.

def test_ai_intelligence_sync_status_idle_reflects_db():
    r = client.get("/api/v1/ai-intelligence/sync/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("idle", "running", "completed", "failed")
    assert isinstance(body["steps"], list)
    assert "last_scored_at" in body  # boleh None (tabel kosong) atau string ISO datetime


def test_ai_intelligence_sync_start_then_conflict(monkeypatch, governance_auth_token):
    import services.ai_intelligence_sync_service as sync_module

    def _fake_run_script(relative_path):
        time.sleep(0.5)
        return True, None

    monkeypatch.setattr(sync_module.AiIntelligenceSyncService, "_run_script", staticmethod(_fake_run_script))

    headers = {"Authorization": f"Bearer {governance_auth_token}"}
    r1 = client.post("/api/v1/ai-intelligence/sync", headers=headers)
    assert r1.status_code == 202
    body = r1.json()
    assert body["status"] == "running"
    assert body["job_id"]

    r2 = client.post("/api/v1/ai-intelligence/sync", headers=headers)
    assert r2.status_code == 409


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

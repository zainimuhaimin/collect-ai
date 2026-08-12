"""Unit test murni untuk modul AI Reasoning (post-presentation-review-tasks.md
TASK-E4). BEDA dari test_auth.py/test_smoke.py — TIDAK butuh Postgres sama
sekali. build_payload, compute_source_signature, compute_nba_spread, dan
_build_fallback_or_failed semuanya fungsi/metode murni yang beroperasi pada
dataclass domain, jadi diuji langsung dengan objek sintetis.

Test untuk `include_rule_nba` pada build_payload() (TASK-E6) ada di bagian
"ablation anchoring" di bawah.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import AiScoringSnapshot, ContractDetail
from services.ai_reasoning_payload import build_payload, compute_nba_spread, compute_source_signature
from services.ai_reasoning_service import AiReasoningService
from services.gemini_client import GeminiError


def _make_scoring(
    nba_recommendation=None,
    recovery_score=0.4,
    self_cure_probability=0.1,
    roll_forward_risk=0.5,
    ptp_success_probability=0.2,
    risk_segment="Cannot Pay",
    scoring_date=date(2026, 8, 1),
    nba_trigger=None,
):
    return AiScoringSnapshot(
        recovery_score=recovery_score,
        risk_segment=risk_segment,
        self_cure_probability=self_cure_probability,
        roll_forward_risk=roll_forward_risk,
        ptp_success_probability=ptp_success_probability,
        nba_recommendation=nba_recommendation,
        confidence_level=0.8,
        scoring_date=scoring_date,
        nba_trigger=nba_trigger,
    )


def _make_contract(
    contract_no="CTR-TEST-1",
    cust_id="CUST-TEST",
    ai_scoring=None,
    dpd_current=10,
    principal_ots=10_000.0,
    interest_ots=1_000.0,
    payment_history=None,
):
    return ContractDetail(
        contract_no=contract_no,
        cust_id=cust_id,
        cust_name="Test Debitur",
        product_type="KMG",
        cycle="C1",
        prev_cycle=None,
        closed_via_restructure=False,
        new_contract_no=None,
        loan_amount=100_000.0,
        installment_amount=5_000.0,
        interest_rate=0.1,
        maturity_date=date(2027, 1, 1),
        remaining_tenor_months=6,
        dpd_current=dpd_current,
        overdue_installment_count=2,
        late_fee_amount=0.0,
        ambc=0.0,
        principal_ots=principal_ots,
        interest_ots=interest_ots,
        ai_scoring=ai_scoring,
        payment_history=payment_history or [],
    )


# ── build_payload() — TASK-E1: 4 skor model per kontrak ─────────────────────


def test_build_payload_includes_all_four_scores_per_contract():
    scoring = _make_scoring(
        nba_recommendation="Somasi",
        recovery_score=0.42,
        self_cure_probability=0.15,
        roll_forward_risk=0.6,
        ptp_success_probability=0.3,
    )
    contract = _make_contract(ai_scoring=scoring)

    payload = build_payload("CUST-TEST", None, [contract])
    block = payload["contracts"][0]

    assert block["recovery_score"] == 0.42
    assert block["self_cure_probability"] == 0.15
    assert block["ptp_success_probability"] == 0.3
    # roll_forward_risk WAJIB self-describing (nilainya P(tidak bayar), bukan
    # P(bayar) — lihat komentar AiScoringSnapshot.roll_forward_risk).
    assert block["roll_forward_risk_prob_not_paying"] == 0.6
    assert "roll_forward_risk" not in block


def test_build_payload_omits_scores_for_unscored_contract():
    contract = _make_contract(ai_scoring=None)
    payload = build_payload("CUST-TEST", None, [contract])
    block = payload["contracts"][0]

    for key in ("recovery_score", "self_cure_probability", "ptp_success_probability",
                "roll_forward_risk_prob_not_paying", "risk_segment"):
        assert key not in block, f"{key} tidak seharusnya ada untuk kontrak belum discoring"


# ── build_payload(include_rule_nba=...) — TASK-E6 ablation anchoring ───────


def test_build_payload_includes_rule_nba_by_default():
    scoring = _make_scoring(nba_recommendation="Somasi", nba_trigger="high_dpd")
    contract = _make_contract(ai_scoring=scoring)

    payload = build_payload("CUST-TEST", None, [contract])
    block = payload["contracts"][0]

    assert block["nba_recommendation"] == "Somasi"
    assert block["nba_trigger"] == "high_dpd"
    assert payload["portfolio_rollup"]["nba_spread"] == ["Somasi"]


def test_build_payload_omits_rule_nba_when_disabled():
    scoring = _make_scoring(nba_recommendation="Somasi", nba_trigger="high_dpd")
    contract = _make_contract(ai_scoring=scoring)

    payload = build_payload("CUST-TEST", None, [contract], include_rule_nba=False)
    block = payload["contracts"][0]

    assert "nba_recommendation" not in block
    assert "nba_trigger" not in block
    assert "nba_spread" not in payload["portfolio_rollup"]
    # Skor model & fakta lain TIDAK terpengaruh — hanya rekomendasi rule NBA
    # yang dihilangkan, bukan seluruh blok kontrak.
    assert block["risk_segment"] == scoring.risk_segment
    assert block["recovery_score"] == scoring.recovery_score


# ── compute_source_signature() — cache staleness ────────────────────────────


def test_source_signature_stable_for_same_inputs():
    c1 = _make_contract(contract_no="CTR-A", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 1)))
    c2 = _make_contract(contract_no="CTR-A", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 1)))
    assert compute_source_signature([c1]) == compute_source_signature([c2])


def test_source_signature_changes_when_scoring_date_changes():
    c1 = _make_contract(contract_no="CTR-A", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 1)))
    c2 = _make_contract(contract_no="CTR-A", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 2)))
    assert compute_source_signature([c1]) != compute_source_signature([c2])


def test_source_signature_independent_of_contract_order():
    c1 = _make_contract(contract_no="CTR-A", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 1)))
    c2 = _make_contract(contract_no="CTR-B", ai_scoring=_make_scoring(scoring_date=date(2026, 8, 1)))
    assert compute_source_signature([c1, c2]) == compute_source_signature([c2, c1])


# ── compute_nba_spread() + perhitungan nba_agreement — TASK-E2 ─────────────
# nba_agreement TIDAK LAGI self-report LLM (lihat catatan di
# ai_reasoning_prompt.py::build_response_schema()) — dihitung di
# ai_reasoning_service.py dengan logika yang sama seperti di bawah ini.


def _agreement_for(primary_nba_action, active_contracts):
    nba_spread = compute_nba_spread(active_contracts)
    if not nba_spread:
        return None
    return "AGREE" if primary_nba_action in nba_spread else "DIFFER"


def test_nba_spread_deduplicates_and_sorts():
    contracts = [
        _make_contract("A", ai_scoring=_make_scoring(nba_recommendation="WA")),
        _make_contract("B", ai_scoring=_make_scoring(nba_recommendation="Somasi")),
        _make_contract("C", ai_scoring=_make_scoring(nba_recommendation="WA")),
    ]
    assert compute_nba_spread(contracts) == ["Somasi", "WA"]


def test_agreement_is_agree_when_llm_matches_rule_spread():
    contracts = [_make_contract(ai_scoring=_make_scoring(nba_recommendation="Somasi"))]
    assert _agreement_for("Somasi", contracts) == "AGREE"


def test_agreement_is_differ_when_llm_diverges_from_rule_spread():
    contracts = [_make_contract(ai_scoring=_make_scoring(nba_recommendation="WA"))]
    assert _agreement_for("Pickup", contracts) == "DIFFER"


def test_agreement_is_none_when_no_contract_scored():
    contracts = [_make_contract(ai_scoring=None)]
    assert _agreement_for("Somasi", contracts) is None


# ── _build_fallback_or_failed() — jalur degradasi ───────────────────────────
# Metode ini murni (tidak menyentuh self._customers/_contracts/_ai_reasoning/
# _gemini), jadi service diinstansiasi dengan repo None — cukup untuk menguji
# logikanya tanpa DB.


def _service():
    return AiReasoningService(
        customer_repository=None,
        contract_repository=None,
        ai_reasoning_repository=None,
        gemini_client=None,
    )


def test_fallback_uses_largest_ots_contract_as_template_source():
    small = _make_contract(
        "CTR-SMALL", principal_ots=1_000.0, interest_ots=0.0,
        ai_scoring=_make_scoring(nba_recommendation="WA", risk_segment="Can Pay"),
    )
    large = _make_contract(
        "CTR-LARGE", principal_ots=50_000.0, interest_ots=0.0,
        ai_scoring=_make_scoring(nba_recommendation="Somasi", risk_segment="Won't Pay"),
    )
    exc = GeminiError("quota habis", kind="quota")

    record = _service()._build_fallback_or_failed(
        "CUST-TEST", "sig123", [small, large], exc, payload_bytes=100
    )

    assert record.status == "FALLBACK"
    assert record.primary_nba_action == "Somasi"
    assert "Won't Pay" in record.summary
    assert record.error_code == "gemini_quota"
    assert "[Template otomatis" in record.summary


def test_fallback_becomes_failed_when_no_scored_contract_available():
    unscored = _make_contract(ai_scoring=None)
    exc = GeminiError("timeout", kind="timeout")

    record = _service()._build_fallback_or_failed(
        "CUST-TEST", "sig123", [unscored], exc, payload_bytes=50
    )

    assert record.status == "FAILED"
    assert record.error_code == "gemini_timeout"
    assert record.summary is None


def test_fallback_primary_nba_action_none_when_rule_nba_not_in_enum():
    # nba_recommendation di luar NBA_ACTIONS (data korup/legacy) tidak boleh
    # lolos sebagai primary_nba_action di record fallback.
    contract = _make_contract(
        ai_scoring=_make_scoring(nba_recommendation="SMS", risk_segment="Cannot Pay")
    )
    exc = GeminiError("http 500", kind="http")

    record = _service()._build_fallback_or_failed(
        "CUST-TEST", "sig123", [contract], exc, payload_bytes=50
    )

    assert record.status == "FALLBACK"
    assert record.primary_nba_action is None

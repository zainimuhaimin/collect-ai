"""Unit test murni untuk Tier 1-3 evaluasi AI Reasoning (TASK-E5). Semua
fungsi yang diuji di sini beroperasi pada dict polos — TIDAK butuh Postgres
maupun panggilan LLM sungguhan (Tier 2 diuji dengan judge_client palsu)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ai_reasoning_eval import (
    check_agreement_consistency,
    check_contract_integrity,
    check_numeric_grounding,
    check_urgency_monotonic,
    check_valid_enum,
    run_tier1_checks,
    run_tier2_judge,
    run_tier3_self_consistency,
)
from services.llm_client import LlmError, LlmResult


def _record(**overrides):
    base = {
        "summary": "Debitur ini memiliki 2 kontrak aktif.",
        "customer_treatment_strategy": "Hubungi lewat WA dalam 3 hari.",
        "key_factors": [],
        "primary_nba_action": "WA",
        "primary_nba_rationale": "Masih tahap awal.",
        "per_contract_focus": [
            {"contract_no": "CTR-1", "urgency": "LOW", "note": "Baru menunggak, belum lama."},
        ],
        "consistency_note": "Konsisten.",
        "nba_agreement": "AGREE",
        "analyzed_contract_nos": ["CTR-1"],
    }
    base.update(overrides)
    return base


# ── numeric grounding ────────────────────────────────────────────────────

def test_numeric_grounding_flags_fabricated_number():
    record = _record(summary="Total tunggakan mencapai Rp 999.999.999.")
    payload = {"contracts": [{"total_ots": 5_000_000}]}
    result = check_numeric_grounding(record, payload)
    assert result["unsupported_count"] >= 1


def test_numeric_grounding_accepts_percent_form_of_fraction():
    # payload punya fraksi 0.82; narasi mengutip "82%" — harus dianggap grounded
    record = _record(summary="82% dari total OTS sedang menunggak.")
    payload = {"portfolio_rollup": {"arrears_ots_share": 0.82}}
    result = check_numeric_grounding(record, payload)
    assert result["unsupported_count"] == 0


def test_numeric_grounding_accepts_rupiah_thousands_format():
    record = _record(summary="Total OTS sebesar Rp 45.000.000.")
    payload = {"contracts": [{"total_ots": 45_000_000}]}
    result = check_numeric_grounding(record, payload)
    assert result["unsupported_count"] == 0


def test_numeric_grounding_ignores_small_generic_counts():
    record = _record(summary="Debitur ini memiliki 2 kontrak aktif.")
    payload = {"contracts": []}
    result = check_numeric_grounding(record, payload)
    assert result["unsupported_count"] == 0


# ── contract integrity ───────────────────────────────────────────────────

def test_contract_integrity_detects_hallucinated_contract():
    record = _record(
        analyzed_contract_nos=["CTR-1"],
        per_contract_focus=[{"contract_no": "CTR-999", "urgency": "LOW", "note": "x"}],
    )
    result = check_contract_integrity(record)
    assert result["has_hallucination"] is True
    assert "CTR-999" in result["hallucinated_contract_nos"]


def test_contract_integrity_detects_missing_coverage():
    record = _record(
        analyzed_contract_nos=["CTR-1", "CTR-2"],
        per_contract_focus=[{"contract_no": "CTR-1", "urgency": "LOW", "note": "x"}],
    )
    result = check_contract_integrity(record)
    assert result["covers_all"] is False
    assert "CTR-2" in result["missing_contract_nos"]


def test_contract_integrity_passes_when_exact_match():
    record = _record(
        analyzed_contract_nos=["CTR-1"],
        per_contract_focus=[{"contract_no": "CTR-1", "urgency": "LOW", "note": "x"}],
    )
    result = check_contract_integrity(record)
    assert result["has_hallucination"] is False
    assert result["covers_all"] is True


# ── agreement consistency ────────────────────────────────────────────────

def test_agreement_consistency_flags_mismatch():
    record = _record(primary_nba_action="Somasi", nba_agreement="AGREE")
    result = check_agreement_consistency(record, nba_spread=["WA", "Deskcoll"])
    assert result["expected"] == "DIFFER"
    assert result["consistent"] is False


def test_agreement_consistency_none_when_no_spread():
    record = _record(nba_agreement=None)
    result = check_agreement_consistency(record, nba_spread=[])
    assert result["expected"] is None
    assert result["consistent"] is True


# ── urgency monotonicity ─────────────────────────────────────────────────

def test_urgency_monotonic_flags_severe_inversion():
    record = _record(per_contract_focus=[
        {"contract_no": "CTR-LOW-DPD", "urgency": "CRITICAL", "note": "x"},
        {"contract_no": "CTR-HIGH-DPD", "urgency": "LOW", "note": "y"},
    ])
    dpd_by_contract = {"CTR-LOW-DPD": 1, "CTR-HIGH-DPD": 300}
    result = check_urgency_monotonic(record, dpd_by_contract)
    assert result["inversions"] >= 1


def test_urgency_monotonic_allows_adjacent_level_difference():
    record = _record(per_contract_focus=[
        {"contract_no": "CTR-A", "urgency": "MEDIUM", "note": "x"},
        {"contract_no": "CTR-B", "urgency": "HIGH", "note": "y"},
    ])
    dpd_by_contract = {"CTR-A": 100, "CTR-B": 90}
    result = check_urgency_monotonic(record, dpd_by_contract)
    assert result["inversions"] == 0


# ── enum validity ────────────────────────────────────────────────────────

def test_valid_enum_rejects_unknown_nba_action():
    record = _record(primary_nba_action="Telepon")
    result = check_valid_enum(record)
    assert result["primary_nba_action_valid"] is False


# ── run_tier1_checks (integrasi ringan) ──────────────────────────────────

def test_run_tier1_checks_all_pass_on_clean_record():
    record = _record()
    payload = {"contracts": [{"total_ots": 5_000_000}]}
    result = run_tier1_checks(record, payload, nba_spread=["WA"], dpd_by_contract={"CTR-1": 5})
    assert result["contract_hallucination"] is False
    assert result["contract_coverage_gap"] is False
    assert result["agreement_consistent"] is True
    assert result["valid_enum"] is True


# ── Tier 2 — judge (dengan klien palsu, tanpa HTTP sungguhan) ────────────

class _FakeJudgeOk:
    model = "fake-judge"

    def generate(self, system_instruction, payload, response_schema):
        import json
        return LlmResult(
            text=json.dumps({
                "faithfulness": 4.5, "actionability": 4.0,
                "internal_consistency": 5.0, "key_factors_alignment": 3.5,
            }),
            model_used="fake-judge-v1",
        )


class _FakeJudgeMalformed:
    model = "fake-judge"

    def generate(self, system_instruction, payload, response_schema):
        return LlmResult(text="bukan json valid", model_used="fake-judge-v1")


class _FakeJudgeTimeout:
    model = "fake-judge"

    def generate(self, system_instruction, payload, response_schema):
        raise LlmError("timeout", kind="timeout")


def test_tier2_judge_skipped_when_no_client():
    result = run_tier2_judge(None, _record(), {"contracts": []})
    assert result["judge_skipped"] is True
    assert result["judge_failed"] is False


def test_tier2_judge_scores_valid_response():
    result = run_tier2_judge(_FakeJudgeOk(), _record(), {"contracts": []})
    assert result["judge_failed"] is False
    assert result["faithfulness_score"] == 4.5


def test_tier2_judge_failure_is_not_scored_zero():
    """Kegagalan parse HARUS jadi judge_failed=True, BUKAN skor 0 — skor 0
    akan mencemari rata-rata kalau dirata-rata bersama skor yang valid."""
    result = run_tier2_judge(_FakeJudgeMalformed(), _record(), {"contracts": []})
    assert result["judge_failed"] is True
    assert "faithfulness_score" not in result


def test_tier2_judge_timeout_is_judge_failure():
    result = run_tier2_judge(_FakeJudgeTimeout(), _record(), {"contracts": []})
    assert result["judge_failed"] is True


# ── Tier 3 — self-consistency ─────────────────────────────────────────────

def test_tier3_consistent_when_all_actions_same():
    result = run_tier3_self_consistency(["WA", "WA", "WA"])
    assert result["is_consistent"] is True
    assert result["distinct_primary_actions"] == 1


def test_tier3_inconsistent_when_actions_differ():
    result = run_tier3_self_consistency(["WA", "Visit", "WA"])
    assert result["is_consistent"] is False
    assert result["distinct_primary_actions"] == 2

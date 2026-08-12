"""Evaluasi AI Reasoning Tier 1-3 (post-presentation-review-tasks.md TASK-E5).

Tier 4 (latent oracle) SENGAJA TIDAK di sini — itu analisis batch lintas
banyak kontrak yang butuh file latents faker (`_audit_latents.parquet`,
tidak pernah masuk DB), beda sifat dari evaluasi per-output di sini. Lihat
`scripts/evaluate_tier4_oracle.py`.

Fungsi Tier 1/2/3 di modul ini sengaja menerima/mengembalikan `dict` polos
(bukan domain model backend) — supaya bisa ditest tanpa DB/FastAPI (pola
sama dengan `build_payload()` di ai_reasoning_payload.py) dan dipanggil dari
script standalone (`scripts/run_ai_reasoning_eval.py`) maupun dari backend.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from core.config import settings
from services.ai_reasoning_prompt import NBA_ACTIONS
from services.llm_client import LlmError
from services.openai_compat_client import OpenAiCompatClient

URGENCY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
URGENCY_RANK = {lvl: i for i, lvl in enumerate(URGENCY_LEVELS)}

EVALUATOR_VERSION = "v1"


def build_judge_client() -> Optional[OpenAiCompatClient]:
    """None kalau judge_enabled=False ATAU belum ada key — Tier 2 dilewati
    dengan status jelas (judge_skipped), bukan error. Sama pola dengan
    `build_gemini_client()` di ai_reasoning_service.py."""
    if not settings.judge_enabled or not settings.judge_api_keys:
        return None
    return OpenAiCompatClient(
        base_url=settings.judge_api_base_url,
        api_keys=settings.judge_api_keys,
        model=settings.judge_model,
        timeout_seconds=settings.judge_timeout_seconds,
    )


# ══════════════════════════════════════════════════════════════════════════
# TIER 1 — deterministic checks (tanpa LLM, jalankan pada 100% output)
# ══════════════════════════════════════════════════════════════════════════

_NUMBER_TOKEN_RE = re.compile(r"\d[\d.,]*\d|\d+")


def _parse_id_number(tok: str) -> Optional[float]:
    """Parse token angka format Indonesia (titik=ribuan, koma=desimal) atau
    format polos (skor 0-1, mis. "0.75" dari data mentah yang ikut dikutip)."""
    tok = tok.strip().rstrip(".,")
    if not tok:
        return None
    has_comma, has_dot = "," in tok, "." in tok
    try:
        if has_comma and has_dot:
            candidate = tok.replace(".", "").replace(",", ".")
        elif has_comma:
            parts = tok.split(",")
            candidate = tok.replace(",", ".") if len(parts) == 2 and len(parts[1]) <= 2 else tok.replace(",", "")
        elif has_dot:
            parts = tok.split(".")
            candidate = tok if len(parts) == 2 and len(parts[1]) <= 2 else tok.replace(".", "")
        else:
            candidate = tok
        return float(candidate)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list:
    if not text:
        return []
    out = []
    for tok in _NUMBER_TOKEN_RE.findall(text):
        val = _parse_id_number(tok)
        if val is not None:
            out.append(val)
    return out


def _numeric_leaves(obj, out: list) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numeric_leaves(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numeric_leaves(v, out)


def _payload_number_pool(payload: dict) -> list:
    """Kumpulkan semua angka di payload PLUS bentuk turunan yang wajar
    dikutip narasi (persen <-> fraksi, dibulatkan ke juta/ribu) — supaya
    toleransi format tidak menghasilkan unsupported-claim palsu untuk angka
    yang sebenarnya valid, hanya beda representasi."""
    raw = []
    _numeric_leaves(payload, raw)
    pool = set()
    for v in raw:
        pool.add(round(v, 6))
        pool.add(round(v))
        pool.add(round(v * 100, 2))
        pool.add(round(v / 100, 6))
        for div in (1_000, 1_000_000):
            if abs(v) >= div:
                pool.add(round(v / div, 2))
    return sorted(pool)


def _is_grounded(number: float, pool: list) -> bool:
    if not pool:
        return False
    for p in pool:
        tol = max(0.6, abs(p) * 0.02)
        if abs(number - p) <= tol:
            return True
    return False


def check_numeric_grounding(record: dict, payload: dict) -> dict:
    """Tiap angka yang dikutip summary/customerTreatmentStrategy/keyFactors/
    per_contract_focus.note harus ada di payload (toleransi pembulatan &
    format Rupiah) -> unsupported-claim rate. Angka <=3 dianggap selalu
    grounded — hampir selalu kata ganti jumlah generik ("3 kontrak", "2
    tahun") di narasi Bahasa Indonesia, bukan klaim data yang perlu
    ditelusuri sumbernya."""
    pool = _payload_number_pool(payload)
    texts = [record.get("summary") or "", record.get("customer_treatment_strategy") or ""]
    texts += list(record.get("key_factors") or [])
    for focus in record.get("per_contract_focus") or []:
        texts.append((focus or {}).get("note") or "")

    total, unsupported = 0, 0
    unsupported_examples = []
    for text in texts:
        for num in _extract_numbers(text):
            total += 1
            if num <= 3:
                continue
            if not _is_grounded(num, pool):
                unsupported += 1
                unsupported_examples.append(num)
    rate = (unsupported / total) if total else 0.0
    return {
        "total_numbers_cited": total,
        "unsupported_count": unsupported,
        "unsupported_claim_rate": round(rate, 4),
        "unsupported_examples": unsupported_examples[:10],
    }


def check_contract_integrity(record: dict) -> dict:
    """perContractFocus[].contractNo harus SUBSET dari analyzed_contract_nos
    (deteksi kontrak halusinasi) DAN menutup semuanya (deteksi kontrak yang
    terlewat)."""
    analyzed = set(record.get("analyzed_contract_nos") or [])
    focus_nos = {
        (f or {}).get("contract_no") or (f or {}).get("contractNo")
        for f in (record.get("per_contract_focus") or [])
    }
    focus_nos.discard(None)
    hallucinated = focus_nos - analyzed
    missing = analyzed - focus_nos
    return {
        "hallucinated_contract_nos": sorted(hallucinated),
        "missing_contract_nos": sorted(missing),
        "has_hallucination": bool(hallucinated),
        "covers_all": not missing,
    }


def check_agreement_consistency(record: dict, nba_spread: list) -> dict:
    """nba_agreement TERSIMPAN harus cocok dengan perbandingan yang dihitung
    ULANG dari data (primary_nba_action vs nba_spread) — bukan dipercaya
    begitu saja hanya karena kolomnya sudah dihitung server-side (TASK-E2).
    Ini memverifikasi ULANG hasil E2, bukan mengasumsikannya benar."""
    expected = (
        ("AGREE" if record.get("primary_nba_action") in nba_spread else "DIFFER")
        if nba_spread else None
    )
    stored = record.get("nba_agreement")
    return {"expected": expected, "stored": stored, "consistent": expected == stored}


def check_urgency_monotonic(record: dict, dpd_by_contract: dict) -> dict:
    """Urgensi TIDAK dituntut monoton sempurna terhadap dpd (LLM boleh
    mempertimbangkan faktor lain, mis. collection_sensitivity) — hanya
    pelanggaran BESAR (dpd jauh lebih tinggi diberi urgensi jauh lebih
    rendah, jarak >1 level) ditandai sebagai inversion. Soft-warning,
    bukan hard-fail."""
    pairs = []
    for focus in record.get("per_contract_focus") or []:
        cn = (focus or {}).get("contract_no") or (focus or {}).get("contractNo")
        urgency = (focus or {}).get("urgency")
        if cn in dpd_by_contract and urgency in URGENCY_RANK:
            pairs.append((dpd_by_contract[cn], URGENCY_RANK[urgency]))
    pairs.sort()
    inversions = 0
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            if pairs[i][0] < pairs[j][0] and pairs[i][1] > pairs[j][1] + 1:
                inversions += 1
    return {"n_pairs": len(pairs), "inversions": inversions}


def check_valid_enum(record: dict) -> dict:
    primary_ok = record.get("primary_nba_action") in NBA_ACTIONS
    urgencies = [(f or {}).get("urgency") for f in (record.get("per_contract_focus") or [])]
    urgency_ok = all(u in URGENCY_LEVELS for u in urgencies)
    return {"primary_nba_action_valid": primary_ok, "urgency_values_valid": urgency_ok}


def run_tier1_checks(record: dict, payload: dict, nba_spread: list, dpd_by_contract: dict) -> dict:
    grounding = check_numeric_grounding(record, payload)
    integrity = check_contract_integrity(record)
    agreement = check_agreement_consistency(record, nba_spread)
    urgency = check_urgency_monotonic(record, dpd_by_contract)
    enum_check = check_valid_enum(record)
    return {
        "unsupported_claim_count": grounding["unsupported_count"],
        "unsupported_claim_rate": grounding["unsupported_claim_rate"],
        "contract_hallucination": integrity["has_hallucination"],
        "contract_coverage_gap": not integrity["covers_all"],
        "agreement_consistent": agreement["consistent"],
        "urgency_monotonic": urgency["inversions"] == 0,
        "valid_enum": enum_check["primary_nba_action_valid"] and enum_check["urgency_values_valid"],
        "detail": {
            "grounding": grounding, "integrity": integrity,
            "agreement": agreement, "urgency": urgency, "enum": enum_check,
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# TIER 2 — LLM-as-judge (provider OpenAI-compatible, keluarga model beda)
# ══════════════════════════════════════════════════════════════════════════

class _JudgeScoreSchema(BaseModel):
    faithfulness: float = Field(ge=1, le=5)
    actionability: float = Field(ge=1, le=5)
    internal_consistency: float = Field(ge=1, le=5)
    key_factors_alignment: float = Field(ge=1, le=5)


_JUDGE_INSTRUCTION = (
    "Anda adalah auditor independen yang menilai kualitas SATU analisis kredit "
    "yang dihasilkan sistem AI LAIN (bukan Anda) untuk debitur multifinance di "
    "Indonesia. Anda tidak tahu siapa pembuatnya — nilai objektif berdasarkan "
    "data yang diberikan, jangan bersikap sungkan.\n\n"
    "Input JSON berisi dua bagian: \"input_payload\" (data mentah debitur yang "
    "dilihat sistem AI tersebut) dan \"ai_output\" (hasil analisis yang harus "
    "Anda nilai).\n\n"
    "Beri skor 1-5 (1=sangat buruk, 5=sangat baik) untuk masing-masing:\n"
    "- faithfulness: apakah klaim di ai_output didukung angka NYATA di "
    "input_payload (bukan mengarang angka yang tidak ada)\n"
    "- actionability: apakah rekomendasi cukup konkret untuk ditindaklanjuti "
    "kolektor lapangan\n"
    "- internal_consistency: apakah primaryNbaAction, perContractFocus, dan "
    "consistencyNote saling konsisten satu sama lain\n"
    "- key_factors_alignment: apakah customerTreatmentStrategy benar-benar "
    "mengikuti keyFactors yang disebutkan, bukan generik"
)

_JUDGE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "faithfulness": {"type": "NUMBER"},
        "actionability": {"type": "NUMBER"},
        "internal_consistency": {"type": "NUMBER"},
        "key_factors_alignment": {"type": "NUMBER"},
    },
    "required": ["faithfulness", "actionability", "internal_consistency", "key_factors_alignment"],
}


def run_tier2_judge(judge_client, record: dict, payload: dict) -> dict:
    """`judge_client=None` -> judge_skipped=True (bukan judge_failed) — Tier
    2 memang belum dikonfigurasi (JUDGE_ENABLED=false / tidak ada key), beda
    dari kegagalan panggilan nyata. Kegagalan parse/validasi Pydantic dicatat
    sebagai judge_failed=True dengan skor None — TIDAK dijadikan skor 0, itu
    akan mencemari rata-rata (lihat TASK-E5)."""
    if judge_client is None:
        return {"judge_failed": False, "judge_skipped": True, "reason": "judge_disabled_or_no_key"}

    judge_payload = {
        "input_payload": payload,
        "ai_output": {
            "summary": record.get("summary"),
            "customerTreatmentStrategy": record.get("customer_treatment_strategy"),
            "keyFactors": record.get("key_factors"),
            "primaryNbaAction": record.get("primary_nba_action"),
            "primaryNbaRationale": record.get("primary_nba_rationale"),
            "perContractFocus": record.get("per_contract_focus"),
            "consistencyNote": record.get("consistency_note"),
        },
    }
    try:
        result = judge_client.generate(_JUDGE_INSTRUCTION, judge_payload, _JUDGE_RESPONSE_SCHEMA)
        raw = json.loads(result.text)
        parsed = _JudgeScoreSchema.model_validate(raw)
    except (LlmError, ValidationError, json.JSONDecodeError) as exc:
        return {
            "judge_failed": True, "judge_skipped": False,
            "error": str(exc), "judge_model": settings.judge_model,
        }
    return {
        "judge_failed": False, "judge_skipped": False,
        "judge_model": result.model_used,
        "faithfulness_score": parsed.faithfulness,
        "actionability_score": parsed.actionability,
        "internal_consistency_score": parsed.internal_consistency,
        "key_factors_alignment_score": parsed.key_factors_alignment,
        "raw_response": raw,
    }


# ══════════════════════════════════════════════════════════════════════════
# TIER 3 — self-consistency (K panggilan ulang payload sama, force=True)
# ══════════════════════════════════════════════════════════════════════════

def run_tier3_self_consistency(actions: list) -> dict:
    distinct = sorted(set(a for a in actions if a))
    return {
        "k_calls": len(actions),
        "distinct_primary_actions": len(distinct),
        "actions": actions,
        "is_consistent": len(distinct) <= 1,
    }


# ══════════════════════════════════════════════════════════════════════════
# Persistensi — ai_reasoning_evaluation (tabel TERPISAH dari ai_reasoning_output,
# lihat schema.sql, supaya satu output bisa dievaluasi ulang oleh evaluator_version berbeda)
# ══════════════════════════════════════════════════════════════════════════

def save_evaluation(
    engine, ai_reasoning_output_id: int, tier1: dict, tier2: dict,
    tier3: Optional[dict] = None, evaluator_version: str = EVALUATOR_VERSION,
) -> None:
    from sqlalchemy import text

    tier3 = tier3 or {}
    params = {
        "oid": ai_reasoning_output_id,
        "ev": evaluator_version,
        "t1_count": tier1["unsupported_claim_count"],
        "t1_rate": tier1["unsupported_claim_rate"],
        "t1_halluc": tier1["contract_hallucination"],
        "t1_gap": tier1["contract_coverage_gap"],
        "t1_agree": tier1["agreement_consistent"],
        "t1_mono": tier1["urgency_monotonic"],
        "t1_enum": tier1["valid_enum"],
        "t1_detail": json.dumps(tier1["detail"], default=str),
        "t2_model": tier2.get("judge_model"),
        "t2_faith": tier2.get("faithfulness_score"),
        "t2_action": tier2.get("actionability_score"),
        "t2_consist": tier2.get("internal_consistency_score"),
        "t2_align": tier2.get("key_factors_alignment_score"),
        "t2_failed": tier2.get("judge_failed", False),
        "t2_error": tier2.get("error"),
        "t2_raw": json.dumps(tier2.get("raw_response")) if tier2.get("raw_response") is not None else None,
        "t3_k": tier3.get("k_calls"),
        "t3_distinct": tier3.get("distinct_primary_actions"),
        "t3_actions": json.dumps(tier3.get("actions")) if tier3.get("actions") is not None else None,
    }
    with engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO ai_reasoning_evaluation (
                ai_reasoning_output_id, evaluator_version,
                tier1_unsupported_claim_count, tier1_unsupported_claim_rate,
                tier1_contract_hallucination, tier1_contract_coverage_gap,
                tier1_agreement_consistent, tier1_urgency_monotonic, tier1_valid_enum,
                tier1_detail,
                tier2_judge_model, tier2_faithfulness_score, tier2_actionability_score,
                tier2_internal_consistency_score, tier2_key_factors_alignment_score,
                tier2_judge_failed, tier2_judge_error, tier2_raw_response,
                tier3_k_calls, tier3_distinct_primary_actions, tier3_actions
            ) VALUES (
                :oid, :ev,
                :t1_count, :t1_rate, :t1_halluc, :t1_gap, :t1_agree, :t1_mono, :t1_enum,
                CAST(:t1_detail AS JSONB),
                :t2_model, :t2_faith, :t2_action, :t2_consist, :t2_align,
                :t2_failed, :t2_error, CAST(:t2_raw AS JSONB),
                :t3_k, :t3_distinct, CAST(:t3_actions AS JSONB)
            )
            ON CONFLICT (ai_reasoning_output_id, evaluator_version) DO UPDATE SET
                tier1_unsupported_claim_count = EXCLUDED.tier1_unsupported_claim_count,
                tier1_unsupported_claim_rate = EXCLUDED.tier1_unsupported_claim_rate,
                tier1_contract_hallucination = EXCLUDED.tier1_contract_hallucination,
                tier1_contract_coverage_gap = EXCLUDED.tier1_contract_coverage_gap,
                tier1_agreement_consistent = EXCLUDED.tier1_agreement_consistent,
                tier1_urgency_monotonic = EXCLUDED.tier1_urgency_monotonic,
                tier1_valid_enum = EXCLUDED.tier1_valid_enum,
                tier1_detail = EXCLUDED.tier1_detail,
                tier2_judge_model = EXCLUDED.tier2_judge_model,
                tier2_faithfulness_score = EXCLUDED.tier2_faithfulness_score,
                tier2_actionability_score = EXCLUDED.tier2_actionability_score,
                tier2_internal_consistency_score = EXCLUDED.tier2_internal_consistency_score,
                tier2_key_factors_alignment_score = EXCLUDED.tier2_key_factors_alignment_score,
                tier2_judge_failed = EXCLUDED.tier2_judge_failed,
                tier2_judge_error = EXCLUDED.tier2_judge_error,
                tier2_raw_response = EXCLUDED.tier2_raw_response,
                tier3_k_calls = EXCLUDED.tier3_k_calls,
                tier3_distinct_primary_actions = EXCLUDED.tier3_distinct_primary_actions,
                tier3_actions = EXCLUDED.tier3_actions,
                evaluated_at = now()
            """
        ), params)

#!/usr/bin/env python3
"""TASK-E5 — Jalankan evaluasi Tier 1-3 AI Reasoning pada sampel debitur.

Untuk tiap debitur: generate ULANG (force=True) lewat AiReasoningService ASLI
(sama kode yang dipakai endpoint POST /customers/{id}/ai-reasoning) supaya
payload yang dievaluasi Tier 1/2 PERSIS payload yang benar-benar dilihat LLM
saat itu — bukan direkonstruksi dari state yang mungkin sudah berubah
(masalah staleness yang sama seperti nba_agreement, lihat compute_source_
signature di ai_reasoning_payload.py).

Tier 3 (self-consistency) hanya dijalankan untuk subset (--tier3-sample,
default 5 debitur) karena butuh K panggilan LLM tambahan PER debitur — biaya
K x N, dibatasi eksplisit di sini, bukan di semua sampel.

Pakai:
    python scripts/run_ai_reasoning_eval.py --limit 20 --tier3-sample 5 --tier3-k 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend")
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from core.dependencies import (  # noqa: E402
    get_ai_reasoning_repository,
    get_contract_repository,
    get_customer_repository,
    get_engine,
)
from services.ai_reasoning_eval import (  # noqa: E402
    build_judge_client,
    run_tier1_checks,
    run_tier2_judge,
    run_tier3_self_consistency,
    save_evaluation,
)
from services.ai_reasoning_payload import build_payload, compute_nba_spread  # noqa: E402
from services.ai_reasoning_service import AiReasoningService, build_gemini_client  # noqa: E402


def _sample_customers(engine, limit: int) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT cs.cust_id FROM contract_snapshot cs "
            "JOIN ai_intelligence_output ai ON ai.contract_no = cs.contract_no "
            "WHERE cs.status = 'aktif' ORDER BY cs.cust_id LIMIT :limit"
        ), {"limit": limit})
        return [r[0] for r in rows]


def _output_id(engine, cust_id, source_signature, prompt_version):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM ai_reasoning_output "
            "WHERE cust_id=:c AND source_signature=:s AND prompt_version=:p "
            "ORDER BY created_at DESC LIMIT 1"
        ), {"c": cust_id, "s": source_signature, "p": prompt_version}).fetchone()
        return row[0] if row else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20, help="Jumlah debitur yang dievaluasi Tier 1/2.")
    parser.add_argument("--tier3-sample", type=int, default=5, help="Jumlah debitur untuk Tier 3.")
    parser.add_argument("--tier3-k", type=int, default=3, help="K panggilan ulang per debitur untuk Tier 3.")
    parser.add_argument(
        "--sleep-seconds", type=float, default=0.0,
        help="Jeda antar panggilan Gemini — naikkan kalau kena gemini_quota (429) "
        "akibat rate-limit per-menit tier gratis, bukan kuota harian.",
    )
    args = parser.parse_args()

    engine = get_engine()
    customer_repo = get_customer_repository()
    contract_repo = get_contract_repository()
    ai_reasoning_repo = get_ai_reasoning_repository()
    gemini = build_gemini_client()
    judge = build_judge_client()

    if gemini is None:
        print(
            "⚠️  Gemini client tidak terkonfigurasi (AI_REASONING_ENABLED=false atau "
            "tidak ada key) — tidak bisa generate output baru untuk dievaluasi. Berhenti.",
            file=sys.stderr,
        )
        sys.exit(1)
    if judge is None:
        print("⚠️  Judge (Tier 2) tidak dikonfigurasi (JUDGE_ENABLED=false / tidak ada key) — dilewati, dicatat sebagai judge_skipped.")

    service = AiReasoningService(customer_repo, contract_repo, ai_reasoning_repo, gemini)

    cust_ids = _sample_customers(engine, args.limit)
    print(f"Sampel debitur: {len(cust_ids)}")

    results = []
    for i, cust_id in enumerate(cust_ids):
        if i > 0 and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
        outcome = service.generate(cust_id, force=True)
        # gemini_quota (429 rate-limit per-menit tier gratis, BUKAN kuota
        # harian ai_reasoning_daily_call_limit) layak di-retry dengan
        # backoff — beda dari kegagalan lain (validasi/timeout) yang
        # dibiarkan jatuh ke FALLBACK apa adanya.
        retry_delays = [8.0, 20.0]
        while (
            outcome.record is not None and outcome.record.status == "FALLBACK"
            and outcome.record.error_code == "gemini_quota" and retry_delays
        ):
            delay = retry_delays.pop(0)
            print(f"    (gemini_quota, retry dalam {delay:.0f}s)")
            time.sleep(delay)
            outcome = service.generate(cust_id, force=True)
        if not outcome.ok or outcome.record is None or outcome.record.status not in ("OK", "FALLBACK"):
            print(f"  [{i+1}/{len(cust_ids)}] {cust_id}: dilewati (status={getattr(outcome.record, 'status', None)}, ok={outcome.ok})")
            continue
        record = outcome.record

        active_contracts = contract_repo.list_active_contracts_for_customer(cust_id)
        behavioral = customer_repo.get_behavioral_raw(cust_id)
        payload = build_payload(cust_id, behavioral, active_contracts)
        # nba_agreement HANYA dihitung server-side untuk status OK (lihat
        # ai_reasoning_service.py::generate) — FALLBACK/FAILED selalu
        # nba_agreement=None secara desain, bukan inkonsistensi. Kirim
        # nba_spread=[] untuk status selain OK supaya check_agreement_
        # consistency membandingkan None vs None (konsisten), bukan
        # None vs "AGREE"/"DIFFER" (false positive).
        nba_spread = compute_nba_spread(active_contracts) if record.status == "OK" else []
        dpd_by_contract = {c.contract_no: c.dpd_current for c in active_contracts}

        record_dict = {
            "summary": record.summary,
            "customer_treatment_strategy": record.customer_treatment_strategy,
            "key_factors": record.key_factors,
            "primary_nba_action": record.primary_nba_action,
            "primary_nba_rationale": record.primary_nba_rationale,
            "per_contract_focus": record.per_contract_focus,
            "consistency_note": record.consistency_note,
            "nba_agreement": record.nba_agreement,
            "analyzed_contract_nos": record.analyzed_contract_nos,
        }

        tier1 = run_tier1_checks(record_dict, payload, nba_spread, dpd_by_contract)
        tier2 = run_tier2_judge(judge, record_dict, payload) if record.status == "OK" else {"judge_skipped": True, "judge_failed": False, "reason": "record_not_OK"}

        tier3 = None
        if i < args.tier3_sample and record.status == "OK":
            actions = [record.primary_nba_action]
            for _ in range(args.tier3_k - 1):
                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)
                repeat = service.generate(cust_id, force=True)
                if repeat.ok and repeat.record is not None:
                    actions.append(repeat.record.primary_nba_action)
            tier3 = run_tier3_self_consistency(actions)

        output_id = _output_id(engine, cust_id, record.source_signature, record.prompt_version)
        if output_id is not None:
            save_evaluation(engine, output_id, tier1, tier2, tier3)

        results.append({
            "cust_id": cust_id, "status": record.status,
            "tier1": tier1, "tier2": tier2, "tier3": tier3,
        })
        print(
            f"  [{i+1}/{len(cust_ids)}] {cust_id}: status={record.status} "
            f"unsupported_rate={tier1['unsupported_claim_rate']:.2%} "
            f"hallucination={tier1['contract_hallucination']} "
            f"agreement_consistent={tier1['agreement_consistent']} "
            f"judge={'skip' if tier2.get('judge_skipped') else ('fail' if tier2.get('judge_failed') else 'ok')}"
            + (f" tier3_consistent={tier3['is_consistent']}" if tier3 else "")
        )

    n = len(results)
    if n == 0:
        print("Tidak ada output yang berhasil dievaluasi.")
        return

    print("\n=== Ringkasan ===")
    print(f"Total dievaluasi: {n}")
    print(f"unsupported_claim_rate rata-rata: {sum(r['tier1']['unsupported_claim_rate'] for r in results) / n:.2%}")
    print(f"contract_hallucination: {sum(r['tier1']['contract_hallucination'] for r in results)}/{n}")
    print(f"agreement_consistent: {sum(r['tier1']['agreement_consistent'] for r in results)}/{n}")
    print(f"urgency_monotonic: {sum(r['tier1']['urgency_monotonic'] for r in results)}/{n}")
    print(f"valid_enum: {sum(r['tier1']['valid_enum'] for r in results)}/{n}")
    judge_ok = [r for r in results if not r["tier2"].get("judge_skipped") and not r["tier2"].get("judge_failed")]
    judge_failed = [r for r in results if r["tier2"].get("judge_failed")]
    judge_skipped = [r for r in results if r["tier2"].get("judge_skipped")]
    print(f"Tier 2 judge: ok={len(judge_ok)} failed={len(judge_failed)} skipped={len(judge_skipped)}")
    if judge_ok:
        for dim in ["faithfulness_score", "actionability_score", "internal_consistency_score", "key_factors_alignment_score"]:
            avg = sum(r["tier2"][dim] for r in judge_ok) / len(judge_ok)
            print(f"  avg {dim}: {avg:.2f}")
    tier3_results = [r for r in results if r["tier3"]]
    if tier3_results:
        consistent = sum(1 for r in tier3_results if r["tier3"]["is_consistent"])
        print(f"Tier 3 self-consistency: {consistent}/{len(tier3_results)} debitur konsisten")

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "ai_reasoning_eval_tier123.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Detail lengkap: {out_path}")


if __name__ == "__main__":
    main()

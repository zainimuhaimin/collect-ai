#!/usr/bin/env python3
"""TASK-E6 — Ablation anchoring rule NBA.

Sampel N debitur, tiap debitur DUA arm:
  A) payload dengan nba_recommendation/nba_trigger/nba_spread (SEPERTI PRODUKSI)
  B) payload TANPA field itu (`include_rule_nba=False`)

Ukur: tingkat kesamaan primaryNbaAction (arm) terhadap rule NBA — kalau arm A
jauh lebih sering "setuju" dengan rule dibanding arm B, itu bukti anchoring
(LLM menjangkar pada rekomendasi yang diberikan alih-alih bernalar sendiri).

⚠️ BYPASS AiReasoningService SEPENUHNYA — memanggil build_payload() +
GeminiClient.generate() LANGSUNG, TIDAK menyentuh cache/DB produksi
(ai_reasoning_output, rate limit harian) sama sekali. Hasil ablation adalah
EKSPERIMEN, bukan output yang boleh bercampur dengan populasi produksi.

Biaya: 2 panggilan generate per debitur (+1 judge kalau nanti dipakai) -> N=50
~100 panggilan Gemini. Diperhitungkan TERPISAH dari
`ai_reasoning_daily_call_limit` (yang menghitung dari tabel ai_reasoning_output,
tidak tersentuh script ini) — tapi tetap tercermin di kuota provider yang
sama, jadi jangan jalankan N besar berulang-ulang di hari yang sama.

Pakai:
    python scripts/ablation_nba.py --n 50 --seed 42 --out reports/ablation_nba.md
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend")
sys.path.insert(0, BACKEND_DIR)

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.dependencies import get_contract_repository, get_customer_repository, get_engine  # noqa: E402
from schemas.ai_reasoning import GeminiReasoningOutputSchema  # noqa: E402
from services.ai_reasoning_payload import build_payload, compute_nba_spread  # noqa: E402
from services.ai_reasoning_prompt import build_instruction, build_response_schema, parse_response_text  # noqa: E402
from services.ai_reasoning_service import build_gemini_client  # noqa: E402
from services.gemini_client import GeminiError  # noqa: E402


def _sample_customers(engine, n: int, seed: int) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT cs.cust_id FROM contract_snapshot cs "
            "JOIN ai_intelligence_output ai ON ai.contract_no = cs.contract_no "
            "WHERE cs.status = 'aktif'"
        ))
        all_ids = [r[0] for r in rows]
    random.Random(seed).shuffle(all_ids)
    return all_ids[:n]


def _one_arm(gemini, cust_id, behavioral, active_contracts, include_rule_nba: bool) -> dict:
    payload = build_payload(cust_id, behavioral, active_contracts, include_rule_nba=include_rule_nba)
    try:
        result = gemini.generate(build_instruction(), payload, build_response_schema())
        parsed = GeminiReasoningOutputSchema.model_validate(parse_response_text(result.text))
        return {"ok": True, "primary_nba_action": parsed.primary_nba_action, "raw": parsed.model_dump()}
    except (GeminiError, ValidationError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "ablation_nba.md"))
    args = parser.parse_args()

    engine = get_engine()
    customer_repo = get_customer_repository()
    contract_repo = get_contract_repository()
    gemini = build_gemini_client()
    if gemini is None:
        print("⚠️  Gemini client tidak terkonfigurasi — tidak bisa menjalankan ablation. Berhenti.", file=sys.stderr)
        sys.exit(1)

    cust_ids = _sample_customers(engine, args.n, args.seed)
    print(f"Sampel: {len(cust_ids)} debitur (target N={args.n}, seed={args.seed})")

    rows = []
    for i, cust_id in enumerate(cust_ids):
        active_contracts = contract_repo.list_active_contracts_for_customer(cust_id)
        behavioral = customer_repo.get_behavioral_raw(cust_id)
        nba_spread = compute_nba_spread(active_contracts)
        if not nba_spread:
            print(f"  [{i+1}/{len(cust_ids)}] {cust_id}: dilewati (tidak ada nba_spread untuk dibandingkan)")
            continue

        arm_a = _one_arm(gemini, cust_id, behavioral, active_contracts, include_rule_nba=True)
        arm_b = _one_arm(gemini, cust_id, behavioral, active_contracts, include_rule_nba=False)
        if not (arm_a["ok"] and arm_b["ok"]):
            print(f"  [{i+1}/{len(cust_ids)}] {cust_id}: dilewati (arm A ok={arm_a['ok']}, arm B ok={arm_b['ok']})")
            continue

        row = {
            "cust_id": cust_id,
            "nba_spread": nba_spread,
            "arm_a_action": arm_a["primary_nba_action"],
            "arm_b_action": arm_b["primary_nba_action"],
            "arm_a_agrees_rule": arm_a["primary_nba_action"] in nba_spread,
            "arm_b_agrees_rule": arm_b["primary_nba_action"] in nba_spread,
        }
        rows.append(row)
        print(
            f"  [{i+1}/{len(cust_ids)}] {cust_id}: rule={nba_spread} "
            f"A={row['arm_a_action']}({'agree' if row['arm_a_agrees_rule'] else 'differ'}) "
            f"B={row['arm_b_action']}({'agree' if row['arm_b_agrees_rule'] else 'differ'})"
        )

    n = len(rows)
    if n == 0:
        print("Tidak ada pasangan arm A/B yang valid — tidak bisa menyimpulkan apa pun.")
        return

    a_agree = sum(r["arm_a_agrees_rule"] for r in rows)
    b_agree = sum(r["arm_b_agrees_rule"] for r in rows)
    a_rate, b_rate = a_agree / n, b_agree / n
    delta = a_rate - b_rate

    dist_a = {}
    dist_b = {}
    for r in rows:
        dist_a[r["arm_a_action"]] = dist_a.get(r["arm_a_action"], 0) + 1
        dist_b[r["arm_b_action"]] = dist_b.get(r["arm_b_action"], 0) + 1

    lines = []
    lines.append("# TASK-E6 — Ablation anchoring rule NBA")
    lines.append("")
    lines.append(f"N pasangan valid: **{n}** (target N={args.n}, seed={args.seed}).")
    lines.append("")
    lines.append("## Tingkat kesamaan primaryNbaAction terhadap rule NBA (nba_spread)")
    lines.append("")
    lines.append(f"- Arm A (dengan rule NBA di payload): **{a_rate:.1%}** ({a_agree}/{n})")
    lines.append(f"- Arm B (TANPA rule NBA di payload): **{b_rate:.1%}** ({b_agree}/{n})")
    lines.append(f"- Delta (A - B): **{delta:+.1%}**")
    lines.append("")
    lines.append("## Distribusi primaryNbaAction per arm")
    lines.append("")
    lines.append(f"- Arm A: {dist_a}")
    lines.append(f"- Arm B: {dist_b}")
    lines.append("")
    lines.append("## Kejujuran statistik")
    lines.append("")
    if n < 30:
        lines.append(
            f"**N={n} terlalu kecil untuk klaim signifikansi statistik.** Angka di atas "
            f"adalah hitungan dan proporsi mentah — TIDAK diklaim signifikan secara "
            f"statistik. Untuk klaim yang lebih kuat, naikkan N (--n) dan catat p-value "
            f"dari uji proporsi berpasangan (mis. McNemar's test, arm A vs B pada debitur "
            f"yang sama)."
        )
    else:
        lines.append(f"N={n}. Tetap disarankan uji McNemar berpasangan untuk klaim signifikansi formal (belum dihitung di sini).")
    lines.append("")
    lines.append("## Keputusan")
    lines.append("")
    if delta >= 0.15:
        decision = (
            f"**Anchoring TERBUKTI** (delta {delta:+.1%} >= ambang indikatif 15 poin persentase yang "
            f"ditetapkan sebelum menjalankan ablation ini). Rekomendasi: buang rule NBA dari payload "
            f"produksi (`include_rule_nba=False` jadi default), nba_agreement tetap dihitung di kode "
            f"dari rule engine (TASK-E2 sudah menyiapkan jalannya — perhitungan agreement TIDAK "
            f"bergantung pada apakah rule NBA ada di payload)."
        )
    elif delta <= -0.15:
        decision = (
            f"**Pola TIDAK terduga** — arm B (tanpa rule NBA) justru LEBIH sering cocok dengan rule "
            f"engine (delta {delta:+.1%}). Ini bukan bukti anchoring; kemungkinan sinyal lain yang "
            f"belum ditelusuri (mis. distribusi sampel, arm order). Tulis apa adanya, jangan "
            f"dipaksakan jadi salah satu narasi."
        )
    else:
        decision = (
            f"**Tidak konklusif / anchoring tidak terbukti** (delta {delta:+.1%}, di bawah ambang "
            f"indikatif 15 poin persentase). Rule NBA AMAN dipertahankan di payload — selain tidak "
            f"terbukti menjangkar LLM, field ini berguna untuk rekonsiliasi (LLM eksplisit diminta "
            f"menjelaskan kalau menyimpang dari rule engine, lihat consistencyNote)."
        )
    lines.append(decision)
    lines.append("")

    md = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(md)
    raw_path = os.path.splitext(args.out)[0] + "_raw.json"
    with open(raw_path, "w") as f:
        json.dump(rows, f, indent=2, default=str)

    print("\n" + md)
    print(f"\n✓ {args.out}")
    print(f"✓ Detail mentah: {raw_path}")


if __name__ == "__main__":
    main()

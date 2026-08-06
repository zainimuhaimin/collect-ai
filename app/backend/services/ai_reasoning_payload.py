"""Payload builder AI Reasoning (ai-reasoning-api-upgrade-tasks.md §5 + §1.1).

`_has_champion()`/`_REGISTRY_PATH` MENDUPLIKASI pola yang sama di
ai_intelligence_sync_service.py (baca registry.json mentah, bukan import
model_registry.py) — konsisten dengan prinsip yang sudah didokumentasikan di
sana: backend TIDAK PERNAH mengimpor modul app/machine-learning/src/ ke
prosesnya sendiri."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import List, Optional

from domain.models import ContractDetail, CustomerBehavioralRaw

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_REGISTRY_PATH = os.path.join(_REPO_ROOT, "app", "machine-learning", "models", "registry.json")

MODEL_TYPES = ("recovery", "self_cure", "roll_forward", "ptp_success")

# NOTE (scope trim, dicatat eksplisit): §8.1 dokumen desain juga meminta
# ringkasan agregat kontrak LUNAS 3 tahun terakhir (jumlah, total, rata-rata
# delay settlement) sebagai konteks tambahan. Belum diimplementasikan di
# iterasi ini — payload sekarang hanya berisi kontrak AKTIF, yang sudah
# menanggung bobot utama tujuan fitur ini (rekonsiliasi NBA lintas kontrak
# aktif). Ringkasan kontrak lunas adalah penyempurnaan konteks, bukan inti
# hyper-personalization, jadi ditunda untuk task terpisah.


def available_models() -> List[str]:
    """model_type yang punya champion di registry.json — dikirim ke LLM
    (`available_models`) supaya ia tidak menyimpulkan "probabilitas rendah"
    dari skor yang sebenarnya TIDAK ADA (temuan #17 di dokumen)."""
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    types = data.get("model_types", {})
    return [mt for mt in MODEL_TYPES if bool(types.get(mt, {}).get("current_champion"))]


def compute_source_signature(active_contracts: List[ContractDetail]) -> str:
    """hash(sorted (contract_no, scoring_date) seluruh kontrak aktif) — cache
    basi otomatis begitu skor diperbarui, kontrak baru ditambahkan, atau
    kontrak ditutup (§4 dokumen)."""
    pairs = sorted(
        (
            c.contract_no,
            c.ai_scoring.scoring_date.isoformat() if c.ai_scoring and c.ai_scoring.scoring_date else "",
        )
        for c in active_contracts
    )
    raw = json.dumps(pairs, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _ots_weighted_average(active_contracts: List[ContractDetail], getter) -> Optional[float]:
    weighted_sum = 0.0
    weight_total = 0.0
    for c in active_contracts:
        if c.ai_scoring is None:
            continue
        value = getter(c)
        if value is None:
            continue
        weight = c.principal_ots + c.interest_ots
        weighted_sum += value * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return weighted_sum / weight_total


def _customer_profile_block(behavioral: Optional[CustomerBehavioralRaw]) -> dict:
    if behavioral is None or not behavioral.has_cbs_row:
        return {}
    block = {
        "behavioral_grade": behavioral.behavioral_grade,
        "b_list_status": behavioral.b_list_status,
        "active_contract_count": behavioral.active_contract_count,
        "total_active_ots": behavioral.total_active_ots,
        "cbs_as_of": behavioral.cbs_as_of.isoformat() if behavioral.cbs_as_of else None,
    }
    # ptp_reliability_index/collection_sensitivity boleh NULL walau baris CBS
    # ADA (belum pernah PTP / belum ada channel dominan) — hilangkan key,
    # jangan kirim None sebagai nilai (temuan #9: "tidak diketahui" harus
    # hilang dari payload, bukan terlihat seperti fakta).
    if behavioral.ptp_reliability_index is not None:
        block["ptp_reliability_index"] = behavioral.ptp_reliability_index
    if behavioral.collection_sensitivity is not None:
        block["collection_sensitivity"] = behavioral.collection_sensitivity
    return block


def _portfolio_rollup_block(active_contracts: List[ContractDetail]) -> dict:
    scored = [c for c in active_contracts if c.ai_scoring is not None]

    worst_dpd = max((c.dpd_current for c in active_contracts), default=0)
    # Urutan keparahan cycle: C0 < C1 < C2 < C3+ (string biasa tidak terurut
    # begini secara leksikografis, jadi map manual).
    cycle_rank = {"C0": 0, "C1": 1, "C2": 2, "C3+": 3}
    worst_cycle = max(
        (c.cycle for c in active_contracts if c.cycle in cycle_rank),
        key=lambda v: cycle_rank[v],
        default=None,
    )
    risk_rank = {"Can Pay": 0, "Self-cure": 1, "Cannot Pay": 2, "Won't Pay": 3}
    worst_risk_segment = max(
        (c.ai_scoring.risk_segment for c in scored if c.ai_scoring.risk_segment in risk_rank),
        key=lambda v: risk_rank[v],
        default=None,
    )

    total_ots = sum(c.principal_ots + c.interest_ots for c in active_contracts)
    arrears_ots = sum(
        c.principal_ots + c.interest_ots for c in active_contracts if c.dpd_current > 0
    )

    nba_spread = sorted({c.ai_scoring.nba_recommendation for c in scored if c.ai_scoring.nba_recommendation})

    rollup = {
        "worst_dpd": worst_dpd,
        "contracts_in_arrears": sum(1 for c in active_contracts if c.dpd_current > 0),
        "arrears_ots_share": round(arrears_ots / total_ots, 4) if total_ots > 0 else 0.0,
        "nba_spread": nba_spread,
    }
    if worst_risk_segment is not None:
        rollup["worst_risk_segment"] = worst_risk_segment
    if worst_cycle is not None:
        rollup["worst_cycle"] = worst_cycle

    ots_weighted_recovery = _ots_weighted_average(active_contracts, lambda c: c.ai_scoring.recovery_score)
    if ots_weighted_recovery is not None:
        rollup["ots_weighted_recovery_score"] = round(ots_weighted_recovery, 4)

    # roll_forward_risk tersimpan TERBALIK (P(tidak bayar), bukan P(bayar) —
    # temuan #8 dokumen) — nama field di payload WAJIB self-describing.
    max_rf_risk = max(
        (c.ai_scoring.roll_forward_risk for c in scored if c.ai_scoring.roll_forward_risk is not None),
        default=None,
    )
    if max_rf_risk is not None:
        rollup["max_roll_forward_risk_prob_not_paying"] = max_rf_risk

    return rollup


def _contract_block(c: ContractDetail) -> dict:
    block = {
        "contract_no": c.contract_no,
        "product_type": c.product_type,
        "dpd_current": c.dpd_current,
        "cycle": c.cycle,
        "overdue_installment_count": c.overdue_installment_count,
        "installment_amount": c.installment_amount,
        "total_ots": round(c.principal_ots + c.interest_ots, 2),
        "late_fee_amount": c.late_fee_amount,
        "recent_payments": [
            {
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "actual_pay_date": p.actual_pay_date.isoformat() if p.actual_pay_date else None,
                "pay_status": p.pay_status,
                "delay_days": p.delay_days,
            }
            for p in c.payment_history
        ],
    }
    if c.ai_scoring is not None:
        block["risk_segment"] = c.ai_scoring.risk_segment
        block["recovery_score"] = c.ai_scoring.recovery_score
        if c.ai_scoring.nba_recommendation:
            block["nba_recommendation"] = c.ai_scoring.nba_recommendation
        if c.ai_scoring.nba_trigger:
            block["nba_trigger"] = c.ai_scoring.nba_trigger
    # historical_default_count/income_debt_ratio SENGAJA tidak dikirim meski
    # sekarang terisi benar (Fase 0 perbaikan temuan #17) — itu fitur model,
    # bukan fakta yang perlu dijelaskan ke LLM (concern berbeda, lihat §1.1).
    return block


def build_payload(
    cust_id: str,
    behavioral: Optional[CustomerBehavioralRaw],
    active_contracts: List[ContractDetail],
    as_of: Optional[date] = None,
) -> dict:
    return {
        "cust_id": cust_id,
        "as_of": (as_of or date.today()).isoformat(),
        "available_models": available_models(),
        "customer_profile": _customer_profile_block(behavioral),
        "portfolio_rollup": _portfolio_rollup_block(active_contracts),
        "contracts": [_contract_block(c) for c in active_contracts],
    }

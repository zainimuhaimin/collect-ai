"""Restructuring Recommendation Runner — Step 7.5 daily batch (TASK-52).

Dipanggil dari pipelines/daily_scoring.py SETELAH business rules (segment/
NBA/priority) dan SEBELUM quality check, memakai df_scored yang sudah ada
di memori (recovery_score/self_cure_probability/risk_segment) — TIDAK query
ai_intelligence_output dari DB, karena publish hari ini belum terjadi saat
titik ini dieksekusi.

Bisa juga dijalankan berdiri sendiri (`python pipelines/restructuring_runner.py`)
untuk re-generate rekomendasi tanpa scoring ulang — dalam mode ini,
skor diambil dari ai_intelligence_output yang sudah ter-publish untuk
reference_date tsb.

Batch tetap MENYIMPAN hasil untuk tier AUTO maupun MANUAL_REVIEW (dipakai
sebagai cache oleh endpoint on-demand backend) — hanya tier AUTO yang
memicu notifikasi ke collector.
"""
from __future__ import annotations

import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import (  # noqa: E402
    DB_URL,
    RESTRUCTURE_OFFER_EXPIRY_DAYS,
    MIN_DPD_FOR_RESTRUCTURE,
    CONSOLIDATION_PROBLEM_CONTRACTS_ONLY,
)
from src.restructuring_offer_calculator import (  # noqa: E402
    AssetAppraisal,
    ContractInput,
    CustomerContext,
    EligibilityTier,
    assess_restructuring_options,
    effective_remaining_tenor,
    restructuring_policy_from_settings,
)

SCORE_COLS = ["contract_no", "recovery_score", "self_cure_probability", "risk_segment"]


def _remaining_tenor_months(maturity_date, reference_date) -> int:
    if maturity_date is None or (isinstance(maturity_date, float) and pd.isna(maturity_date)):
        return 0
    maturity = pd.Timestamp(maturity_date)
    if pd.isna(maturity):
        return 0
    days = (maturity - pd.Timestamp(reference_date)).days
    return max(0, round(days / 30))


def _load_contracts(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM contract_snapshot", engine)
    df.columns = [c.lower() for c in df.columns]
    return df


def _load_cbs(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM customer_behavioral_standing", engine)
    df.columns = [c.lower() for c in df.columns]
    return df


def _load_appraisal(engine) -> pd.DataFrame:
    try:
        df = pd.read_sql("SELECT * FROM asset_appraisal", engine)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def _load_scores_from_db(engine, ref_date) -> pd.DataFrame:
    try:
        df = pd.read_sql(
            text(
                "SELECT contract_no, recovery_score, self_cure_probability, risk_segment "
                "FROM ai_intelligence_output WHERE scoring_date = :d"
            ),
            engine,
            params={"d": ref_date},
        )
    except Exception:
        return pd.DataFrame(columns=SCORE_COLS)
    df.columns = [c.lower() for c in df.columns]
    return df


def _to_contract_input(row, reference_date) -> ContractInput:
    principal_ots = float(row.get("prnc_ots") or 0)
    # total_ots = kewajiban BRUTO (pokok + bunga belum jatuh tempo). Keduanya
    # diteruskan terpisah: yang diamortisasi ulang HANYA pokok, sedangkan yang
    # bruto dipakai untuk sisa jumlah cicilan & cakupan aset — lihat koreksi #1
    # di docstring shared/restructuring_offer_calculator.py.
    total_ots = principal_ots + float(row.get("intr_ots") or 0)
    interest_rate = row.get("interest_rate")
    return ContractInput(
        contract_no=row["contract_no"],
        cust_id=row["cust_id"],
        product_type=row.get("product_type") or "Unknown",
        total_ots=total_ots,
        principal_ots=principal_ots,
        interest_rate=float(interest_rate) if pd.notna(interest_rate) else 0.0,
        remaining_tenor_months=_remaining_tenor_months(row.get("maturity_date"), reference_date),
        installment_amount=float(row.get("installment_amount") or 0.0),
        dpd_current=int(row.get("dpd_current") or 0),
        risk_segment=row.get("risk_segment") or "Cannot Pay",
        recovery_score=float(row["recovery_score"]) if pd.notna(row.get("recovery_score")) else 0.0,
        self_cure_probability=(
            float(row["self_cure_probability"]) if pd.notna(row.get("self_cure_probability")) else 0.0
        ),
        closed_via_restructure=bool(row.get("closed_via_restructure") or False),
    )


def _to_customer_context(cust_id, cbs_row) -> CustomerContext:
    if cbs_row is None:
        return CustomerContext(cust_id=cust_id, b_list_status="N", restructure_count=0, active_contract_count=1)
    return CustomerContext(
        cust_id=cust_id,
        b_list_status=cbs_row.get("b_list_status") or "N",
        restructure_count=int(cbs_row.get("restructure_count") or 0),
        active_contract_count=int(cbs_row.get("active_contract_count") or 1),
    )


def _notify_collector(group_id: str, cust_id: str, offer_type: str):
    """Placeholder notifikasi — ganti dengan integrasi channel collector
    nyata (WA/email/task queue). Hanya dipanggil untuk tier AUTO."""
    print(f"  [Notify] -> collector: {cust_id} punya tawaran {offer_type} baru ({group_id})")


def _qc_check_offer(offer, contract_input: ContractInput, policy) -> list[str]:
    """TASK-54 — safety net. apply_guardrail() dan calculate_*_offer() SUDAH
    menjamin ini semua secara matematis; cek ini murni jaring pengaman kalau
    ada perubahan kode di masa depan yang tidak sengaja melewatinya."""
    violations: list[str] = []

    # Sisi lender — basis yang SAMA dengan apply_guardrail() (dua-duanya
    # risk-adjusted). Dulu di sini memakai npv_restructured mentah, ikut
    # mewarisi perbandingan tidak sebanding yang membuat 100% offer lolos.
    if offer.npv_restructured_risk_adjusted <= offer.npv_baseline:
        violations.append(
            f"{offer.offer_type.value} {contract_input.contract_no}: "
            "NPV risk-adjusted tidak lebih baik dari baseline (lolos guardrail?)"
        )

    # Sisi nasabah — safety net kalau guardrail dilewati perubahan kode nanti.
    is_full_payoff = offer.recommended_new_tenor_months <= 0 and offer.recommended_new_installment <= 0
    if not is_full_payoff and offer.current_installment_total > 0:
        max_new_installment = offer.current_installment_total * (1 - policy.min_installment_reduction_pct)
        if offer.recommended_new_installment > max_new_installment + 0.01:
            violations.append(
                f"{offer.offer_type.value} {contract_input.contract_no}: cicilan baru "
                f"{offer.recommended_new_installment:,.0f} tidak lebih ringan dari cicilan sekarang "
                f"{offer.current_installment_total:,.0f} (lolos guardrail?)"
            )

    if offer.offer_type.value in ("REFINANCE", "TAKEOVER") and offer.recommended_new_rate > 0:
        # Formula sama dengan calculate_refinance_offer/calculate_takeover_offer —
        # QC ini murni memverifikasi hasilnya konsisten dengan formula tsb.
        min_allowed_rate = max(
            contract_input.interest_rate * (1 - policy.max_haircut_pct),
            policy.min_rate_floor,
        )
        # Toleransi 5e-5: recommended_new_rate sudah dibulatkan ke 4 desimal
        # oleh calculate_refinance_offer/calculate_takeover_offer, sedangkan
        # min_allowed_rate di sini dihitung tanpa pembulatan — beri toleransi
        # setengah unit pembulatan supaya tidak false-positive.
        if offer.recommended_new_rate < min_allowed_rate - 5e-5:
            violations.append(
                f"{offer.offer_type.value} {contract_input.contract_no}: recommended_new_rate "
                f"{offer.recommended_new_rate} di bawah floor kebijakan {min_allowed_rate:.4f}"
            )

    if offer.offer_type.value == "REFINANCE":
        # Basis tenor-nya effective_remaining_tenor(), sama dengan yang dipakai
        # calculate_refinance_offer() — BUKAN remaining_tenor_months dari
        # maturity_date, yang mengabaikan tunggakan (lihat koreksi #2).
        base_tenor = effective_remaining_tenor(contract_input)
        max_ext = min(
            policy.max_tenor_extension_months,
            int(base_tenor * policy.max_tenor_extension_ratio),
        )
        max_allowed_tenor = base_tenor + max_ext
        if offer.recommended_new_tenor_months > max_allowed_tenor + 1:
            violations.append(
                f"REFINANCE {contract_input.contract_no}: tenor {offer.recommended_new_tenor_months} "
                f"melebihi cap kebijakan {max_allowed_tenor}"
            )

    return violations


def _check_product_conversion_mapping(engine, output_rows: list[dict]) -> list[str]:
    """(c) TASK-54 — TAKEOVER tidak boleh berstatus OFFERED ke production
    selama product_conversion_mapping masih placeholder kosong (tim produk
    belum konfirmasi — lihat restructuring-engine-tasks.md Catatan #2)."""
    takeover_offered = any(r["offer_type"] == "TAKEOVER" and r["offer_status"] == "OFFERED" for r in output_rows)
    if not takeover_offered:
        return []
    try:
        n = pd.read_sql("SELECT COUNT(*) AS n FROM product_conversion_mapping", engine)["n"].iloc[0]
    except Exception:
        n = 0
    if n == 0:
        return [
            "Ada TAKEOVER offer berstatus OFFERED tapi product_conversion_mapping masih "
            "kosong (placeholder) — tim produk belum konfirmasi mapping asli"
        ]
    return []


def run_restructuring_assessment(reference_date=None, engine=None, df_scored: pd.DataFrame | None = None) -> dict:
    ref_date = pd.Timestamp(reference_date).date() if reference_date else pd.Timestamp.today().date()
    engine = engine or create_engine(DB_URL)

    contracts = _load_contracts(engine)
    if contracts.empty:
        print("[Restructuring] contract_snapshot kosong — dilewati")
        return {"processed": 0, "errors": 0, "auto": 0, "manual_review": 0, "blocked": 0}

    if df_scored is not None and not df_scored.empty:
        scores = df_scored.copy()
        scores.columns = [c.lower() for c in scores.columns]
        scores = scores[[c for c in SCORE_COLS if c in scores.columns]]
    else:
        scores = _load_scores_from_db(engine, ref_date)

    merged = contracts.merge(scores, on="contract_no", how="left", suffixes=("", "_score"))

    cbs = _load_cbs(engine)
    cbs_by_cust = {r["cust_id"]: r for _, r in cbs.iterrows()} if not cbs.empty else {}

    appraisal = _load_appraisal(engine)
    appraisal_latest = (
        appraisal.sort_values("appraisal_date").groupby("contract_no").last()
        if not appraisal.empty else pd.DataFrame()
    )

    policy = restructuring_policy_from_settings()

    n_processed = n_errors = n_auto = n_manual = n_blocked = 0
    qc_violations: list[str] = []
    group_map_rows: list[dict] = []
    output_rows: list[dict] = []
    seq_counter: dict[str, int] = {}

    # TASK-P2/P5: dulu tiap iterasi loop di bawah memfilter ULANG seluruh
    # `merged` (`merged[merged["cust_id"] == row["cust_id"]] ...`) untuk
    # mencari sibling kontrak — itu O(n) per baris x n baris = O(n²). Pada
    # 50 rb kontrak, profiling cProfile (perf/profile_scoring.py, TASK-P2)
    # menunjukkan ini 61% dari total waktu daily_scoring, dan pada 100 rb
    # kontrak inilah yang membuat ladder TASK-P4 melewati stop rule waktu.
    # `groupby` SEKALI di sini menghasilkan hasil yang PERSIS SAMA (partisi
    # baris yang identik dengan boolean-mask lama, hanya dihitung sekali,
    # bukan n kali) — lookup per baris jadi O(group size), total O(n).
    siblings_by_cust = {cust_id: grp for cust_id, grp in merged.groupby("cust_id")}

    print(f"\n[Restructuring] Menilai {len(merged):,} kontrak untuk {ref_date}...")

    for _, row in merged.iterrows():
        try:
            if pd.isna(row.get("recovery_score")):
                # Belum discoring hari ini (mis. kontrak baru/lunas) — bukan
                # error, cuma belum ada input untuk dinilai.
                continue

            contract_input = _to_contract_input(row, ref_date)
            customer = _to_customer_context(row["cust_id"], cbs_by_cust.get(row["cust_id"]))

            # Dari `merged`, BUKAN `contracts`: `contracts` adalah
            # contract_snapshot mentah tanpa kolom recovery_score, sehingga
            # setiap sibling masuk ke kalkulator dengan recovery_score=0.0.
            # Akibatnya kontribusi sibling ke npv_baseline CONSOLIDATE jadi nol
            # (baseline hanya sebesar kontrak utama — mis. CUST-00001 tercatat
            # 1.126.647 padahal seharusnya 2.154.649), jadi guardrail menilai
            # tawaran konsolidasi terhadap pembanding yang terlalu rendah dan
            # meloloskannya terlalu mudah.
            cust_group = siblings_by_cust.get(row["cust_id"])
            sibling_rows = (
                cust_group[cust_group["contract_no"] != row["contract_no"]]
                if cust_group is not None
                else merged.iloc[0:0]
            )
            sibling_rows = sibling_rows[sibling_rows["recovery_score"].notna()]
            if CONSOLIDATION_PROBLEM_CONTRACTS_ONLY:
                sibling_rows = sibling_rows[
                    pd.to_numeric(sibling_rows["dpd_current"], errors="coerce").fillna(0) >= MIN_DPD_FOR_RESTRUCTURE
                ]
            siblings = [_to_contract_input(r, ref_date) for _, r in sibling_rows.iterrows()] or None

            appraisal_obj = None
            if not appraisal_latest.empty and row["contract_no"] in appraisal_latest.index:
                arow = appraisal_latest.loc[row["contract_no"]]
                appraisal_obj = AssetAppraisal(
                    contract_no=row["contract_no"],
                    appraised_value=float(arow["appraised_value"]),
                    appraisal_date=pd.Timestamp(arow["appraisal_date"]).date(),
                )

            assessment = assess_restructuring_options(
                contract=contract_input,
                customer=customer,
                policy=policy,
                sibling_contracts=siblings,
                appraisal=appraisal_obj,
                today=ref_date,
            )

            n_processed += 1
            if assessment.eligibility_tier == EligibilityTier.AUTO:
                n_auto += 1
            elif assessment.eligibility_tier == EligibilityTier.MANUAL_REVIEW:
                n_manual += 1
            else:
                n_blocked += 1

            for offer in assessment.offers:
                qc_violations.extend(_qc_check_offer(offer, contract_input, policy))

                prefix = f"RG-{row['cust_id']}-{ref_date}"
                seq_counter[prefix] = seq_counter.get(prefix, 0) + 1
                group_id = f"{prefix}-{seq_counter[prefix]}"

                for c_no in offer.contract_nos:
                    group_map_rows.append({
                        "restructure_group_id": group_id,
                        "contract_no": c_no,
                        "cust_id": row["cust_id"],
                        "inclusion_reason": offer.offer_type.value,
                    })

                output_rows.append({
                    "restructure_group_id": group_id,
                    "cust_id": row["cust_id"],
                    "offer_type": offer.offer_type.value,
                    "contract_count_included": len(offer.contract_nos),
                    "total_ots_combined": offer.total_ots_combined,
                    "recommended_new_tenor": offer.recommended_new_tenor_months,
                    "recommended_new_rate": offer.recommended_new_rate,
                    "recommended_new_installment": offer.recommended_new_installment,
                    "recovery_from_asset": offer.recovery_from_asset,
                    "npv_baseline": offer.npv_baseline,
                    "npv_restructured": offer.npv_restructured,
                    "offer_status": "OFFERED" if assessment.eligibility_tier == EligibilityTier.AUTO else "GENERATED",
                    "generated_date": ref_date,
                    "expiry_date": ref_date + pd.Timedelta(days=RESTRUCTURE_OFFER_EXPIRY_DAYS),
                    "eligibility_tier": assessment.eligibility_tier.value,
                    "eligibility_reasons": "; ".join(assessment.eligibility_reasons),
                    "source": "BATCH",
                    "requested_by": None,
                })

                if assessment.eligibility_tier == EligibilityTier.AUTO:
                    _notify_collector(group_id, row["cust_id"], offer.offer_type.value)

        except Exception as exc:
            n_errors += 1
            print(f"[Restructuring] Gagal memproses {row.get('contract_no')}: {exc}")
            continue

    # ── QC (TASK-54) — safety net sebelum publish ke DB ────────────
    qc_violations.extend(_check_product_conversion_mapping(engine, output_rows))
    print("\n[Restructuring QC] Summary")
    if qc_violations:
        for v in qc_violations:
            print(f"  - FAIL: {v}")
        raise ValueError(
            f"Restructuring QC gagal: {len(qc_violations)} pelanggaran ditemukan (lihat log di atas)"
        )
    print(f"  - PASS: {len(output_rows)} offer lolos semua QC check")

    with engine.begin() as conn:
        # Idempotent: hapus batch output hari ini dulu sebelum insert ulang
        # (aman dijalankan berkali-kali untuk reference_date yang sama).
        existing = pd.read_sql(
            text(
                "SELECT restructure_group_id FROM restructuring_recommendation_output "
                "WHERE generated_date = :d AND source = 'BATCH'"
            ),
            conn,
            params={"d": ref_date},
        )
        old_ids = existing["restructure_group_id"].tolist() if not existing.empty else []
        if old_ids:
            conn.execute(
                text("DELETE FROM restructuring_group_map WHERE restructure_group_id = ANY(:ids)"),
                {"ids": old_ids},
            )
            conn.execute(
                text("DELETE FROM restructuring_recommendation_output WHERE restructure_group_id = ANY(:ids)"),
                {"ids": old_ids},
            )

        if output_rows:
            pd.DataFrame(output_rows).to_sql(
                "restructuring_recommendation_output", conn, if_exists="append", index=False
            )
        if group_map_rows:
            pd.DataFrame(group_map_rows).to_sql(
                "restructuring_group_map", conn, if_exists="append", index=False
            )

    summary = {
        "processed": n_processed,
        "errors": n_errors,
        "auto": n_auto,
        "manual_review": n_manual,
        "blocked": n_blocked,
        "offers_generated": len(output_rows),
    }
    print(
        f"[Restructuring] Selesai: {n_processed:,} diproses, {n_errors} error | "
        f"AUTO={n_auto} MANUAL_REVIEW={n_manual} BLOCKED={n_blocked} | "
        f"{len(output_rows)} offer tersimpan"
    )
    return summary


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_restructuring_assessment(sys.argv[1])
    else:
        run_restructuring_assessment()

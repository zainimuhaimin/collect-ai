"""Core Banking — Contract Origination Simulator.

Ini merepresentasikan sistem TERPISAH dari collect-ai (ML + backend) yang
dalam dunia nyata benar-benar mencairkan kontrak baru (approval kredit,
tanda tangan, dsb) untuk multifinance/leasing. collect-ai (backend) HANYA
mencatat keputusan customer (offer_status='ACCEPTED') — modul inilah yang
"mengeksekusi" keputusan itu menjadi kontrak baru di contract_snapshot,
persis seperti sync harian dari core banking sungguhan.

Kenapa terpisah dari app/backend/ dan app/machine-learning/:
- Origination kredit (approval, pencairan, tanda tangan) adalah proses
  bisnis yang BEDA lapisan dari scoring/collection (ML) maupun presentasi
  data ke CS (backend) — punya siklus hidup, SLA, dan tim pemilik sendiri
  di dunia nyata.
- Memisahkannya juga menghindari godaan biar backend/ML "iseng" membuat
  kontrak baru sendiri — satu-satunya jalan kontrak baru muncul adalah
  lewat modul (atau sistem nyata yang disimulasikannya) ini.

Jalankan:
    cd app/core-banking
    python originator.py
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core.config import DB_URL  # noqa: E402


def _load_pending_accepted_offers(engine) -> pd.DataFrame:
    """Offer ACCEPTED yang kontrak lamanya BELUM closed_via_restructure —
    itu tandanya belum pernah dieksekusi (idempotency check, tanpa perlu
    kolom status eksekusi terpisah)."""
    query = text(
        """
        SELECT DISTINCT ro.restructure_group_id, ro.cust_id, ro.offer_type,
               ro.recommended_new_tenor, ro.recommended_new_rate,
               ro.recommended_new_installment, ro.total_ots_combined
        FROM restructuring_recommendation_output ro
        JOIN restructuring_group_map gm ON gm.restructure_group_id = ro.restructure_group_id
        JOIN contract_snapshot cs ON cs.contract_no = gm.contract_no
        WHERE ro.offer_status = 'ACCEPTED'
          AND COALESCE(cs.closed_via_restructure, FALSE) = FALSE
        """
    )
    df = pd.read_sql(query, engine)
    df.columns = [c.lower() for c in df.columns]
    return df


def _member_contracts(engine, group_id: str) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            "SELECT cs.* FROM contract_snapshot cs "
            "JOIN restructuring_group_map gm ON gm.contract_no = cs.contract_no "
            "WHERE gm.restructure_group_id = :g"
        ),
        engine,
        params={"g": group_id},
    )
    df.columns = [c.lower() for c in df.columns]
    return df


def _new_contract_no(group_id: str) -> str:
    """contract_no kolom di contract_snapshot cuma VARCHAR(30) — group_id
    (mis. 'RG-CUST-00029-2026-07-21-1') sering lebih panjang dari itu, jadi
    dipadatkan jadi hash pendek yang deterministik (bukan random) supaya
    tetap konsisten/dapat-ditelusuri kalau originate_contract() perlu
    dipanggil ulang untuk group_id yang sama."""
    short = hashlib.md5(group_id.encode()).hexdigest()[:10].upper()
    return f"CTR-R-{short}"


def originate_contract(engine, offer_row, member_contracts: pd.DataFrame, today: date) -> str:
    """Buat 1 kontrak baru dari 1 offer ACCEPTED, tutup semua kontrak lama
    yang jadi anggotanya. Return contract_no kontrak baru."""
    new_contract_no = _new_contract_no(offer_row["restructure_group_id"])

    total_ots = float(offer_row["total_ots_combined"] or 0)
    # Split principal/interest mengikuti konvensi yang sama dipakai faker
    # (intr_ots ~= 10% dari prnc_ots) — origination sungguhan tentu punya
    # perhitungan sendiri, ini simulasi yang konsisten dengan data generator.
    prnc_ots = round(total_ots / 1.10, 2)
    intr_ots = round(total_ots - prnc_ots, 2)

    new_tenor = int(offer_row["recommended_new_tenor"] or 0)
    new_rate = float(offer_row["recommended_new_rate"] or 0)
    new_installment = float(offer_row["recommended_new_installment"] or 0)
    product_type = member_contracts.iloc[0]["product_type"] if not member_contracts.empty else "Unknown"
    maturity_date = today + timedelta(days=max(1, new_tenor) * 30)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO contract_snapshot (
                    contract_no, cust_id, dpd_current, prnc_ots, intr_ots, cycle,
                    product_type, interest_rate, installment_amount, maturity_date,
                    overdue_installment_count, late_fee_amount,
                    closed_via_restructure, new_contract_no
                ) VALUES (
                    :contract_no, :cust_id, 0, :prnc_ots, :intr_ots, 'C0',
                    :product_type, :interest_rate, :installment_amount, :maturity_date,
                    0, 0, FALSE, NULL
                )
                ON CONFLICT (contract_no) DO NOTHING
                """
            ),
            {
                "contract_no": new_contract_no,
                "cust_id": offer_row["cust_id"],
                "prnc_ots": prnc_ots,
                "intr_ots": intr_ots,
                "product_type": product_type,
                "interest_rate": new_rate,
                "installment_amount": new_installment,
                "maturity_date": maturity_date,
            },
        )

        for old_contract_no in member_contracts["contract_no"].tolist():
            conn.execute(
                text(
                    "UPDATE contract_snapshot "
                    "SET closed_via_restructure = TRUE, new_contract_no = :new_no "
                    "WHERE contract_no = :old_no"
                ),
                {"new_no": new_contract_no, "old_no": old_contract_no},
            )

    return new_contract_no


def run_contract_origination(reference_date=None, engine=None) -> dict:
    today = pd.Timestamp(reference_date).date() if reference_date else date.today()
    engine = engine or create_engine(DB_URL)

    pending = _load_pending_accepted_offers(engine)
    if pending.empty:
        print("[Core Banking] Tidak ada offer ACCEPTED yang menunggu eksekusi")
        return {"executed": 0, "errors": 0}

    print(f"\n[Core Banking] Mengeksekusi {len(pending):,} tawaran ACCEPTED...")
    n_executed = 0
    n_errors = 0

    for _, offer_row in pending.iterrows():
        group_id = offer_row["restructure_group_id"]
        try:
            members = _member_contracts(engine, group_id)
            if members.empty:
                print(f"[Core Banking] {group_id}: tidak ada kontrak anggota di restructuring_group_map, dilewati")
                continue

            new_contract_no = originate_contract(engine, offer_row, members, today)
            n_executed += 1
            print(
                f"  [Executed] {group_id} -> kontrak baru {new_contract_no} "
                f"(menutup {len(members)} kontrak lama: {members['contract_no'].tolist()})"
            )
        except Exception as exc:
            n_errors += 1
            print(f"[Core Banking] Gagal eksekusi {group_id}: {exc}")
            continue

    print(f"[Core Banking] Selesai: {n_executed:,} kontrak baru dieksekusi, {n_errors} error")
    return {"executed": n_executed, "errors": n_errors}


if __name__ == "__main__":
    run_contract_origination()

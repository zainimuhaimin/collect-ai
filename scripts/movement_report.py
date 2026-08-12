#!/usr/bin/env python3
"""TASK-S4 — Laporan pergerakan skor lintas hari.

Baca `scoring_history` (arsip yang ditulis TASK-S2 di setiap hari simulasi
— BUKAN tabel live, karena tabel live hanya menyimpan keadaan hari
terakhir), hasilkan CSV + Markdown: delta per kontrak, matriks transisi
risk_segment D0->Dn, agregat naik/turun/tetap, dan daftar top-mover.

Pakai (setelah `scripts/simulate_days.py` selesai):
    python scripts/movement_report.py --out reports/movement_2026-08.md

Kalau matriks transisi 100% diagonal, simulasi TIDAK benar-benar memajukan
apa pun — itu kegagalan yang harus ditelusuri (lihat TASK-S2), bukan hasil
yang dilaporkan begitu saja.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(ROOT, "app", "machine-learning")
sys.path.insert(0, ML_DIR)

from config.settings import DB_URL  # noqa: E402

RISK_SEGMENTS = ["Can Pay", "Cannot Pay", "Won't Pay"]


def _load_history(engine) -> pd.DataFrame:
    return pd.read_sql(text("SELECT * FROM scoring_history ORDER BY contract_no, snapshot_date"), engine)


def _first_last(df: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(df["snapshot_date"].unique())
    if len(dates) < 2:
        raise SystemExit(
            f"scoring_history hanya punya {len(dates)} snapshot_date — butuh minimal 2 "
            f"(jalankan scripts/simulate_days.py --dates D0,D1,... dulu)."
        )
    d0, dn = dates[0], dates[-1]
    first = df[df["snapshot_date"] == d0].set_index("contract_no")
    last = df[df["snapshot_date"] == dn].set_index("contract_no")
    common = first.index.intersection(last.index)
    first, last = first.loc[common], last.loc[common]

    out = pd.DataFrame({
        "contract_no": common,
        "cust_id": first["cust_id"].values,
        "snapshot_date_d0": d0,
        "snapshot_date_dn": dn,
        "risk_segment_d0": first["risk_segment"].values,
        "risk_segment_dn": last["risk_segment"].values,
        "recovery_score_d0": first["recovery_score"].values,
        "recovery_score_dn": last["recovery_score"].values,
        "dpd_current_d0": first["dpd_current"].values,
        "dpd_current_dn": last["dpd_current"].values,
        "nba_recommendation_d0": first["nba_recommendation"].values,
        "nba_recommendation_dn": last["nba_recommendation"].values,
        "priority_level_d0": first["priority_level"].values,
        "priority_level_dn": last["priority_level"].values,
        "total_ots_d0": first["total_ots"].values,
        "total_ots_dn": last["total_ots"].values,
    })
    out["recovery_score_delta"] = out["recovery_score_dn"] - out["recovery_score_d0"]
    out["dpd_delta"] = out["dpd_current_dn"] - out["dpd_current_d0"]
    out["segment_changed"] = out["risk_segment_d0"] != out["risk_segment_dn"]
    out["nba_changed"] = out["nba_recommendation_d0"] != out["nba_recommendation_dn"]
    return out, d0, dn


def _transition_matrix(delta: pd.DataFrame) -> pd.DataFrame:
    segs = sorted(set(delta["risk_segment_d0"]) | set(delta["risk_segment_dn"]))
    mat = pd.crosstab(delta["risk_segment_d0"], delta["risk_segment_dn"])
    mat = mat.reindex(index=segs, columns=segs, fill_value=0)
    return mat


def _top_movers(delta: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    ranked = delta.copy()
    ranked["_abs_score_delta"] = ranked["recovery_score_delta"].abs()
    ranked = ranked.sort_values("_abs_score_delta", ascending=False)
    cols = [
        "contract_no", "cust_id", "risk_segment_d0", "risk_segment_dn",
        "recovery_score_d0", "recovery_score_dn", "recovery_score_delta",
        "dpd_current_d0", "dpd_current_dn", "nba_recommendation_d0", "nba_recommendation_dn",
    ]
    return ranked[cols].head(n)


def _render_markdown(delta, matrix, movers, d0, dn) -> str:
    n = len(delta)
    up = int((delta["recovery_score_delta"] > 0).sum())
    down = int((delta["recovery_score_delta"] < 0).sum())
    flat = n - up - down
    seg_changed = int(delta["segment_changed"].sum())
    nba_changed = int(delta["nba_changed"].sum())
    is_diagonal = bool((matrix.values.sum() - pd.Series(matrix.values.diagonal()).sum()) == 0)

    lines = []
    lines.append(f"# Laporan pergerakan — {d0} -> {dn}")
    lines.append("")
    lines.append(f"Kontrak dibandingkan: **{n:,}** (hanya kontrak yang punya baris di kedua tanggal).")
    lines.append("")
    lines.append("## Ringkasan agregat")
    lines.append("")
    lines.append(f"- recovery_score naik: **{up:,}** ({100*up/n:.1f}%)")
    lines.append(f"- recovery_score turun: **{down:,}** ({100*down/n:.1f}%)")
    lines.append(f"- recovery_score tetap: **{flat:,}** ({100*flat/n:.1f}%)")
    lines.append(f"- risk_segment berubah: **{seg_changed:,}** ({100*seg_changed/n:.1f}%)")
    lines.append(f"- nba_recommendation berubah: **{nba_changed:,}** ({100*nba_changed/n:.1f}%)")
    lines.append("")
    lines.append("## Distribusi risk_segment")
    lines.append("")
    d0_dist = delta["risk_segment_d0"].value_counts().to_dict()
    dn_dist = delta["risk_segment_dn"].value_counts().to_dict()
    lines.append(f"- {d0}: {d0_dist}")
    lines.append(f"- {dn}: {dn_dist}")
    lines.append("")
    lines.append("## Distribusi priority_level")
    lines.append("")
    lines.append(f"- {d0}: {delta['priority_level_d0'].value_counts().to_dict()}")
    lines.append(f"- {dn}: {delta['priority_level_dn'].value_counts().to_dict()}")
    lines.append("")
    lines.append(f"## Matriks transisi risk_segment ({d0} -> {dn})")
    lines.append("")
    if is_diagonal:
        lines.append(
            "**⚠️ PERINGATAN: matriks 100% diagonal — TIDAK ADA pergerakan segmen "
            "sama sekali.** Ini kegagalan yang harus ditelusuri (lihat TASK-S2 "
            "`recompute_contract_state()`/`update_cbs()`), BUKAN dipresentasikan "
            "sebagai hasil."
        )
        lines.append("")
    header = "| dari \\ ke | " + " | ".join(matrix.columns) + " |"
    sep = "|---|" + "---|" * len(matrix.columns)
    lines.append(header)
    lines.append(sep)
    for idx in matrix.index:
        row = " | ".join(str(v) for v in matrix.loc[idx])
        lines.append(f"| **{idx}** | {row} |")
    lines.append("")
    lines.append(f"## Top {len(movers)} mover (perubahan recovery_score terbesar)")
    lines.append("")
    lines.append(
        "| contract_no | cust_id | segment (d0->dn) | score (d0->dn) | delta | dpd (d0->dn) | nba (d0->dn) |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in movers.iterrows():
        lines.append(
            f"| {r['contract_no']} | {r['cust_id']} | {r['risk_segment_d0']} -> {r['risk_segment_dn']} "
            f"| {r['recovery_score_d0']:.4f} -> {r['recovery_score_dn']:.4f} "
            f"| {r['recovery_score_delta']:+.4f} | {r['dpd_current_d0']} -> {r['dpd_current_dn']} "
            f"| {r['nba_recommendation_d0']} -> {r['nba_recommendation_dn']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(ROOT, "reports", "movement_report.md"))
    parser.add_argument("--csv-out", default=None, help="Default: sama seperti --out tapi berekstensi .csv")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    engine = create_engine(DB_URL)
    history = _load_history(engine)
    delta, d0, dn = _first_last(history)
    matrix = _transition_matrix(delta)
    movers = _top_movers(delta, n=args.top_n)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    csv_out = args.csv_out or (os.path.splitext(args.out)[0] + ".csv")
    delta.to_csv(csv_out, index=False)

    md = _render_markdown(delta, matrix, movers, d0, dn)
    with open(args.out, "w") as f:
        f.write(md)

    print(md)
    print(f"\n✓ Markdown: {args.out}")
    print(f"✓ CSV: {csv_out}")


if __name__ == "__main__":
    main()

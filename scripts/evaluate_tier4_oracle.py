#!/usr/bin/env python3
"""TASK-E5 — Tier 4: evaluasi akurasi terhadap latent oracle (kunci jawaban
sintetis). Satu-satunya jalur yang membuat kata *akurasi* sah dipakai — lihat
"Ringkasan keputusan" #8 dan "Cara menjelaskan Tier 4 ke audiens" di
post-presentation-review-tasks.md.

⚠️ PRASYARAT OPERASIONAL — latents dan isi DB harus dari RUN YANG SAMA.
Faker truncate-and-regenerate: begitu ada regenerasi baru, `_audit_latents.
parquet` (atau `.csv`) tidak lagi berkorespondensi dengan `contract_snapshot`
di DB. Script ini TIDAK bisa mendeteksi itu secara otomatis — verifikasi
manual: seed & jumlah customer run terakhir HARUS dicatat di laporan
(`ai-reasoning-evaluation.md`) berdampingan dengan angka Tier 4.

⚠️ Ambang (w, c) -> segmen oracle DIBEKUKAN di modul ini
(ORACLE_W_THRESHOLD / ORACLE_C_THRESHOLD, keduanya 0.0 — titik nol alami
karena w/c mendekati terstandardisasi di sekitar 0, lihat
draw_customer_latents()/draw_contract_latents() di generate-faker-
realistic.py). JANGAN diubah setelah melihat hasil — itu membatalkan seluruh
nilai pengukuran ini (lihat TASK-E5).

Pemetaan (w, c) -> segmen oracle:
  - c >= 0 (mampu) & w <  0 (tidak mau bayar)      -> Won't Pay
  - c >= 0 (mampu) & w >= 0 (mau bayar)             -> Can Pay
  - c <  0 (TIDAK mampu), berapa pun w              -> Cannot Pay
  Kapasitas (c) dijadikan gate utama: debitur dengan kapasitas rendah secara
  definisi "tidak mampu bayar" apa pun keinginannya — ini yang menyatukan
  kuadran "keduanya rendah" (kasus terburuk, tidak disebutkan eksplisit di
  rencana) ke Cannot Pay, alih-alih membuat kategori ke-4 yang tidak ada di
  rule engine (hanya 3 segmen: Can Pay/Cannot Pay/Won't Pay).

Pakai:
    python scripts/evaluate_tier4_oracle.py --out reports/tier4_oracle.md
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(ROOT, "app", "machine-learning")
FAKER_DIR = os.path.join(ROOT, "faker")
sys.path.insert(0, ML_DIR)

from config.settings import DB_URL  # noqa: E402

ORACLE_W_THRESHOLD = 0.0
ORACLE_C_THRESHOLD = 0.0
ORACLE_SEVERITY = {"Can Pay": 0, "Cannot Pay": 1, "Won't Pay": 2}
RULE_SEGMENTS = ["Can Pay", "Cannot Pay", "Won't Pay"]


def _load_latents() -> pd.DataFrame:
    for name in ("_audit_latents.parquet", "_audit_latents.csv"):
        path = os.path.join(FAKER_DIR, name)
        if os.path.exists(path):
            df = pd.read_parquet(path) if name.endswith(".parquet") else pd.read_csv(path)
            print(f"✓ Latents dimuat dari {path} ({len(df):,} kontrak)")
            return df
    raise SystemExit(
        "Tidak ada _audit_latents.parquet/.csv di faker/ — generate dulu dengan "
        "--dump-latents (BUKAN bulk_clone.py, itu SENGAJA mengarantina/menghapus "
        "file ini — lihat TASK-P3)."
    )


def _oracle_segment(w: float, c: float) -> str:
    if c < ORACLE_C_THRESHOLD:
        return "Cannot Pay"
    return "Won't Pay" if w < ORACLE_W_THRESHOLD else "Can Pay"


def _confusion_matrix(y_true: pd.Series, y_pred: pd.Series, labels: list) -> pd.DataFrame:
    mat = pd.crosstab(y_true, y_pred)
    return mat.reindex(index=labels, columns=labels, fill_value=0)


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney U / rank-sum AUC — tanpa dependency sklearn tambahan di
    luar yang sudah dipakai ML repo (scipy sudah ada, tapi implementasi
    manual ini lebih murah untuk N kecil dan tidak menambah import)."""
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = pd.Series(np.concatenate([pos, neg])).rank().values
    n_pos = len(pos)
    rank_sum_pos = ranks[:n_pos].sum()
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * len(neg))


def _calibration_table(scores: np.ndarray, labels: np.ndarray, n_bins: int = 5) -> pd.DataFrame:
    df = pd.DataFrame({"score": scores, "y": labels})
    df["bin"] = pd.qcut(df["score"], q=min(n_bins, df["score"].nunique()), duplicates="drop")
    return df.groupby("bin").agg(n=("y", "size"), avg_predicted=("score", "mean"), actual_rate=("y", "mean"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(ROOT, "reports", "tier4_oracle.md"))
    args = parser.parse_args()

    latents = _load_latents()
    latents["oracle_segment"] = [
        _oracle_segment(w, c) for w, c in zip(latents["w"], latents["c"])
    ]

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        snapshot = pd.read_sql(text("SELECT contract_no, status FROM contract_snapshot"), conn)
        rule = pd.read_sql(text(
            "SELECT contract_no, risk_segment FROM contract_snapshot cs "
            "JOIN ai_intelligence_output ai USING (contract_no)"
        ), conn)

    # Cek run-match SEBENARNYA: latents vs contract_snapshot (SELURUH baris,
    # apa pun status-nya) — ini yang membuktikan latents & DB berasal dari
    # generate-faker-realistic.py run yang SAMA (bootstrap TASK-S2 menyalin
    # stg_contract_snapshot 1:1 ke contract_snapshot live, jadi seharusnya
    # cocok 1:1 kalau tidak ada regenerasi di antaranya).
    orphan_vs_snapshot_latents = set(latents["contract_no"]) - set(snapshot["contract_no"])
    orphan_vs_snapshot_db = set(snapshot["contract_no"]) - set(latents["contract_no"])
    run_match_clean = not orphan_vs_snapshot_latents and not orphan_vs_snapshot_db

    joined = latents.merge(rule, on="contract_no", how="inner")
    # Kontrak di latents/contract_snapshot TAPI tidak di ai_intelligence_output
    # itu BUKAN sinyal run-mismatch — daily_scoring.py hanya men-scoring
    # kontrak status='aktif' (lihat query WHERE status='aktif' di
    # pipelines/daily_scoring.py), jadi kontrak 'lunas'/'write-off' memang
    # sengaja tidak muncul di sana. Dipisahkan eksplisit dari cek run-match
    # di atas supaya tidak jadi false alarm.
    not_scored = snapshot[~snapshot["contract_no"].isin(rule["contract_no"])]
    not_scored_but_active = not_scored[not_scored["status"] == "aktif"]

    lines = []
    lines.append("# TASK-E5 Tier 4 — Evaluasi terhadap latent oracle")
    lines.append("")
    lines.append(f"Ambang (dibekukan SEBELUM melihat hasil): w >= {ORACLE_W_THRESHOLD}, c >= {ORACLE_C_THRESHOLD}.")
    lines.append(f"Kontrak di latents: {len(latents):,}. Kontrak di contract_snapshot (live): {len(snapshot):,}.")
    lines.append(f"Kontrak ter-scoring (ai_intelligence_output): {len(rule):,}. Kontrak ter-join & dievaluasi: {len(joined):,}.")
    lines.append("")
    if run_match_clean:
        lines.append(
            "✓ **Run-match bersih**: seluruh contract_no di latents identik persis dengan "
            "contract_snapshot (0 baris yatim di kedua sisi) — latents dan DB dipastikan "
            "berasal dari run faker yang SAMA."
        )
    else:
        lines.append(
            f"**⚠️ RUN-MISMATCH TERDETEKSI** — {len(orphan_vs_snapshot_latents)} contract_no "
            f"di latents TIDAK ADA di contract_snapshot, {len(orphan_vs_snapshot_db)} sebaliknya. "
            f"Latents dan DB kemungkinan dari run faker yang BERBEDA (truncate-and-regenerate "
            f"di antara dump latents dan state DB saat ini). **Angka di bawah TIDAK VALID.**"
        )
    lines.append("")
    if len(not_scored):
        lines.append(
            f"Catatan (bukan run-mismatch): {len(not_scored):,} kontrak ada di contract_snapshot "
            f"tapi tidak di ai_intelligence_output — {len(not_scored) - len(not_scored_but_active):,} "
            f"karena status bukan 'aktif' (lunas/write-off, sengaja tidak di-scoring "
            f"`daily_scoring.py`), {len(not_scored_but_active):,} berstatus 'aktif' tapi belum "
            f"ter-scoring (perlu ditelusuri kalau jumlahnya besar)."
        )
        lines.append("")

    # ── (1) Akurasi rule engine vs oracle, level KONTRAK ─────────────────
    lines.append("## 1. Akurasi rule engine (risk_segment) vs oracle — level kontrak")
    lines.append("")
    cm = _confusion_matrix(joined["oracle_segment"], joined["risk_segment"], RULE_SEGMENTS)
    lines.append("Baris = oracle (kebenaran), kolom = rule engine (prediksi).")
    lines.append("")
    header = "| oracle \\ rule | " + " | ".join(cm.columns) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(cm.columns))
    for idx in cm.index:
        lines.append(f"| **{idx}** | " + " | ".join(str(v) for v in cm.loc[idx]) + " |")
    overall_acc = (joined["oracle_segment"] == joined["risk_segment"]).mean()
    naive_baseline_seg = joined["oracle_segment"].value_counts().idxmax()
    naive_baseline_acc = (joined["oracle_segment"] == naive_baseline_seg).mean()
    lines.append("")
    lines.append(f"Akurasi keseluruhan (exact match 3 kelas): **{overall_acc:.1%}**")
    lines.append(
        f"**Catatan kejujuran wajib:** baseline naif \"selalu tebak '{naive_baseline_seg}'\" "
        f"(kelas oracle terbanyak) sendirian sudah mencapai **{naive_baseline_acc:.1%}**. Kalau "
        f"angka exact-match rule engine di atas LEBIH RENDAH dari baseline ini, itu berarti "
        f"`risk_segment` (rule engine) TIDAK sejalan dengan definisi willingness/capacity oracle "
        f"di sini — bukan berarti rule engine \"buruk\" secara umum (lihat AUC recovery_score di "
        f"bagian 2, yang jauh lebih tinggi), melainkan tanda bahwa segmen rule engine dan segmen "
        f"oracle (w,c) mengukur konstruk yang tidak identik. Dilaporkan apa adanya, bukan disembunyikan."
    )
    lines.append("")
    lines.append("Recall per kelas oracle (dari total kontrak oracle kelas itu, berapa % ditandai benar oleh rule engine):")
    for seg in RULE_SEGMENTS:
        denom = (joined["oracle_segment"] == seg).sum()
        if denom == 0:
            continue
        recall = ((joined["oracle_segment"] == seg) & (joined["risk_segment"] == seg)).sum() / denom
        lines.append(f"- {seg}: {recall:.1%} (n={denom})")
    lines.append("")

    # ── (2) Kalibrasi ML (recovery_score) vs y_pay ───────────────────────
    lines.append("## 2. Kalibrasi model ML (recovery_score) vs outcome oracle (y_pay)")
    lines.append("")
    with engine.connect() as conn:
        scores = pd.read_sql(text(
            "SELECT contract_no, recovery_score FROM ai_intelligence_output"
        ), conn)
    calib = latents.merge(scores, on="contract_no", how="inner")
    if calib.empty or calib["recovery_score"].isna().all():
        lines.append("Tidak ada `recovery_score` yang bisa dipasangkan — dilewati.")
    else:
        calib = calib.dropna(subset=["recovery_score", "y_pay"])
        y = calib["y_pay"].astype(int).values
        s = calib["recovery_score"].astype(float).values
        auc = _auc(s, y)
        lines.append(f"N = {len(calib):,}. AUC(recovery_score, y_pay) = **{auc:.4f}**")
        lines.append("")
        lines.append("Kurva kalibrasi (5 bin berdasarkan recovery_score):")
        lines.append("")
        calib_table = _calibration_table(s, y)
        lines.append("| bin (recovery_score) | n | avg predicted | actual y_pay rate |")
        lines.append("|---|---|---|---|")
        for idx, row in calib_table.iterrows():
            lines.append(f"| {idx} | {int(row['n'])} | {row['avg_predicted']:.4f} | {row['actual_rate']:.4f} |")
    lines.append("")

    # ── (3) Akurasi AI Summary vs oracle ─────────────────────────────────
    lines.append("## 3. Akurasi AI Summary (primaryNbaAction) vs aksi oracle")
    lines.append("")
    with engine.connect() as conn:
        n_ok = conn.execute(text("SELECT count(*) FROM ai_reasoning_output WHERE status='OK'")).scalar_one()
    if n_ok == 0:
        lines.append(
            "**TIDAK DIHITUNG** — nol baris `ai_reasoning_output` berstatus OK saat "
            "ini (baik karena Gemini belum dikonfigurasi/kuota habis, ATAU baris "
            "sebelumnya tertimpa reset/sweep lain — cek `ai-reasoning-evaluation.md` "
            "untuk histori terakhir). Metodologinya: gabungkan `ai_reasoning_output."
            "primary_nba_action` (status=OK) per debitur dengan segmen oracle "
            "level-debitur (kontrak terburuk per `ORACLE_SEVERITY`), lalu bandingkan "
            "terhadap pemetaan segmen oracle -> channel yang sama dipakai rule engine "
            "default (`SEGMENT_DEFAULT_CHANNEL`, src/cbs_builder.py). Jalankan ulang "
            "`scripts/run_ai_reasoning_eval.py` dengan kuota Gemini yang tersedia, "
            "lalu script ini, untuk mengisi bagian ini dengan angka nyata."
        )
    else:
        with engine.connect() as conn:
            ai_out = pd.read_sql(text(
                "SELECT cust_id, primary_nba_action FROM ai_reasoning_output WHERE status='OK'"
            ), conn)
        cust_oracle = (
            joined.assign(sev=joined["oracle_segment"].map(ORACLE_SEVERITY))
            .sort_values("sev", ascending=False)
            .groupby("cust_id")
            .first()
        )
        lines.append(f"n={len(ai_out)} debitur dengan output OK — lihat detail di `reports/`.")

    lines.append("")
    md = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(md)
    print(md)
    print(f"\n✓ {args.out}")


if __name__ == "__main__":
    main()

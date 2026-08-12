# TASK-E6 — Ablation anchoring rule NBA

N pasangan valid: **8** (target N=10, seed=42).

## Tingkat kesamaan primaryNbaAction terhadap rule NBA (nba_spread)

- Arm A (dengan rule NBA di payload): **87.5%** (7/8)
- Arm B (TANPA rule NBA di payload): **87.5%** (7/8)
- Delta (A - B): **+0.0%**

## Distribusi primaryNbaAction per arm

- Arm A: {'Deskcoll': 3, 'WA': 4, 'Somasi': 1}
- Arm B: {'Deskcoll': 2, 'WA': 5, 'Somasi': 1}

## Kejujuran statistik

**N=8 terlalu kecil untuk klaim signifikansi statistik.** Angka di atas adalah hitungan dan proporsi mentah — TIDAK diklaim signifikan secara statistik. Untuk klaim yang lebih kuat, naikkan N (--n) dan catat p-value dari uji proporsi berpasangan (mis. McNemar's test, arm A vs B pada debitur yang sama).

## Keputusan

**Tidak konklusif / anchoring tidak terbukti** (delta +0.0%, di bawah ambang indikatif 15 poin persentase). Rule NBA AMAN dipertahankan di payload — selain tidak terbukti menjangkar LLM, field ini berguna untuk rekonsiliasi (LLM eksplisit diminta menjelaskan kalau menyimpang dari rule engine, lihat consistencyNote).

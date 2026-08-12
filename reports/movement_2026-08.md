# Laporan pergerakan — 2026-08-01 -> 2026-08-31

Kontrak dibandingkan: **426** (hanya kontrak yang punya baris di kedua tanggal).

## Ringkasan agregat

- recovery_score naik: **227** (53.3%)
- recovery_score turun: **197** (46.2%)
- recovery_score tetap: **2** (0.5%)
- risk_segment berubah: **130** (30.5%)
- nba_recommendation berubah: **120** (28.2%)

## Distribusi risk_segment

- 2026-08-01: {"Won't Pay": 233, 'Cannot Pay': 100, 'Can Pay': 93}
- 2026-08-31: {"Won't Pay": 207, 'Can Pay': 130, 'Cannot Pay': 89}

## Distribusi priority_level

- 2026-08-01: {'Critical': 252, 'High': 98, 'Medium': 68, 'Low': 8}
- 2026-08-31: {'Critical': 218, 'High': 108, 'Medium': 82, 'Low': 18}

## Matriks transisi risk_segment (2026-08-01 -> 2026-08-31)

| dari \ ke | Can Pay | Cannot Pay | Won't Pay |
|---|---|---|---|
| **Can Pay** | 74 | 16 | 3 |
| **Cannot Pay** | 32 | 43 | 25 |
| **Won't Pay** | 24 | 30 | 179 |

## Top 10 mover (perubahan recovery_score terbesar)

| contract_no | cust_id | segment (d0->dn) | score (d0->dn) | delta | dpd (d0->dn) | nba (d0->dn) |
|---|---|---|---|---|---|---|
| CTR-00151-1 | CUST-00151 | Won't Pay -> Can Pay | 0.1181 -> 0.8640 | +0.7459 | 179 -> 209 | Somasi -> Deskcoll |
| CTR-00291-1 | CUST-00291 | Won't Pay -> Can Pay | 0.2020 -> 0.9239 | +0.7219 | 269 -> 299 | Somasi -> Deskcoll |
| CTR-00272-1 | CUST-00272 | Won't Pay -> Can Pay | 0.1740 -> 0.7802 | +0.6062 | 234 -> 264 | Somasi -> Visit |
| CTR-00253-2 | CUST-00253 | Won't Pay -> Can Pay | 0.1150 -> 0.7152 | +0.6002 | 185 -> 215 | Somasi -> Deskcoll |
| CTR-00190-1 | CUST-00190 | Won't Pay -> Can Pay | 0.0847 -> 0.6439 | +0.5592 | 314 -> 344 | Somasi -> Deskcoll |
| CTR-00112-2 | CUST-00112 | Won't Pay -> Can Pay | 0.1694 -> 0.7204 | +0.5510 | 412 -> 442 | Somasi -> Deskcoll |
| CTR-00040-2 | CUST-00040 | Won't Pay -> Can Pay | 0.2976 -> 0.8346 | +0.5370 | 159 -> 189 | Somasi -> Deskcoll |
| CTR-00162-1 | CUST-00162 | Cannot Pay -> Can Pay | 0.3373 -> 0.8699 | +0.5326 | 325 -> 355 | Visit -> Deskcoll |
| CTR-00001-2 | CUST-00001 | Cannot Pay -> Can Pay | 0.3578 -> 0.8883 | +0.5305 | 687 -> 717 | Visit -> Deskcoll |
| CTR-00079-1 | CUST-00079 | Cannot Pay -> Can Pay | 0.3659 -> 0.8751 | +0.5092 | 318 -> 348 | Visit -> Deskcoll |

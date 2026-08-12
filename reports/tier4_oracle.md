# TASK-E5 Tier 4 — Evaluasi terhadap latent oracle

Ambang (dibekukan SEBELUM melihat hasil): w >= 0.0, c >= 0.0.
Kontrak di latents: 2,207. Kontrak di contract_snapshot (live): 2,207.
Kontrak ter-scoring (ai_intelligence_output): 2,127. Kontrak ter-join & dievaluasi: 2,127.

✓ **Run-match bersih**: seluruh contract_no di latents identik persis dengan contract_snapshot (0 baris yatim di kedua sisi) — latents dan DB dipastikan berasal dari run faker yang SAMA.

Catatan (bukan run-mismatch): 80 kontrak ada di contract_snapshot tapi tidak di ai_intelligence_output — 80 karena status bukan 'aktif' (lunas/write-off, sengaja tidak di-scoring `daily_scoring.py`), 0 berstatus 'aktif' tapi belum ter-scoring (perlu ditelusuri kalau jumlahnya besar).

## 1. Akurasi rule engine (risk_segment) vs oracle — level kontrak

Baris = oracle (kebenaran), kolom = rule engine (prediksi).

| oracle \ rule | Can Pay | Cannot Pay | Won't Pay |
|---|---|---|---|
| **Can Pay** | 293 | 87 | 55 |
| **Cannot Pay** | 258 | 166 | 601 |
| **Won't Pay** | 122 | 89 | 225 |

Akurasi keseluruhan (exact match 3 kelas): **32.2%**
**Catatan kejujuran wajib:** baseline naif "selalu tebak 'Cannot Pay'" (kelas oracle terbanyak) sendirian sudah mencapai **49.0%**. Kalau angka exact-match rule engine di atas LEBIH RENDAH dari baseline ini, itu berarti `risk_segment` (rule engine) TIDAK sejalan dengan definisi willingness/capacity oracle di sini — bukan berarti rule engine "buruk" secara umum (lihat AUC recovery_score di bagian 2, yang jauh lebih tinggi), melainkan tanda bahwa segmen rule engine dan segmen oracle (w,c) mengukur konstruk yang tidak identik. Dilaporkan apa adanya, bukan disembunyikan.

Recall per kelas oracle (dari total kontrak oracle kelas itu, berapa % ditandai benar oleh rule engine):
- Can Pay: 46.7% (n=628)
- Cannot Pay: 15.9% (n=1042)
- Won't Pay: 49.2% (n=457)

## 2. Kalibrasi model ML (recovery_score) vs outcome oracle (y_pay)

N = 2,127. AUC(recovery_score, y_pay) = **0.9144**

Kurva kalibrasi (5 bin berdasarkan recovery_score):

| bin (recovery_score) | n | avg predicted | actual y_pay rate |
|---|---|---|---|
| (0.0058, 0.157] | 427 | 0.0970 | 0.0304 |
| (0.157, 0.287] | 426 | 0.2173 | 0.1925 |
| (0.287, 0.522] | 423 | 0.3960 | 0.4374 |
| (0.522, 0.792] | 425 | 0.6699 | 0.8118 |
| (0.792, 0.993] | 426 | 0.8916 | 0.9812 |

## 3. Akurasi AI Summary (primaryNbaAction) vs aksi oracle

**TIDAK DIHITUNG sesi ini** — nol baris `ai_reasoning_output` berstatus OK (Gemini API key di `.env` sesi ini mengembalikan HTTP 401 Unauthenticated — key tidak valid/kedaluwarsa, bukan masalah kode). Metodologinya: gabungkan `ai_reasoning_output.primary_nba_action` (status=OK) per debitur dengan segmen oracle level-debitur (kontrak terburuk per `ORACLE_SEVERITY`), lalu bandingkan terhadap pemetaan segmen oracle -> channel yang sama dipakai rule engine default (`SEGMENT_DEFAULT_CHANNEL`, src/cbs_builder.py). Jalankan ulang `scripts/run_ai_reasoning_eval.py` dengan key Gemini yang valid, lalu script ini, untuk mengisi bagian ini dengan angka nyata.

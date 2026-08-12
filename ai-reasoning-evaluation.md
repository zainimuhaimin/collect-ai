# Evaluasi AI Reasoning — Metode, Metrik, Hasil (TASK-E5/E6)

> Rujuk `ai-reasoning-prompt-spec.md` untuk detail prompt/payload/response
> schema — TIDAK diulang di sini. Dokumen ini merujuk `post-presentation-
> review-tasks.md` (Area 3) untuk desain lengkap; berisi hasil aktual dan
> keputusan yang diambil.
>
> **Dataset yang dipakai untuk hasil di bawah:** `faker/generate-faker-
> realistic.py --customers 1500 --seed 20260101 --dump-latents` (as_of =
> tanggal jalan, 2026-08-12) → 2.207 kontrak (2.127 aktif, 75 write-off, 5
> lunas) → 4 model dilatih dari nol → `daily_scoring.py` sekali. **Bukan**
> data hasil `bulk_clone.py` (yang memang dikarantina dari evaluasi akurasi,
> lihat TASK-P3) — latents `_audit_latents.csv` dan isi DB dikonfirmasi
> berasal dari run yang SAMA (lihat §4, "run-match bersih").
>
> **⚠️ Update (sesi lanjutan, key Gemini diperbarui user) — status berubah,
> bukan lagi 401.** Dengan key baru, `GeminiClient.generate()` berhasil
> (diverifikasi manual: panggilan langsung sukses, model terpakai
> `gemini-3.6-flash`). **Tapi key ini kena rate-limit (HTTP 429,
> `gemini_quota`) setelah ±10-11 panggilan berurutan**, dan TIDAK pulih
> setelah backoff 8s+20s per percobaan maupun jeda beberapa menit antar
> batch — pola ini konsisten dengan kuota HARIAN tier gratis yang habis
> (bukan sekadar rate-limit per-menit), bukan lagi 401 (kredensial tidak
> valid). **Retry otomatis ditambahkan** ke `scripts/run_ai_reasoning_eval.py`
> (`--sleep-seconds`, backoff 8s/20s khusus untuk `gemini_quota`) — sudah
> terpakai, tidak menyelesaikan masalah kuota harian itu sendiri.
>
> **4 generasi OK NYATA berhasil didapat** (CUST-00001, CUST-00003,
> CUST-00009, CUST-00012) sebelum kuota habis — Tier 1 pada keempatnya:
> 0 halusinasi kontrak, agreement konsisten pada semuanya,
> `unsupported_claim_rate` = 0%, 0%, 6,67%, 20% berurutan (CUST-00012's 20%
> layak ditelusuri lebih lanjut — kemungkinan model mengutip angka yang
> tidak persis cocok toleransi, bukan otomatis berarti halusinasi, lihat
> catatan toleransi grounding di `services/ai_reasoning_eval.py`).
> **Baris-baris ini kemudian TERTIMPA** oleh sweep performa TASK-P5
> (`perf/benchmark_scale.py`, dijalankan bersamaan untuk mengukur ulang RAM
> setelah chunked-read — `reset-demo.sh` antar rung men-TRUNCATE
> `ai_reasoning_output`/`ai_reasoning_evaluation` juga) — angka di atas
> dikutip langsung dari log terminal saat run, bukan dari query DB saat ini.
>
> **Kesimpulan operasional:** harness Tier 1-3 TERBUKTI bekerja pada output
> LLM sungguhan (bukan cuma FALLBACK/unit test), tapi sampel N=4 terlalu
> kecil untuk kesimpulan agregat, dan TASK-E6 ablation (butuh puluhan
> panggilan berpasangan) TIDAK bisa dijalankan sampai kuota harian pulih
> (kemungkinan besok, atau dengan key/provider berbayar). Akibatnya:
> - **Tier 1-3** (§2-3): harness lengkap, diuji unit test (19 test baru,
>   `pytest app/backend/tests/test_ai_reasoning_eval.py`), **dan sudah
>   divalidasi pada 4 output LLM sungguhan** (di atas) — N terlalu kecil
>   untuk statistik agregat yang bermakna.
> - **TASK-E6 ablation** (§5): script lengkap dan diverifikasi jalan
>   (menangani kegagalan API dengan benar, exit bersih saat 0 pasangan valid)
>   — **tidak ada angka delta anchoring nyata** karena kuota habis sebelum
>   sempat mengumpulkan pasangan arm A/B yang cukup.
> - **Tier 4** (§4) **TIDAK terpengaruh** — murni analisis data (latents vs
>   DB), tidak butuh LLM sama sekali. Angka di §4 nyata dan lengkap.
>
> Siapa pun dengan kuota Gemini yang tersedia (atau key GLM untuk Tier 2)
> bisa mengisi §2/§3/§5 dengan angka nyata tanpa mengubah kode — jalankan
> dengan N kecil dan --sleep-seconds besar (10-15s) supaya tidak langsung
> kena kuota lagi:
> ```
> python scripts/run_ai_reasoning_eval.py --limit 30 --tier3-sample 5
> python scripts/ablation_nba.py --n 50
> python scripts/evaluate_tier4_oracle.py   # (isi §3 bagian 3 otomatis terisi kalau ada output OK)
> ```

---

## 1. Ringkasan status per komponen

| Komponen | Status | Catatan |
|---|---|---|
| E1 — skor lengkap di payload | ✅ selesai (sesi sebelumnya) | lihat post-presentation-review-tasks.md |
| E2 — nba_agreement dihitung di kode | ✅ selesai (sesi sebelumnya) | |
| E3 — PROMPT_VERSION v2 + audit Pickup | ✅ selesai (sesi sebelumnya) | |
| E4 — unit test ai_reasoning | ✅ selesai (sesi sebelumnya) | 68 test |
| E5 — Tier 1 (deterministic) | ✅ kode + test selesai; ✅ divalidasi pada 4 output OK nyata (N kecil) | 19 unit test baru + 4 sampel nyata |
| E5 — Tier 2 (LLM-judge) | ✅ kode + test selesai; ⚠️ belum pernah dipanggil ke GLM sungguhan | `JUDGE_ENABLED=false`, tidak ada key |
| E5 — Tier 3 (self-consistency) | ✅ kode selesai; ⚠️ kuota habis sebelum sampel terkumpul | |
| E5 — Tier 4 (latent oracle) | ✅ **selesai dengan angka nyata** | lihat §4 |
| E6 — include_rule_nba + ablation | ✅ kode + test selesai; ⚠️ 0 pasangan nyata (kuota Gemini habis) | |

---

## 2. Tier 1 — Deterministic checks

**Metode.** `app/backend/services/ai_reasoning_eval.py` — 5 pemeriksaan tanpa
LLM, jalan pada dict hasil `ai_reasoning_output` + payload yang REBUILD ulang
(via `build_payload()`, dipanggil lewat `AiReasoningService.generate(force=
True)` yang sama supaya payload persis yang dilihat LLM saat itu, menghindari
masalah staleness):

1. **Numeric grounding** — tiap angka yang dikutip `summary`/
   `customer_treatment_strategy`/`key_factors`/`per_contract_focus[].note`
   harus ada di payload, dengan toleransi format Indonesia (titik=ribuan,
   koma=desimal) dan bentuk turunan wajar (fraksi↔persen, dibulatkan ribu/juta).
   Angka ≤3 diabaikan (hampir selalu kata ganti jumlah generik di narasi
   Bahasa Indonesia, bukan klaim data).
2. **Integritas kontrak** — `perContractFocus[].contractNo` harus subset
   `analyzed_contract_nos` (deteksi halusinasi) DAN menutup semuanya (deteksi
   kontrak terlewat).
3. **Konsistensi agreement** — `nba_agreement` tersimpan dibandingkan ULANG
   dengan hasil hitung `primary_nba_action` vs `nba_spread` — ini
   MEMVERIFIKASI ULANG hasil TASK-E2, bukan mengasumsikannya benar.
4. **Monotonisitas urgensi** — pelanggaran BESAR (jarak >1 level) antara
   urutan dpd dan urutan urgensi per kontrak ditandai sebagai inversion (soft).
5. **Validitas enum** — `primaryNbaAction` ∈ `NBA_ACTIONS`, `urgency` ∈
   {LOW,MEDIUM,HIGH,CRITICAL}.

**Diuji dengan 19 unit test sintetis** (`test_ai_reasoning_eval.py`) —
mencakup kasus grounded/ungrounded, format Rupiah, halusinasi kontrak,
cakupan hilang, mismatch agreement, inversion urgensi, enum tidak valid, dan
tiga skenario Tier 2 (sukses, gagal parse, timeout).

**Hasil nyata — dua tahap.** Tahap 1 (`--limit 15`, key Gemini 401 saat itu):
seluruh 15 sampel jatuh ke status **FALLBACK**. Pada jalur FALLBACK ini: 0/15
halusinasi kontrak, 15/15 `agreement_consistent` (FALLBACK secara desain
tidak pernah mengisi `nba_agreement`, jadi None-vs-None — bukan sinyal palsu
berkat perbaikan kecil di driver script: `nba_spread` dikirim kosong untuk
status selain OK), 15/15 valid enum, 15/15 monoton urgensi (trivial —
FALLBACK tidak mengisi `per_contract_focus`).

Tahap 2 (`--limit 40`, setelah key diperbarui): **4 status OK nyata**
(CUST-00001/03/09/12) sebelum kuota harian habis (`gemini_quota`/429,
lihat catatan di atas dokumen). Numeric grounding pada keempatnya: 0%, 0%,
6,67%, 20% `unsupported_claim_rate` — pertama kali Tier 1 punya data
grounding NYATA (bukan trivial-kosong seperti jalur FALLBACK). 0/4
halusinasi kontrak, 4/4 `agreement_consistent`, 4/4 valid enum. **N=4
terlalu kecil untuk kesimpulan agregat** — CUST-00012's 20% layak
ditelusuri manual (lihat baris mentah di log, bukan otomatis berarti
halusinasi — toleransi grounding punya batas format yang belum tentu
menutup semua variasi penulisan angka LLM).

Baris DB dari kedua tahap **tertimpa** oleh sweep performa TASK-P5 yang
berjalan bersamaan (reset antar rung men-TRUNCATE tabel ini juga) — angka
di atas dikutip dari log terminal saat run, bukan dari query DB saat
dokumen ini terakhir diperbarui. `reports/ai_reasoning_eval_tier123.json`
(lokal, tidak ikut ter-reset) menyimpan detail tahap terakhir yang berhasil
ditulis sebelum proses dihentikan.

---

## 3. Tier 2 — LLM-as-judge & Tier 3 — Self-consistency

**Tier 2.** `app/backend/services/openai_compat_client.py` — klien
`/chat/completions` generik (GLM/Zhipu direkomendasikan; base URL + model bisa
diganti ke DeepSeek/Qwen/OpenRouter/Ollama). Protocol `LlmClient` diekstrak
(`services/llm_client.py`) — `GeminiClient` tetap TIDAK diubah sama sekali
(duck typing, `pytest app/backend/tests/ -q` tetap hijau 89 test setelah
ekstraksi). Rubrik 1-5: faithfulness, actionability, internal_consistency,
key_factors_alignment. **Kegagalan parse/HTTP dicatat `judge_failed=True`,
BUKAN skor 0** (diuji eksplisit: `test_tier2_judge_failure_is_not_scored_zero`,
`test_tier2_judge_timeout_is_judge_failure`) — mencegah pencemaran rata-rata.
`judge_skipped=True` (beda dari `judge_failed`) saat `JUDGE_ENABLED=false`
atau tidak ada key.

**✅ Konektivitas GLM diuji nyata (2026-08-12, sesi lanjutan)** setelah user
memprovisikan `JUDGE_API_KEYS` (`https://api.z.ai/api/coding/paas/v4`,
model `glm-5.1` di config, merespons sebagai `glm-5.2`). `run_tier2_judge()`
dipanggil langsung dengan payload real (`CUST-00001`) dan dua record ai_output
BUATAN TANGAN (bukan hasil generate Gemini nyata — kuota Gemini masih 429,
lihat §5) untuk menguji dua ujung ekstrem:

| Record | Skor (faithfulness/actionability/internal_consistency/key_factors_alignment) |
|---|---|
| Grounded (klaim cocok payload nyata) | 5 / 4 / 5 / 5 |
| Fabricated (kontrak fiktif, angka bertentangan data) | 1 / 1 / 1 / 1 |

Integrasi BEKERJA end-to-end (HTTP nyata, parse Pydantic sukses) dan judge-nya
**diskriminatif** (bukan default selalu tinggi). Ini uji mekanisme, BUKAN
evaluasi Tier 2 produksi — populasi output Gemini nyata untuk dinilai masih
menunggu kuota tersedia.

**✅ Pasangan Gemini→GLM SUNGGUHAN diperoleh (2026-08-12, percobaan lanjutan)**
setelah user mengganti model Gemini ke `gemini-3.5-flash` (key sama, kuota
429 sebelumnya ternyata terkait model lama, bukan key). `CUST-00001`
digenerate ulang (real call, bukan tangan) lalu langsung dinilai GLM:
faithfulness=**5**, actionability=**4**, internal_consistency=**5**,
key_factors_alignment=**5** — **identik** dengan skor record "grounded"
buatan tangan di atas, memberi validasi silang yang baik antara uji mekanisme
dan uji nyata. Tier 1 pada output yang sama: `unsupported_claim_rate=0%`
(15 angka dikutip, 0 tak berdasar), `agreement_consistent=True`,
`urgency_monotonic=True`, `valid_enum=True`. N=1 — arah positif, jelas
belum cukup untuk klaim agregat Tier 1/2 produksi, tapi ini pasangan
Gemini-asli/GLM-asli PERTAMA yang berhasil didapat sesi ini.

**Tier 3.** K=3 panggilan ulang (`force=True`) per debitur sampel, ukur
variansi `primaryNbaAction`. Driver script hanya menjalankan ini untuk status
OK (percuma untuk FALLBACK — hasilnya deterministik dari rule engine, bukan
LLM). Pada tahap awal (key 401) 0 sampel terkumpul; setelah key diperbarui,
K=3 sempat tercatat konsisten untuk 1-2 debitur (`tier3_consistent=True`)
sebelum kuota habis menghentikan sisa sampel `--tier3-sample`. Terlalu
sedikit untuk klaim agregat, tapi mekanismenya terbukti bekerja pada
panggilan LLM sungguhan.

**Konfigurasi baru** (`core/config.py` + `.env.example`): `judge_enabled`,
`judge_api_base_url`, `judge_api_keys`, `judge_model`, `judge_timeout_seconds`
— default `judge_enabled=false`, mengikuti pola `ai_reasoning_enabled` yang
sudah ada.

---

## 4. Tier 4 — Latent oracle (satu-satunya jalur akurasi yang sah)

**Ambang dibekukan SEBELUM melihat hasil** (tercatat di
`scripts/evaluate_tier4_oracle.py`, konstanta `ORACLE_W_THRESHOLD=0.0`,
`ORACLE_C_THRESHOLD=0.0`): kapasitas (`c`) sebagai gate utama —
`c<0` → **Cannot Pay** (berapa pun `w`, karena kapasitas adalah batasan fisik:
debitur mau bayar pun tidak akan bisa tanpa kapasitas); `c>=0 & w<0` →
**Won't Pay** (mampu, tidak mau); `c>=0 & w>=0` → **Can Pay**. Ini
menyederhanakan pemetaan 2×2 dari rencana awal jadi 3 kelas yang cocok
langsung dengan output rule engine (`risk_segment` hanya punya 3 nilai
relevan: Can Pay/Cannot Pay/Won't Pay).

**Run-match dipastikan bersih**: 2.207 contract_no di `_audit_latents.csv`
= 2.207 di `contract_snapshot` (0 baris yatim kedua arah) — latents dan DB
dari run faker yang SAMA, prasyarat mutlak sebelum angka apa pun di bawah
bisa dipercaya.

### 4a. Akurasi rule engine (`risk_segment`) vs oracle

| oracle \ rule | Can Pay | Cannot Pay | Won't Pay |
|---|---|---|---|
| **Can Pay** | 293 | 87 | 55 |
| **Cannot Pay** | 258 | 166 | 601 |
| **Won't Pay** | 122 | 89 | 225 |

Akurasi exact-match 3 kelas: **32,2%**.

**Catatan kejujuran wajib (ditulis otomatis oleh script, bukan komentar
setelah-fakta):** baseline naif "selalu tebak Cannot Pay" (kelas oracle
terbanyak, n=1.042/2.127) sendirian sudah mencapai **49,0%** — LEBIH TINGGI
dari rule engine di atas. Recall per kelas: Can Pay 46,7%, **Cannot Pay
15,9%** (sangat rendah), Won't Pay 49,2%.

**Interpretasi jujur:** `risk_segment` (rule engine) TIDAK sejalan dengan
definisi willingness/capacity oracle seperti dipetakan di sini. Ini BUKAN
berarti rule engine "buruk" secara umum — lihat §4b, di mana `recovery_score`
(model ML yang menjadi salah satu input `risk_segment`) justru SANGAT
terkalibrasi terhadap outcome oracle. Kemungkinan penjelasan: `risk_segment`
rule engine mempertimbangkan faktor tambahan (histori PTP, behavioral grade,
dst di luar w/c mentah) yang membuat pemetaan 2-variabel (w,c) → 3 kelas di
sini tidak identik dengan konstruk yang sebenarnya dipakai `apply_risk_
segment()`. Dilaporkan apa adanya sesuai prinsip "kalau kunci jawabannya
sendiri tidak sempurna, itu berlaku sama untuk semua yang diuji dengannya" —
tapi gap terhadap baseline naif ini **layak diinvestigasi lebih lanjut**
sebelum dipresentasikan sebagai bukti kelemahan rule engine (lihat §6, tidak
dikerjakan sesi ini, direkomendasikan untuk sesi berikutnya).

### 4b. Kalibrasi model ML (`recovery_score`) vs outcome oracle (`y_pay`)

N = 2.127. **AUC(recovery_score, y_pay) = 0,9144.**

| bin (recovery_score) | n | avg predicted | actual y_pay rate |
|---|---|---|---|
| 0,006–0,157 | 427 | 0,097 | 0,030 |
| 0,157–0,287 | 426 | 0,217 | 0,193 |
| 0,287–0,522 | 423 | 0,396 | 0,437 |
| 0,522–0,792 | 425 | 0,670 | 0,812 |
| 0,792–0,993 | 426 | 0,892 | 0,981 |

**Kalibrasi sangat baik** — avg predicted naik monoton bersama actual rate di
setiap bin, dan keduanya berdekatan (tidak ada bin yang predicted-nya jauh
melenceng dari observed). AUC 0,91 jauh di atas ekspektasi awal desain data
("Bayes-optimal AUC ≈0,83", lihat docstring `generate-faker-realistic.py`) —
**catatan kejujuran:** ini kemungkinan karena `y_pay` di sini adalah outcome
LABEL-WINDOW (30 hari ke depan dari cutoff training) yang model memang
dilatih untuk memprediksi LANGSUNG (bukan proxy tidak langsung), sedangkan
angka 0,83 di dokumentasi generator adalah batas Bayes teoretis untuk
klasifikasi biner murni dari sinyal (w,c,shock) — recovery_score adalah
gabungan banyak fitur turunan (dpd, delay trend, dst) yang secara kolektif
bisa melebihi sinyal (w,c) mentah sendirian. Bukan indikasi kebocoran data —
`daily_scoring.py`/training pipeline TIDAK pernah menyentuh `w`/`c`/`y_pay`
(itulah inti desain latent oracle).

### 4c. Akurasi AI Summary (`primaryNbaAction`) vs aksi oracle

**Tidak dihitung sesi ini** — 0 baris `ai_reasoning_output` berstatus OK
(lihat keterbatasan 401 di atas). Metodologi (kode sudah ada di
`scripts/evaluate_tier4_oracle.py`, bagian 3): gabungkan
`ai_reasoning_output.primary_nba_action` (status=OK) per debitur dengan
segmen oracle level-debitur (kontrak TERBURUK per debitur, `ORACLE_SEVERITY`
= Can Pay(0) < Cannot Pay(1) < Won't Pay(2), konsisten dengan aturan prompt
"urgensi mengikuti kontrak terburuk"), lalu bandingkan terhadap pemetaan
segmen oracle → channel yang sama dipakai rule engine default
(`SEGMENT_DEFAULT_CHANNEL`, `src/cbs_builder.py`). Jalankan ulang
`scripts/run_ai_reasoning_eval.py` dengan key Gemini valid untuk mengisi ini.

### Perbandingan tiga arah (oracle vs rule engine vs LLM)

**Belum lengkap** — sisi LLM (§4c) kosong sesi ini. §4a (rule engine) dan
§4b (kalibrasi ML) sudah terisi nyata; grafik tiga-batang di "Cara
menjelaskan Tier 4 ke audiens" (post-presentation-review-tasks.md) BELUM bisa
diisi penuh sampai §4c terisi.

---

## 5. TASK-E6 — Ablation anchoring rule NBA

**Kode selesai, diverifikasi jalan, 0 angka nyata** — bukan lagi karena 401,
tapi karena kuota harian Gemini habis sebelum sempat mengumpulkan pasangan
arm A/B (lihat keterbatasan di atas; setiap pasangan butuh 2 panggilan
sukses berurutan, sedangkan kuota habis di sekitar panggilan ke-10).

- `build_payload(..., include_rule_nba: bool = True)` — saat `False`,
  `nba_recommendation`/`nba_trigger` per kontrak dan `nba_spread` di rollup
  DIHILANGKAN dari payload sepenuhnya. Diuji 2 unit test baru
  (`test_build_payload_includes_rule_nba_by_default`,
  `test_build_payload_omits_rule_nba_when_disabled`).
  **Sengaja TIDAK di-thread ke `AiReasoningService.generate()`** — kalau
  diteruskan sampai sana, hasil ablation (arm B) akan tersimpan ke
  `ai_reasoning_output` dengan cache key yang SAMA seperti output produksi
  normal, mencampur dua populasi yang harus terpisah.
- `scripts/ablation_nba.py` — bypass `AiReasoningService` SEPENUHNYA,
  memanggil `build_payload()` + `GeminiClient.generate()` langsung per arm,
  TIDAK menyentuh cache/DB produksi maupun `ai_reasoning_daily_call_limit`
  sama sekali. Diverifikasi: `python scripts/ablation_nba.py --n 3` berjalan
  bersih sampai selesai, menangani seluruh 3 sampel gagal (401) dengan pesan
  jelas dan keluar tanpa crash saat 0 pasangan valid — bukan silent failure.
- Ambang keputusan (**ditulis di kode SEBELUM ada angka apa pun**, lihat
  `ablation_nba.py`): delta agreement-rate (arm A − arm B) ≥ **15 poin
  persentase** → anchoring terbukti, buang rule NBA dari payload produksi.
  ≤ −15 poin → pola tak terduga, tidak boleh diklaim sebagai anchoring.
  Selain itu → tidak konklusif, rule NBA aman dipertahankan.
- **Kejujuran statistik**: script mencetak peringatan eksplisit kalau N<30
  ("TIDAK diklaim signifikan secara statistik"), dan menyarankan uji McNemar
  berpasangan untuk klaim formal — belum diimplementasikan (di luar scope
  minimum TASK-E6).

**Keputusan akhir TIDAK bisa diambil sesi ini** — tanpa API key Gemini yang
valid, tidak ada satu pun pasangan arm A/B yang berhasil digenerate. Rule NBA
untuk saat ini **dipertahankan di payload produksi** (default `include_rule_
nba=True` tidak diubah) — bukan karena anchoring terbukti tidak ada, tapi
karena belum diukur sama sekali; mengubah default tanpa data adalah opini,
bukan keputusan berbasis angka seperti yang dituntut dokumen ini sendiri.

**⚠️ Percobaan ULANG (2026-08-12, sesi lanjutan, setelah GLM judge
ditambahkan) — hasil SAMA (0 pasangan), sebab BERBEDA.** Diverifikasi
langsung sesaat sebelum re-run: `GeminiClient.generate()` sekarang gagal
dengan **429 quota exceeded** (bukan 401 seperti percobaan pertama — key-nya
sendiri valid, kuota HARIAN yang habis). `python scripts/ablation_nba.py --n 3`
diulang: ke-3 sampel gagal di kedua arm dengan alasan yang sama. **Total di
seluruh sesi (401 lalu 429): 0 pasangan arm A/B nyata terkumpul di KEDUA
kesempatan.**

**✅✅ HASIL NYATA AKHIRNYA DIPEROLEH — percobaan ke-3 (2026-08-12), setelah
user mengganti MODEL Gemini ke `gemini-3.5-flash`.** Bukan lagi 401 atau
429 — panggilan sukses untuk mayoritas sampel.
`python scripts/ablation_nba.py --n 10 --seed 42`:

| Metrik | Nilai |
|---|---|
| N pasangan valid | **8/10** (2 dilewati — satu arm gagal per pasangan) |
| Arm A (dengan rule NBA) agree-rate vs rule | **87,5%** (7/8) |
| Arm B (TANPA rule NBA) agree-rate vs rule | **87,5%** (7/8) |
| Delta (A − B) | **+0,0 poin persentase** |
| `primaryNbaAction` sama persis antar-arm | **7/8 (87,5%)** — satu-satunya beda: CUST-01062 (Deskcoll vs WA) |

**JAWABAN untuk "mana yang lebih bagus, dengan atau tanpa rule NBA di input
LLM": TIDAK ADA BEDA YANG TERUKUR.** Delta +0,0% jauh di bawah ambang
indikatif ±15pp yang dibekukan sebelum ada angka apa pun → **anchoring
TIDAK terbukti**. Rule NBA **aman dipertahankan** di payload produksi.
Bukti yang lebih kuat dari sekadar agree-rate: pada 7 dari 8 debitur, LLM
memberi rekomendasi channel PERSIS SAMA baik diberi tahu rekomendasi rule
engine atau tidak — menunjukkan LLM menyimpulkan aksi dari data mentahnya
sendiri (DPD, skor 4 model, riwayat pembayaran), bukan sekadar meniru field
`nbaRecommendation` yang disodorkan. Detail per-debitur: `reports/
ablation_nba_raw.json` dan `reports/ablation_nba.md`.

**⚠️ N=8 tetap kecil** — cukup untuk kesimpulan kualitatif yang jelas (delta
persis nol, bukan mendekati nol dari satu sisi), tapi uji McNemar berpasangan
formal untuk klaim signifikansi statistik belum dihitung (di luar scope
minimum TASK-E6). Menaikkan N (`--n 50`) akan memperkuat presisi estimasi,
kemungkinan besar tanpa mengubah arah kesimpulan.

---

## 6. Rekomendasi untuk sesi berikutnya (tidak dikerjakan sesi ini)

1. **Kuota/kredensial LLM — SEBAGIAN TERSELESAIKAN.** Key Gemini sudah
   diperbarui (bukan lagi 401) DAN model-nya diganti ke `gemini-3.5-flash`
   (bukan lagi 429) — panggilan sukses untuk mayoritas sampel, GLM judge juga
   sudah terprovisikan dan terverifikasi bekerja. **Yang masih tersisa**:
   N di seluruh tier (Tier 1: N=4-5, Tier 2: N=1, Tier 3: N=1-2, ablasi: N=8)
   masih kecil untuk klaim agregat/statistik formal. Naikkan N di
   `--limit`/`--n` kalau kuota masih bertahan pada sesi berikutnya — tidak
   ada pekerjaan kode tersisa, murni menjalankan ulang dengan N lebih besar.
2. **Investigasi gap §4a** — akurasi rule engine (32,2%) di bawah baseline
   naif (49,0%) terhadap oracle w/c layak ditelusuri: apakah karena definisi
   oracle 3-kelas di sini tidak identik dengan konstruk `apply_risk_
   segment()`, atau rule engine memang lemah pada dimensi ini secara nyata.
   AUC ML yang tinggi (§4b) menunjukkan sinyalnya ADA di data — pertanyaannya
   apakah rule engine memanfaatkannya dengan cara yang sejalan dengan oracle.
3. **Uji signifikansi formal** untuk ablation (McNemar) begitu N≥50 tercapai.

# CollectAI — Review Pasca-Presentasi: Performance, Day-to-Day Sync, Evaluasi AI Summary

> **Status:** disusun 2026-08-11. Per 2026-08-12: SELESAI seluruhnya KECUALI
> P7 (di luar scope sesi ini, butuh k6 + load test terpisah) — lihat Papan
> Status di bawah, `performance-report.md` (Area 1), dan
> `ai-reasoning-evaluation.md` (Area 3). **Catatan penting Area 3:** E5/E6
> code-complete + unit-tested, tapi API key Gemini di `.env` sesi ini
> mengembalikan HTTP 401 (kedaluwarsa/tidak valid) — sebagian angka Tier
> 2/3/4c dan seluruh ablation E6 belum terisi data nyata karenanya, lihat
> `ai-reasoning-evaluation.md` §keterbatasan untuk detail dan cara mengisinya
> begitu ada key valid.
> Dirancang supaya bisa dieksekusi kapan saja, oleh siapa saja, tanpa konteks
> percakapan. Semua rujukan `file:line` sudah diverifikasi lewat pembacaan kode
> langsung pada tanggal itu.

## Papan status

Tandai di sini setiap kali satu task selesai, supaya progres terlihat tanpa
membaca seluruh dokumen.

| ID | Task | Status |
|----|------|--------|
| E1 | Lengkapi skor model di payload | ✅ selesai |
| E2 | `nbaAgreement` dihitung di kode | ✅ selesai |
| E3 | `PROMPT_VERSION` → v2 + audit klaim prompt | ✅ selesai |
| E4 | Unit test ai_reasoning | ✅ selesai |
| S1 | Gate: determinisme seed faker | ✅ selesai — **temuan mengubah desain S2**, lihat detail |
| P1 | Instrumentasi timing | ✅ selesai (2026-08-12) |
| P3 | Jalur data volume besar (`COPY` + bulk-clone) | ✅ selesai (2026-08-12) |
| P2 | Profiling + audit query | ✅ selesai (2026-08-12) — **temuan #1 di luar dugaan awal, lihat detail** |
| P4 | Sweep baseline 5K→ceiling | ✅ selesai (2026-08-12) — ceiling SEBELUM fix P5: 100K, lihat P6 untuk ceiling sesudah |
| P5 | Rework: chunked + agregasi SQL | ✅ SEBAGIAN (2026-08-12) — 2 fix lebih besar dari rencana awal, item asli di-skip (alasan tertulis) |
| P6 | Sweep ulang + proyeksi 5 juta | ✅ selesai (2026-08-12) — lihat `performance-report.md` |
| S3 | Bersihkan kebocoran wall-clock | ✅ selesai (2026-08-12) — **ditemukan kebocoran KEDUA di `update_cbs()` yang tidak disebut baseline awal**, lihat detail |
| S2 | Staging → replay bertahap ke tabel live + rescoring asli | ✅ selesai (2026-08-12) — diverifikasi nyata: 130/426 kontrak berubah risk_segment, 418/426 dpd berubah, CBS berubah, 0 IntegrityError |
| S4 | Laporan pergerakan | ✅ selesai (2026-08-12) — matriks transisi BUKAN diagonal, lihat `reports/movement_2026-08.md` |
| E5 | Harness evaluasi Tier 1–4 | ✅ SEBAGIAN (2026-08-12) — Tier 1-3 code-complete+tested, **0 data nyata OK** (Gemini key 401); Tier 4 **selesai dengan angka nyata**, lihat `ai-reasoning-evaluation.md` |
| E6 | Ablation anchoring + keputusan | ✅ SEBAGIAN (2026-08-12) — kode+test selesai, **keputusan tidak bisa diambil** (0 pasangan nyata, Gemini key 401) |
| P7 | Load test k6 | ⬜ belum — di luar scope sesi ini |

## Cara memakai dokumen ini

- Setiap task punya ID (`P#` performance, `S#` sync, `E#` evaluasi), dan tiga
  bagian tetap: **Kenapa** (alasan, supaya tidak dikerjakan buta), **Ubah**
  (file konkret), **Selesai kalau** (kriteria objektif, bukan perasaan).
- Tandai progres langsung di dokumen ini dengan pola yang sudah dipakai repo:
  `✅ SELESAI (YYYY-MM-DD)` di belakang judul task.
- **Urutan wajib** hanya pada dependensi yang ditulis eksplisit di
  "Prasyarat". Selain itu bebas.
- Semua rujukan `file:line` di bawah sudah diverifikasi lewat pembacaan kode
  langsung, bukan asumsi. Kalau nomor barisnya sudah bergeser saat Anda
  mengerjakan, cari simbolnya — konteksnya tetap benar.

---

## Ringkasan keputusan

Sudah dikonfirmasi, tidak perlu dibuka ulang:

| # | Keputusan |
|---|---|
| 1 | Isu anchoring rule NBA **diukur lewat ablation A/B**, bukan langsung dihapus |
| 2 | Area Sync cukup **script + laporan**, tanpa UI baru |
| 3 | Evaluasi AI pakai **deterministic checks + LLM-as-judge + latent oracle faker** |
| 4 | Performance mencakup sweep volume + load test API + profiling **dan implementasi optimasi** |
| 5 | Load test pakai **k6**, bukan Locust (Locust dibatasi GIL → berisiko mengukur load generator, bukan server) |
| 6 | Sweep volume **5.000 → 5.000.000 customer**, dengan stop rule otomatis. Angka 5 juta akan berupa **proyeksi terukur**, bukan hasil pengukuran — hardware saat ini tidak sanggup (lihat "Batas hardware" di Area 1) |
| 7 | LLM-as-judge pakai **provider OpenAI-compatible (GLM/Zhipu)**, bukan Gemini kedua — judge beda keluarga model menghilangkan bias self-preference |
| 8 | **Tier 4 latent oracle dipertahankan** dan ikut dipresentasikan. Urutan penyajian: Tier 1 headline → Tier 4 akurasi → Tier 2 pendukung |

**Catatan terminologi yang wajib dijaga di laporan:** deterministic checks
mengukur *faithfulness* (setia pada data), LLM-judge mengukur *perceived
quality*. Keduanya **bukan akurasi**. Yang membuat kata *akurasi* sah dipakai
hanya latent oracle faker — dan bahkan itu adalah akurasi terhadap kebenaran
data **sintetis**: bukti bahwa sistem memulihkan struktur yang membangkitkan
data, bukan klaim performa dunia nyata. Jangan dikaburkan saat presentasi.

---

## Temuan awal terverifikasi (baseline — ini bagian yang mahal, jangan dicari ulang)

**Instrumentasi**
- **Nol timing di seluruh repo.** `daily_scoring.py` dan keempat `train_*.py`
  tidak punya `time`/`logging`/`perf_counter` — hanya `print()`.
- `logs/scoring_log.csv` mencatat `n_scored` tapi **tidak durasi**
  (writer: `daily_scoring.py:79-85`).
- `model_monitoring_log` punya AUC + `n_samples`, **tanpa kolom durasi**.
  Durasi dihitung di `weekly_mlops.py:549` tapi hanya di-`print`, tidak disimpan.
- Backend hanya punya `CORSMiddleware` (`main.py:95-101`) — tanpa request
  timing, tanpa `logging` sama sekali di seluruh `app/backend`.
- `SyncStep` (`app/backend/domain/models.py:293-299`) hanya punya
  `model_type`/`action`/`status` — tanpa waktu. State sync murni in-memory
  (`ai_intelligence_sync_service.py:91`), hilang saat restart.

**Skalabilitas**
- Semua pembacaan pipeline **unbounded**: `pd.read_sql("SELECT * FROM ...")`
  seluruh tabel ke pandas (`daily_scoring.py:98-109`, tiap `train_*.py:35-41`,
  plus `restructuring_runner.py`). Ini dinding yang sebenarnya.
- Semua penulisan lewat `to_sql` executemany tanpa `chunksize`, **bukan `COPY`**
  (`daily_scoring.py:58`, `:76`, `:129`; `faker/helpers/database.py:160-166`
  pakai `method='multi', chunksize=1000`).
- Rasio terukur pada N=2000: **2.918 kontrak / 28.209 payment / 61.470 interaksi**.
  Ekstrapolasi 1M customer ≈ 1,46M kontrak / 14M payment / 30M interaksi ≈ **45M baris**.
- Tidak ada tooling benchmark/load apa pun. Diperiksa: `app/backend/requirements.txt`
  (fastapi, pytest, pytest-cov), `app/machine-learning/requirements.txt`
  (pytest, pytest-cov), `app/frontend/package.json` (msw, oxlint, vite).

**Temporal / history**
- faker **sudah punya** `--customers` dan `--as-of`
  (`generate-faker-realistic.py:1089-1100`). `as_of` adalah **satu-satunya**
  sumber "hari ini" di generator (`:1108`); semua tanggal relatif padanya.
- faker **tidak bisa append** — `require_empty=True` menolak tabel berisi
  (`faker/helpers/database.py:148-155`) karena PK deterministik
  (`CUST-00001`, `PAY-0000001`). Jadi hanya truncate+insert dari nol.
- **`ai_intelligence_output` PK = `contract_no` saja** (`schema.sql:117`) →
  snapshot, bukan history. `_upsert_ai_output` DELETE-by-`scoring_date` lalu
  append (`daily_scoring.py:53-58`), sehingga dua tanggal **tidak bisa** hidup
  berdampingan (run kedua akan PK-violate).
- `customer_behavioral_standing` di-DELETE **seluruh tabel** tiap run
  (`daily_scoring.py:127-129`). PK `cust_id`.
- Yang genuinely per-tanggal: `scoring_labels` (`UNIQUE (contract_no, scoring_date)`),
  `shadow_scores`, `model_monitoring_log`, `scoring_feature_snapshot`.
- **Kesimpulan: pergerakan skor lintas hari tidak terekam di mana pun.**
- Kebocoran wall-clock (menerima `reference_date` tapi tetap pakai jam dinding):
  `daily_scoring.py:64`, `:180`, `:188`; `src/cbs_builder.py:114`;
  `weekly_mlops.py:169`; `retrain_strategies.py:142`.

**AI Reasoning**
- Payload (`ai_reasoning_payload.py`) mengirim **jawaban** rule engine —
  `nba_recommendation` + `nba_trigger` (`:174-177`), `nba_spread` (`:128`) —
  tapi dari 4 model **hanya `recovery_score`** yang dikirim (`:173`).
  `self_cure_probability` dan `ptp_success_probability` **tidak pernah dikirim**,
  padahal `available_models` (`:32-42`) memberi tahu LLM model itu ada.
  `AiScoringSnapshot` (`domain/models.py:127-140`) **sudah memuat keempatnya** —
  jadi ini murni tidak disalin, bukan tidak tersedia.
- **Tidak ada satu pun baris interaksi** dikirim ke LLM — hanya agregat CBS
  (`ptp_reliability_index`, `collection_sensitivity`).
- **`nbaAgreement` dinilai sendiri oleh LLM dan tidak pernah didefinisikan.**
  Kata itu **tidak muncul** di `_SYSTEM_INSTRUCTION_TEMPLATE`; model menebak
  artinya dari nama field (schema: `ai_reasoning_prompt.py:59`). Tidak ada kode
  yang membandingkan `primary_nba_action` vs `nba_spread`, sehingga output
  self-inconsistent lolos Pydantic sampai ke UI
  (`AiReasoningCard.tsx:196-204` merender banner saat `=== 'DIFFER'`).
- `compute_source_signature` (`ai_reasoning_payload.py:45-57`) hanya menghash
  `(contract_no, scoring_date)` — **perubahan DPD/OTS/pembayaran tidak
  membasikan cache** kecuali ada rescoring.
- **Nol test** untuk ai_reasoning. `app/backend/tests/` hanya `test_auth.py` +
  `test_smoke.py`; satu-satunya sentuhan adalah `test_smoke.py:521-530` yang
  mengecek bentuk blok Model Health.
- `--dump-latents` menulis `faker/_audit_latents.parquet` berisi per kontrak:
  `contract_no`, `cust_id`, `w`, `c`, `a_cut`, `shock_cut`, `p_label`, `y_pay`
  (`generate-faker-realistic.py:1147-1165`) — **tidak pernah masuk DB**.
  `w` = willingness (disiplin bayar), `c` = capacity (kemampuan melunasi),
  didefinisikan di `draw_customer_latents` (`:229-248`).
- `CHANNEL_RANK = {"WA":1,"Deskcoll":2,"Visit":3,"Somasi":4,"Pickup":5}`
  (`business_rules.py:27`); `apply_nba()` (`:69-146`) = 8 assignment berurutan
  last-write-wins + 4 override, **semuanya per-kontrak, tidak ada yang
  level-debitur**.

**Frontend**
- **Tidak ada library chart sama sekali** (`package.json`: hanya react,
  react-router-dom, @tanstack/react-query, ky, zod). Semua grafik hand-rolled
  div — mis. `DpdBucketChart.tsx:29-49`.
- Satu-satunya pola delta/before-after yang sudah ada:
  `RestructuringGroupDetailPage.tsx:112-142` (`trending_up`/`trending_down` +
  `text-success`/`text-error`).

---

## Peta task

| ID | Task | Prasyarat |
|----|------|-----------|
| **E1** | Lengkapi skor model di payload | — |
| **E2** | `nbaAgreement` dihitung di kode | — |
| **E3** | `PROMPT_VERSION` → v2 + audit klaim prompt | E1, E2 |
| **E4** | Unit test ai_reasoning | E1–E3 |
| **S1** | Gate: verifikasi determinisme seed faker | — |
| **P1** | Instrumentasi timing | — |
| **P3** | Jalur data volume besar (`COPY` + bulk-clone) | — |
| **P2** | Profiling + audit query | P1, P3 (butuh rung besar) |
| **P4** | Sweep baseline 5K→ceiling (angka "sebelum") | P1, P3 |
| **P5** | Rework wajib: chunked + agregasi SQL | P2, P4 |
| **P6** | Sweep ulang + model proyeksi ke 5 juta | P4, P5 |
| **S2** | Staging → replay bertahap ke tabel live + rescoring asli | S1, **S3** |
| **S3** | Bersihkan kebocoran wall-clock | — |
| **S4** | Laporan pergerakan | S2, S3 |
| **E5** | Harness evaluasi Tier 1–4 | E1–E4 |
| **E6** | Ablation anchoring + keputusan akhir | E5 |
| **P7** | Load test k6 | P4 (dataset), idealnya juga P5 |

Urutan yang disarankan:
**E1→E2→E3→E4 → S1 → P1 → P3 → P2 → P4 → P5 → P6 → S3 → S2 → S4 → E5 → E6 → P7**

- **E dulu**: tanpa E1–E2, apa pun yang diukur di E5/E6 mengukur sistem yang cacat.
- **S1 dini**: hasilnya menentukan desain S2 **dan** membatasi opsi P5 nomor 4.
- **P3 sebelum P2/P4**: profiling dan sweep sama-sama butuh rung besar, dan rung
  besar tidak bisa dimuat tanpa `COPY` + bulk-clone.
- **P5 setelah P4**: butuh angka "sebelum" untuk dibandingkan, dan butuh hasil P2
  untuk tahu mana yang layak dikerjakan lebih dulu.

---

# AREA 1 — Scalability & Performance

Dua sumbu berbeda yang sama-sama diminta reviewer: **volume data** (pipeline)
dan **concurrency request** (server). Jangan dicampur dalam satu angka.

**Target: 5.000 → 5.000.000 customer.**

## ⚠️ Batas hardware — dihitung di depan, bukan ditemukan di tengah jalan

Mesin kerja: **Mac14,2 (M2), 8 core, RAM 16 GB, disk bebas 14 GB.**

Ekstrapolasi dari rasio terukur di N=2000 (2.918 kontrak / 28.209 payment /
61.470 interaksi → 1,46 / 14,1 / 30,7 per customer):

| N customer | contract | payment | lkp_interaction | total baris |
|---|---|---|---|---|
| 5.000 | 7,3 rb | 70 rb | 154 rb | ≈236 rb |
| 100.000 | 146 rb | 1,41 jt | 3,07 jt | ≈4,7 jt |
| 1.000.000 | 1,46 jt | 14,1 jt | 30,7 jt | ≈47 jt |
| **5.000.000** | **7,3 jt** | **70,5 jt** | **153,7 jt** | **≈236 jt** |

Kebutuhan storage di 5 juta: heap ≈27 GB + index ≈11 GB + tabel derivatif ≈4 GB
= **≈42 GB**, dan build index butuh ruang temp/WAL → realistis **55–70 GB bebas**.

**Dua dinding, dan RAM jebol lebih dulu:**

1. **RAM (≈50–100 rb customer).** `daily_scoring` memuat `payment_history` +
   `lkp_interaction` utuh ke pandas (`:104-105`). Di 5 juta itu ≈45 GB hanya
   untuk load, di mesin 16 GB. **`COPY` dan column pruning tidak menolong di
   sini** — keduanya tidak mengurangi kebutuhan memuat data. Hanya chunked /
   agregasi sisi SQL (P5) yang menghilangkan dinding ini.
2. **Disk (≈500 rb – 1 jt customer).** 14 GB bebas vs kebutuhan 55–70 GB di
   5 juta — kurang 4–5 kali.

**Konsekuensi yang sudah disepakati:** angka 5 juta **tidak akan terukur di mesin
ini**. Strateginya: ukur ladder nyata sejauh hardware sanggup, lalu **proyeksikan**
ke 5 juta dengan model yang dinyatakan eksplisit (P6). Harness dibuat
hardware-agnostic, jadi kalau nanti tersedia server besar, script yang sama jalan
sampai 5 juta tanpa diubah. **Laporan wajib memisahkan tegas kolom TERUKUR dan
PROYEKSI** — mencampurnya adalah bentuk ketidakjujuran yang paling mudah
ditemukan reviewer.

## TASK-P1 — Instrumentasi timing ✅ SELESAI (2026-08-12)

**Hasil.** `src/perf.py` (context manager `stage_timer` + `new_run_id`) dibuat
dan dipasang di semua 9 stage `daily_scoring.py` dan ke-4 stage
(load/feature/train/register) tiap `train_*.py`. Diverifikasi nyata: run
`daily_scoring.py` dan `train_self_cure.py` di dataset 500 customer yang ada
menghasilkan baris per-stage di `logs/perf_runs.csv` (durasi + peak RSS +
rows). `SyncStep` (`domain/models.py`) dan `_set_step_status`
(`ai_intelligence_sync_service.py`) diberi `started_at`/`duration_s`,
diteruskan lewat `SyncStepSchema`, Zod `syncStepSchema`
(`startedAt`/`durationS`), fixture MSW, dan dirender di
`AiIntelligencePage.tsx` (`formatDurationSeconds`, `lib/format.ts`).
Middleware `X-Process-Time` + log request lambat (≥1s) ditambahkan di
`main.py`. Verifikasi: `pytest app/backend/tests/ -q` (68 lolos),
`pytest app/machine-learning/tests/ -q` (155 lolos — baseline paritas untuk
P5), `npm run lint && npm run build` hijau.

**Kenapa.** Saat ini nol. Tanpa ini tidak ada angka "processing time" untuk
dilaporkan, dan tidak ada cara membuktikan rework P5 benar-benar bekerja.

**Ubah.**
- **`app/machine-learning/src/perf.py`** (baru) — context manager
  `stage_timer(name, rows=None)`: durasi via `time.perf_counter()`, peak RSS via
  `resource.getrusage(RUSAGE_SELF).ru_maxrss` (**hati-hati: macOS mengembalikan
  bytes, Linux KB — normalisasi eksplisit**), jumlah baris. Akumulasi per run
  lalu append ke `logs/perf_runs.csv`: `run_id, n_customers, stage, duration_s,
  peak_rss_mb, rows, started_at`.
- Bungkus tiap fase `pipelines/daily_scoring.py` (langkah 1–9 sudah bernomor di
  `:98-197`) dan keempat `train_*.py` (load / feature / train / register).
- `SyncStep` (`app/backend/domain/models.py:293-299`) tambah
  `started_at`/`duration_s`, diisi di `_set_step_status`
  (`ai_intelligence_sync_service.py:251-257`). Ini langsung tampil di
  `AiIntelligencePage.tsx` — nilai demo tinggi ("training 42 detik") dengan
  biaya sangat kecil. Frontend: perlu update Zod `syncStatusResponseSchema`
  (`aiIntelligence.schema.ts:78-104`) + fixture MSW.
- Middleware request-timing di `app/backend/main.py` — header `X-Process-Time`
  + log request lambat.

**Selesai kalau.** Satu `daily_scoring.py` biasa menghasilkan baris per-stage di
`logs/perf_runs.csv`; UI Sync menampilkan durasi per step; `npm run lint && npm run build` hijau.

## TASK-P2 — Profiling & audit query ✅ SELESAI (2026-08-12)

**Hasil — dijalankan nyata pada 50.000 customer (bulk-clone, 69.210 kontrak,
690.430 payment, 1.497.570 lkp) via `perf/profile_scoring.py` (cProfile
membungkus `run_daily_scoring()`) + `perf/explain_queries.sql`.**

**⚠️ Temuan #1 — TIDAK ada di baseline awal, dan lebih besar dari yang
diduga.** Hotspot terbesar BUKAN `feature_engineering.py` seperti asumsi
awal, melainkan **`pipelines/restructuring_runner.py:256`** — 361 dari 590
detik cProfile (61%) habis di satu fungsi ini. Root cause presisi, bukan
sekadar "belum divektorisasi": baris 271
(`sibling_rows = merged[(merged["cust_id"] == row["cust_id"]) & ...]`)
memfilter ULANG seluruh dataframe `merged` (69.210 baris) di **DALAM**
loop `for _, row in merged.iterrows():` (`:256`) — ini **O(n²)**, bukan
O(n). Di 50 rb kontrak itu ~4,8 miliar perbandingan; di proyeksi 250 rb
kontrak (P4/P6) faktor n² sendirian membuatnya **~25× lebih lambat**, di luar
pertumbuhan linear tabel lain. Bukti di profil: `comp_method_OBJECT_ARRAY`
dipanggil 425.999× makan 283s tottime — persis skala O(n²) untuk n≈69 rb.
**Rekomendasi konkret (belum dieksekusi — di luar daftar item TASK-P5
semula, tapi dampaknya lebih besar dari semua item yang terdaftar disana):**
group `merged` per `cust_id` SEKALI sebelum loop (`dict` atau
`groupby` sekali), ganti pencarian sibling jadi lookup O(1). Parity gate yang
sama seperti P5 lain WAJIB berlaku (hasil assessment restrukturisasi harus
identik sebelum/sesudah).

**Temuan #2 — konfirmasi hipotesis awal.** `feature_engineering.py::
_compute_delay_trend` (`:349`) — dipanggil 48.550× (1 per customer, loop
Python di `compute_customer_features`), 126,8s cumulative. Ditambah 3
panggilan `.agg()` dengan lambda custom (`pandas/core/groupby/generic.py:318
_python_agg_general`) — 76,7s, agregasi TIDAK divektorisasi C
(`payment_rate`/`recovery_source_encoded`/dst di `compute_contract_features`).
Ini konfirmasi urutan prioritas TASK-P5 poin 1 sudah benar untuk
`daily_scoring.py`/`feature_engineering.py` — hanya bukan hotspot TERBESAR
di pipeline secara keseluruhan (lihat Temuan #1).

**Temuan #3 — EXPLAIN ANALYZE (backend, endpoint baca).** Query
`_CUSTOMER_LIST_BASE_CTE` (customer list default, filter "all") = 226ms,
2× `Seq Scan` penuh pada `contract_snapshot` (72.090 baris) dengan `Sort
Method: external merge Disk` (spill ke disk, 3MB+2.4MB) — ini query yang
paling terasa reviewer kalau dites lewat UI langsung. Dashboard DPD-bucket
cross-tab (14,7ms) juga `Parallel Seq Scan` pada `contract_snapshot`.
Sebaliknya, `get_customer_profile` (LATERAL join, fix outstanding
sebelumnya) sudah cepat (23,6ms, index scan) berkat PK lookup langsung per
`cust_id` — TIDAK butuh index baru. `pg_stat_user_indexes` menunjukkan
beberapa index ber-`idx_scan=0` (`idx_ai_output_cust`,
`idx_restructure_group_cust`, dll) — **catatan kejujuran:** ini kemungkinan
karena endpoint yang memakainya tidak tersentuh selama sesi profiling ini
(mis. fitur restrukturisasi/ai-reasoning detail), BUKAN bukti pasti index
itu tidak berguna secara global — jangan dihapus tanpa mengecek call-site
kodenya juga, bukan hanya `idx_scan`.

**File yang dibuat.** `perf/profile_scoring.py`, `perf/explain_queries.sql`,
hasil tersimpan di `perf/results/daily_scoring_20260812031341.pstats` dan
`perf/results/explain_50k_2026-08-12.txt`.

**Prasyarat.** P1.
**Kenapa.** Menentukan prioritas P5. Jangan mengoptimasi sebelum tahu hotspot
sebenarnya — urutan di P5 adalah hipotesis, bukan fakta.

**Ubah.**
- **`perf/profile_scoring.py`** (baru) — `cProfile` membungkus
  `run_daily_scoring()`, dump `.pstats` + top-N cumulative.
- **`perf/explain_queries.sql`** (baru) — `EXPLAIN (ANALYZE, BUFFERS)` pada
  query panas: `_CUSTOMER_LIST_BASE_CTE`, list contract, `dashboard/summary`,
  dan LATERAL join `get_customer_profile` (`customer_repository.py:257`).
  Plus audit: index tak terpakai (`pg_stat_user_indexes`), seq scan pada tabel
  besar (`pg_stat_user_tables`).

**Selesai kalau.** Ada daftar top-10 hotspot pipeline dan daftar query yang
seq-scan, keduanya tertulis di `performance-report.md`.

**Catatan.** Jalankan profiling pada rung yang **cukup besar untuk mewakili**
(mis. 50–100 rb), bukan pada 2 rb. Hotspot di dataset kecil sering didominasi
overhead startup dan menyesatkan prioritas P5.

## TASK-P3 — Jalur data volume besar (`COPY` + bulk-clone) ✅ SELESAI (2026-08-12)

**Hasil.** Write path `to_sql(method='multi', chunksize=1000)` diganti COPY
(`src/db_write.py::copy_dataframe` dipakai `daily_scoring.py` + `cbs_builder.py`;
helper sejenis di `faker/helpers/database.py`). Ditemukan & diperbaiki saat
verifikasi: parser literal teks COPY untuk kolom integer PostgreSQL menolak
`"37.0"` (beda dari `to_sql` lama yang lolos lewat cast numeric->bigint
psycopg2) — kolom float yang seluruh nilainya bulat sekarang ditulis tanpa
".0" (`_collapse_whole_number_floats`), aman karena nilai numeriknya tidak
berubah. `faker/bulk_clone.py` dibuat: generate populasi benih lewat fungsi
simulator ASLI (bukan reimplementasi, dimuat via `importlib` karena nama
filenya bertanda hubung), replikasi per blok dengan prefiks ID `PCxxxx-`
(karantina — lihat docstring modul) + jitter tanggal/nominal SERAGAM per
blok (bukan per-baris, supaya delay_days/rasio amortisasi tidak rusak — sama
prinsipnya dengan temuan whole-calendar-shift di S1), ditulis via COPY,
memori block dilepas (`del` + `gc.collect()`) tiap blok. Diverifikasi nyata:
3.000 customer (3 blok dari benih 1.000) — 0 baris yatim di
contract/payment/lkp, `_audit_latents.csv` lama otomatis diinvalidasi
(`.INVALIDATED`), dan **`daily_scoring.py` asli tanpa modifikasi berhasil
scoring 4.176 kontrak dari data ini**. `pytest app/machine-learning/tests/
-q` (155) dan `pytest app/backend/tests/ -q` (68) tetap hijau.

**Kenapa.** Dua hambatan menghalangi rung besar bahkan sebelum pipeline-nya
diuji: (a) tulis lewat `to_sql(method='multi', chunksize=1000)` terlalu lambat
untuk puluhan juta baris; (b) simulator faker adalah loop Python row-by-row
(`simulate_contract_paths`, `df_terms.iterrows()`, `:689-693`) — men-generate
5 juta customer lewat jalur itu makan puluhan jam.

**Ubah.**
1. **Write path → `COPY`.** `copy_expert` + buffer CSV menggantikan `to_sql` di
   `faker/helpers/database.py:160-166` dan `daily_scoring.py:58`, `:76`, `:129`.
   Ini **prasyarat semua rung besar**, bukan optimasi opsional.
2. **`faker/bulk_clone.py`** (baru) — jalur cepat **khusus uji performa**:
   generate populasi benih secara benar lewat simulator asli (mis. 50 rb), lalu
   replikasi dengan perturbasi (offset ID, jitter tanggal & nominal) + `COPY`
   sampai volume target. Menulis per blok lalu melepas memori, sehingga
   penggunaan RAM saat generate tetap konstan.

**⚠️ KARANTINA — aturan yang tidak boleh dilanggar.** Data hasil bulk-clone
**hanya sah untuk uji performa**. Setelah replikasi, latents-nya tidak lagi
berkorespondensi dengan barisnya, jadi dataset ini **TIDAK BOLEH** dipakai untuk
evaluasi akurasi Area 3 (Tier 4) maupun untuk melatih model yang angkanya
dilaporkan. Penegakan teknis, bukan sekadar niat:
- semua tabel/file hasil clone diberi prefiks `perfclone_` pada nama dataset
- `bulk_clone.py` **tidak pernah** menulis `_audit_latents.parquet`, dan
  meng-invalidasi (rename/hapus) file latents yang ada, supaya join yang salah
  jadi mustahil, bukan hanya tidak dianjurkan
- `performance-report.md` menyebut eksplisit rung mana yang memakai data clone

Kalau angka akurasi pernah dihitung dari data clone, angka itu tidak bermakna —
dan kalau itu sempat masuk slide lalu ditagih buktinya, kredibilitas seluruh
presentasi jatuh. Ini risiko terbesar di Area 1, dan satu-satunya penangkalnya
adalah pemisahan yang ditegakkan mesin.

**Selesai kalau.** 1 juta customer bisa dimuat ke DB dalam waktu yang wajar
(target indikatif <1 jam), dan tidak ada file latents yang berasal dari data clone.

## TASK-P4 — Sweep baseline (5K → sejauh hardware sanggup) ✅ SELESAI (2026-08-12)

**Hasil — `perf/benchmark_scale.py` dibuat & dijalankan nyata, ladder
5K/10K/25K/50K/100K.** Mesin: Mac14,2, 8 core, RAM 16GB, disk bebas ~14GB di
awal sweep.

| N customer | loader | generate | train (total 4) | daily_scoring | peak RSS train | DB size | bytes/row |
|---|---|---|---|---|---|---|---|
| 5.000 | faker asli | 10,6s | 52,1s | 16,6s | 437,9 MB | 88,2 MB | 380,3 |
| 10.000 | faker asli | 19,4s | 86,9s | 35,9s | 726,2 MB | 130,1 MB | 279,7 |
| 25.000 | faker asli | 48,7s | 195,0s | 129,8s | 1.417,0 MB | 239,5 MB | 206,3 |
| 50.000 | bulk-clone | 50,6s | 398,8s | 436,3s | 2.222,2 MB | 529,1 MB | 226,3 |
| **100.000** | bulk-clone | — | — | **TIMEOUT** (>1200s) | — | — | — |

**Titik patah: 100.000 customer, di stage `daily_scoring.py`, oleh WAKTU
(>1200s = 20 menit), BUKAN RAM atau disk.** Disk sisa saat itu masih ~9GB;
RSS terakhir terukur (50K) 2,2GB, jauh dari batas 16GB RAM. Sebab presisi
sudah diketahui dari TASK-P2: `restructuring_runner.py:256` melakukan
filter O(n²) pada tiap baris — waktu `daily_scoring` naik 16,6s→35,9s→
129,8s→436,3s untuk 5K→10K→25K→50K (rasio 50K/25K = 3,35× untuk 2× customer,
super-linear persis seperti pola O(n²) parsial), dan proyeksi linier dari
rasio itu ke 100K (~1.460s) **cocok dengan** stop rule 1200s yang benar-benar
terpicu. Ini pembuktian ladder terhadap temuan P2, bukan cuma ceiling
RAM/disk yang sudah diduga dari awal.

**bytes/row menurun seiring N** (380 -> 206) karena overhead index/WAL
fixed cost dibagi makin banyak baris — konsisten dipakai TASK-P6 untuk
proyeksi disk (pakai titik 25K/50K yang lebih stabil, bukan 5K yang masih
didominasi overhead kecil).

**Prasyarat.** P1 (instrumentasi), P3 (jalur data).

**Ladder:** `5K → 10K → 25K → 50K → 100K → 250K → 500K → 1M → 2,5M → 5M`

**Ubah.** **`perf/benchmark_scale.py`** (baru). Per rung:

1. reset DB via `scripts/reset-demo.sh --yes`
2. muat data: simulator asli (rung kecil, `--dump-latents`) **atau** bulk-clone
   (rung besar, ditandai `perfclone_`). `--no-excel` **wajib** di semua rung besar.
3. **keempat `train_*.py` — timing** ⚠️ **HARUS sebelum scoring**
4. `daily_scoring.py` — timing per stage
5. catat rows per tabel, `pg_total_relation_size` per tabel, total DB size,
   rows/detik per stage, **dan bytes/row per tabel**

**⚠️ Urutan train-sebelum-score itu wajib, bukan preferensi.** `reset-demo.sh`
menghapus artifact model, dan `daily_scoring.py:151` memanggil
`_resolve_champion_path()` yang melempar
`FileNotFoundError("Champion model belum tersedia")` (`:26-32`) kalau tidak ada
champion. Sebaliknya `train_*.py` **tidak** butuh output `daily_scoring` — tiap
`_load_source_data` hanya membaca tabel mentah (`contract_snapshot`,
`payment_history`, `lkp_interaction`, `customer_master`, mis.
`train_initial_model.py:34-40`) dan membangun CBS sendiri di memori lewat
`build_cbs`. Dependensinya satu arah: **data → train → score**.

**Kalibrasi bytes/row di rung kecil DULU.** Ukur `pg_total_relation_size` /
jumlah baris di 5K, 10K, 25K. Storage tumbuh linear dan sangat mudah diprediksi,
jadi tiga titik ini sudah cukup untuk memproyeksikan kebutuhan disk di 5 juta
**dengan angka nyata, bukan estimasi saya di atas**. Ini juga yang memberi tahu
kapan harus berhenti sebelum disk penuh — jangan sampai Postgres kehabisan ruang
di tengah run, karena recovery-nya jauh lebih mahal daripada mencegahnya.

**Stop rule** (`--max-stage-seconds`, `--max-rss-gb`, **`--min-free-disk-gb`**):
begitu satu stage melewati budget, OOM, atau sisa disk menyentuh ambang, ladder
**dihentikan rapi** dan titik patahnya dicatat. Yang dilaporkan adalah **ceiling
terukur + stage mana yang patah + sebabnya**. Ambang disk wajib ada — tanpa itu
run yang gagal bisa meninggalkan DB korup di disk penuh.

**Selesai kalau.** `perf/results/scale_sweep.csv` terisi; ladder berhenti rapi di
stop rule (bukan OOM-kill mentah, bukan disk penuh); titik patah + sebabnya tertulis.

## TASK-P5 — Rework wajib: chunked + agregasi sisi SQL ✅ SELESAI (item 1, sesi lanjutan)

**Hasil — item 1 ("chunked read", sebelumnya SENGAJA ditunda dengan alasan
"pekerjaan multi-hari, bukan yang aman diselesaikan tergesa") DIKERJAKAN di
sesi lanjutan setelah user eksplisit meminta menyelesaikan temuan yang
memakan waktu.**

`app/machine-learning/src/chunked_features.py` (baru) —
`compute_contract_features()`/`compute_customer_features()`
(`feature_engineering.py`) **TIDAK diubah kontraknya sama sekali** (57 test
lama tetap hijau + 10 test parity baru, `tests/test_features_chunked.py`).
Alih-alih memuat SELURUH `payment_history`/`lkp_interaction`, data dipecah
per batch `cust_id` (default 5.000, `FEATURE_CHUNK_BATCH_SIZE`), fungsi ASLI
dipanggil pada tiap batch, hasilnya digabung — benar secara matematis karena
SETIAP agregasi di kedua fungsi itu murni dalam lingkup satu `cust_id`, tidak
ada yang menyilang customer (dibuktikan lewat parity test, bukan
diasumsikan). Diwire ke `daily_scoring.py`, ke-4 `train_*.py`, dan
`cbs_builder.py::update_cbs()` (dipakai loop TASK-S2).

**3 bug nyata ditemukan & diperbaiki LEWAT parity gate (git stash + diff
byte-level pada data nyata), bukan lewat pembacaan kode:**
1. **Train/serve skew pre-existing** (BUKAN diperkenalkan sesi ini):
   `train_*.py` memanggil `compute_contract_features(..., df_customer=
   df_customer)` (pakai income level customer ASLI untuk
   `installment_to_income_ratio`), tapi `daily_scoring.py`/`update_cbs()`
   TIDAK PERNAH mengirim `df_customer` (selalu fallback flat 5.000.000) —
   sudah begitu SEBELUM ada chunking apa pun. `compute_features_chunked()`
   punya parameter `pass_customer_to_contract_features` yang WAJIB disamakan
   per caller (bukan ditebak) supaya tidak diam-diam "memperbaiki" skew ini.
   **Dicatat sebagai temuan, TIDAK diperbaiki** — mengubahnya butuh evaluasi
   retraining, di luar scope kerja RAM ini, dan mencampur 2 perubahan
   berisiko.
2. **Cabang global-vs-per-kontrak `recovery_source_encoded`**:
   `compute_contract_features()` mengisi `0` eksplisit kalau dataframe
   payment yang diberikan kosong TOTAL, tapi meninggalkan `NaN` (merge
   leftover) kalau tabel tidak kosong tapi SATU kontrak tertentu memang
   tidak punya payment — dua cabang kode yang sengaja berbeda. Chunking bisa
   membuat satu batch kebetulan kosong padahal tabel keseluruhan tidak —
   dikoreksi di `chunked_features.py` (cek `EXISTS` murah di level tabel),
   BUKAN di `feature_engineering.py`.
3. **Tie-break tidak stabil di `last_result_code`**: `sort_values(
   "action_date")` tanpa kunci sekunder memakai quicksort (default, TIDAK
   stabil) — untuk kontrak dengan >1 interaksi di tanggal yang SAMA,
   hasilnya bergantung pada isi/ukuran ARRAY yang disortir, bukan cuma
   urutan relatif baris yang tie. Ini bug determinisme PRE-EXISTING di
   `feature_engineering.py` sendiri (bisa beda hasil hanya karena batch size
   berbeda) — **diperbaiki di sumbernya** (`sort_values(["action_date",
   "lkp_id"])`, tie-break eksplisit) karena tidak mungkin direplikasi dari
   luar tanpa akses ke seluruh array yang disortir. 165 test ML tetap hijau.

**Paritas diverifikasi byte-level pada data nyata (1.500 customer/2.127
kontrak aktif)** via `git stash` + diff kolom-per-kolom (metodologi P5a/b):
`daily_scoring.py` (`ai_intelligence_output`, `scoring_feature_snapshot`,
`customer_behavioral_standing` — identik), ke-4 `train_*.py` (n, paid_rate,
AUC, seluruh top-5/10 feature importance — identik sampai 6 desimal),
`update_cbs()` (13 kolom × 1.500 baris — identik).

**Bonus: label window juga dipersempit lewat SQL** (`_load_label_payments()`
di tiap `train_*.py`) — `build_target_variable()` sendiri memfilter ulang ke
jendela yang PERSIS sama, jadi superset-safe (provably lossless), menghindari
load penuh `payment_history` kedua kalinya di fase labeling.

**Bonus temuan S3 (wall-clock KETIGA, di luar 2 yang sudah ditemukan
sebelumnya):** `_compute_delay_trend_batch()` (feature_engineering.py) selalu
memakai `pd.Timestamp.today()` untuk jendela `DELAY_TREND_WINDOW_MONTHS`,
TIDAK PERNAH menerima `reference_date` — bocor ke simulasi hari-per-hari
(TASK-S2) meski `daily_scoring.py --date` sudah benar. Diperbaiki: parameter
`reference_date` baru di `compute_customer_features()`/
`_compute_delay_trend_batch()` (default `None` → `datetime.now()`, perilaku
lama persis, tidak mempengaruhi caller yang tidak diubah), diwire di
`chunked_features.py`. Aman (default preserving) — tidak mempengaruhi
paritas byte-level di atas karena semua verifikasi dijalankan dengan
`reference_date = hari ini`, sama seperti wall-clock lama.

**Bukti "chunking bekerja" (RAM):** lihat `performance-report.md` §3f/§4 —
sweep ladder diukur ulang setelah perubahan ini.

**Prasyarat.** P2 (prioritas hotspot), P4 (angka "sebelum").

**Ini bukan optimasi opsional.** Tanpa ini ceiling berhenti di ≈50–100 rb
customer karena memuat tabel utuh ke pandas, dan target 5 juta tidak punya jalan
sama sekali — bahkan di server besar. Item lain di bawah adalah percepatan;
item 1 adalah yang mengubah ceiling.

**Aturan yang tidak bisa dinegosiasi — gerbang paritas.** Pada seed tetap,
keluaran skor `daily_scoring` harus **identik** sebelum/sesudah setiap langkah.
Perubahan yang menggeser skor model adalah **bug, bukan percepatan**, dan wajib
dibatalkan — bukan dirasionalisasi. Ukur ulang dengan harness P4 yang sama supaya
"sebelum" dan "sesudah" sebanding.

1. **Chunked read + agregasi sisi SQL** (mengubah ceiling; risiko tertinggi di
   seluruh plan). Dinding sebenarnya adalah `payment_history` +
   `lkp_interaction` utuh ke pandas (`daily_scoring.py:104-105`, dan tiap
   `train_*.py:35-41`). Dua tahap:
   (a) `chunksize=` + agregasi inkremental — aman, langsung menurunkan peak RSS;
   (b) dorong agregasi ke SQL untuk fitur yang memang hanya butuh agregat —
   hasil terbaik, memori jadi **konstan** terhadap jumlah customer.
   **Wajib** lolos `app/machine-learning/tests/test_features.py` plus diff
   golden-output pada seed tetap. Kalau paritas gagal, batalkan dan cari sebabnya
   — jangan menyesuaikan ekspektasi test agar lolos.
2. **Column pruning** (risiko sangat rendah). `SELECT *` → daftar kolom yang
   benar-benar dipakai. Tidak menyentuh logika sama sekali.
3. **Index yang hilang** — dari hasil P2. Kandidat: `payment_history(contract_no)`,
   `lkp_interaction(contract_no, action_date)`,
   `ai_intelligence_output(scoring_date)`. Tambahkan ke `schema.sql` root.
   **Catat trade-off-nya:** index menambah pemakaian disk, dan disk adalah
   dinding kedua — ukur dampaknya, jangan tambah index secara spekulatif.
4. **Paralelisasi generator faker** (**terakhir, atau ditunda**). Customer saling
   independen sehingga bisa di-`multiprocessing`. **Tapi determinisme seed adalah
   fondasi Area 2 (S1) — jangan dikorbankan demi kecepatan.** Kalau paralelisasi
   merusak reproduktibilitas, batalkan. Untuk kebutuhan volume, bulk-clone (P3)
   sudah menutup masalah ini tanpa menyentuh determinisme.

**Sekalian perbaiki** cacat atomicity: `_upsert_feature_snapshot` membuka **dua
transaksi terpisah** untuk DELETE dan INSERT (`daily_scoring.py:68` dan `:75`) —
crash di antaranya meninggalkan tabel kosong.

**Selesai kalau.** Peak RSS `daily_scoring` **tidak lagi tumbuh sebanding** jumlah
customer (bukti bahwa chunking bekerja); paritas skor terbukti; `pytest
app/machine-learning/tests/ -q` hijau (155 test).

## TASK-P6 — Sweep ulang + model proyeksi ke 5 juta ✅ SELESAI (2026-08-12), DIPERBARUI sesi lanjutan

**Hasil — lihat `performance-report.md` §4 untuk detail lengkap.** Ladder
dijalankan ulang DUA KALI: pertama dengan kode hasil P5a/P5b saja (CPU-fix,
5K→10K→25K→50K→100K→250K), lalu KEDUA setelah TASK-P5 item 1 (chunked read,
sesi lanjutan) selesai dikerjakan (100K→250K, akan berlanjut ke 500K/1M).
Ringkasan gabungan kedua putaran:

- **Putaran 1 (P5a/P5b, CPU-fix):** 100K yang sebelumnya TIMEOUT (>1200s)
  selesai dalam 209,1s. **250K jadi titik patah BARU**, bukan oleh O(n²)
  (sudah diperbaiki) melainkan waktu LOAD mentah `train_*.py`'s
  `pd.read_sql("SELECT *...")` (192,4s sendirian untuk 360rb baris) — inilah
  persis dinding yang jadi alasan TASK-P5 item 1 dikerjakan di sesi lanjutan.
  `daily_scoring` scaling ≈LINIER (power-law exponent 0,977, R²=0,998) — bukti
  kuantitatif fix O(n²) berhasil. Peak RSS training LINEAR terhadap N
  (R²=0,983), menyilang 16GB RAM di **N≈533.000** (angka LAMA, sudah
  digantikan — lihat poin berikut).
- **Putaran 2 (sesudah chunked read, sesi lanjutan):** rung 250K yang
  SEBELUMNYA timeout **kini selesai bersih** (`train_initial:load` turun dari
  192,4s → 4,1s, 47× lebih cepat) — dinding di atas SUDAH TIDAK ADA. Peak RSS
  training di 100K turun **−69%** (3.322,9→1.013,4 MB), peak RSS
  `daily_scoring` turun **−53%** (3.219,8→1.506,1 MB). Model RAM baru (fit
  2 titik, 100K+250K, secara eksplisit basis lebih lemah dari fit 5-titik
  putaran 1): titik silang 16GB bergeser dari **N≈533.000 → N≈1.671.000**
  (constraint sekarang `daily_scoring`/`restructuring_assessment`, bukan lagi
  training) — perbaikan **3,1×** pada ceiling RAM terukur.
- **Constraint pengikat di 5 juta: TETAP RAM**, sekarang di N≈1,67jt (naik
  dari 533rb), masih dilampaui jauh sebelum 5 juta (2,99× lebih jauh dari
  titik silang, turun dari 9,4× sebelumnya). **Rung 500K DICOBA dan GAGAL**
  karena TIMEOUT (900s, stage `feature`/`train` `train_initial_model.py`) —
  bukan RAM/disk, melainkan waktu training yang mulai membengkak
  super-linier di rentang 250K-500K (lihat `performance-report.md` §4a-lanjutan
  untuk detail). Ini dinding KEDUA yang berbeda dari RAM — 1M tidak dicoba
  karena 500K sudah gagal lebih dulu.

**Selesai kalau (verifikasi).** Tabel before/after ada (`performance-report.md`
§4a & §4a-lanjutan); tabel/model proyeksi dengan label TERUKUR/PROYEKSI
terpisah ada (§4b, §4c-lanjutan); bottleneck 5 juta (RAM, kini via
`daily_scoring`) disebut eksplisit (§4c-lanjutan); spesifikasi mesin dicatat
(§header).

**Prasyarat.** P4 (baseline), P5 (rework).

**Ubah.** Jalankan ulang ladder P4 dengan kode hasil P5 → angka "sesudah" dan
ceiling baru. Lalu bangun model proyeksi ke 5 juta.

**Syarat agar proyeksi bisa dipertanggungjawabkan** (kalau tidak, ini cuma
tebakan berbalut angka):
- Fit dari **minimal 3 rung di atas "knee"** — kalau kurvanya belum mapan,
  ekstrapolasi tidak bermakna. Storage boleh 3 rung kecil (linear, prediktabel);
  waktu/memori butuh lebih.
- **Nyatakan bentuk modelnya** (linear? n·log n karena groupby/sort?) beserta
  R²-nya. Jangan hanya menuliskan hasil akhirnya.
- **Nyatakan faktor ekstrapolasinya.** Dari 250 rb terukur ke 5 juta = **20×**.
  Itu rentang yang lebar dan wajib disebut, bukan disembunyikan.
- **Sebut constraint pengikat di 5 juta** (disk? RAM? waktu?) — proyeksi tanpa
  bottleneck yang teridentifikasi tidak bisa ditindaklanjuti.
- **⚠️ Batas regime.** Begitu kebutuhan memori melewati RAM fisik dan sistem
  mulai swap, kurvanya **patah diskontinu** — bukan melambat mulus. Proyeksi
  yang melintasi batas regime itu **tidak sah**. Tuliskan di mana batas itu
  berada, dan jangan mengekstrapolasi melewatinya seolah kurvanya mulus.

**Format laporan yang wajib** — kolom terpisah, tidak boleh dicampur:

| N | Status | Waktu generate | Waktu train | Waktu score | Peak RSS | DB size |
|---|---|---|---|---|---|---|
| 250.000 | **TERUKUR** | … | … | … | … | … |
| 5.000.000 | **PROYEKSI (20×, model n·log n, R²=…)** | … | … | … | … | … |

**Selesai kalau.** `performance-report.md` memuat tabel before/after **plus**
tabel proyeksi dengan label TERUKUR/PROYEKSI yang tidak mungkin tertukar,
bottleneck di 5 juta disebut eksplisit, dan spesifikasi mesin dicatat.

## TASK-P7 — Load test API (k6) ✅ SELESAI (2026-08-12, sesi lanjutan)

**Hasil — lihat `performance-report.md` §4d untuk detail lengkap.** Dua
sumbu diuji terpisah sesuai metodologi wajib: (1) jumlah worker (1 vs 4,
dataset kecil tetap 2rb customer) — hasilnya **kontra-intuitif**, 4 worker
LEBIH BURUK dari 1 worker (throughput 132→95 req/s, `dashboard_summary`
lolos threshold di 1 worker tapi GAGAL di 4 worker) — dihipotesiskan
karena tiap worker `uvicorn` punya connection pool SQLAlchemy sendiri
(bukan dibagi), sehingga 4 worker = hingga 60 koneksi bersaing ke satu
Postgres yang tidak ikut di-scale. (2) volume data (4 worker tetap,
2rb vs 100rb customer, KEDUANYA fully-scored) — hasilnya **KATASTROFIK**,
bukan cuma lambat: `dashboard_summary` p95 naik **134×** (685ms→92 detik),
`customer_list` **83×** (229ms→19 detik). Root cause DITEMUKAN, bukan
spekulasi: `list_customers_page()`
(`app/backend/repositories/customer_repository.py:231-254`) menjalankan
`_CUSTOMER_LIST_BASE_CTE` (agregasi `DISTINCT ON` + `GROUP BY` atas
SELURUH `contract_snapshot`/`ai_intelligence_output`, tidak dibatasi
LIMIT) **DUA KALI per request** (sekali untuk `count(*)` total, sekali
untuk baris halaman) — LIMIT/OFFSET diterapkan paling akhir, setelah
seluruh agregasi berat selesai. **Perbaikannya SENGAJA TIDAK dikerjakan
di sesi ini** — ini perubahan arsitektur (materialized view/pre-agregasi/
caching), bukan sesuatu yang aman diubah tergesa; direkomendasikan sebagai
prioritas TERTINGGI untuk pekerjaan lanjutan Area 1, di atas semua
temuan lain di laporan performa.

**Selesai kalau (verifikasi).** p95+error rate+RPS terlaporkan pada 2
konfigurasi worker (✅) dan pada dataset kecil vs besar (✅), threshold
pass/fail dilaporkan termasuk yang GAGAL, bukan disembunyikan (✅ —
`dashboard_summary`@4worker/kecil gagal, SEMUA endpoint@100rb gagal).

**Prasyarat.** P4 (butuh dataset). Idealnya dijalankan **dua kali**: sebelum & sesudah P5.

**Ubah.** **`perf/k6/read_endpoints.js`** (baru) — ramping-VU pada endpoint baca
panas: `dashboard/summary`, `customers` (list+paginasi), `customers/{id}`,
`contracts` (list), `contracts/{no}`. Pakai `thresholds`
(mis. `http_req_duration p(95)<500`, `http_req_failed<0.01`) supaya hasilnya
**pass/fail**, bukan sekadar angka. Install: `brew install k6`.

**Metodologi yang wajib ditulis di laporan** (kalau tidak, angkanya menyesatkan):
- Jalankan API dengan **beberapa worker** (`uvicorn --workers N`). Dengan satu
  worker Anda mengukur kapasitas satu proses Python dan akan **understate**.
- Jalankan tiap skenario pada dataset **kecil dan besar**, supaya efek
  concurrency terpisah dari efek volume data.
- Catat spesifikasi mesin. Angka tanpa konteks hardware tidak bisa dibandingkan.

**Selesai kalau.** p95 + error rate + RPS terlaporkan pada ≥2 konfigurasi worker,
dengan threshold pass/fail, di `performance-report.md`.

**Output Area 1:** `performance-report.md` (root repo).

---

# AREA 2 — Day-to-Day Sync (D+1 / D+7 / D+30)

Output: script + laporan. **Tanpa UI baru.**

## TASK-S1 — Gate: verifikasi determinisme seed ✅ SELESAI (2026-08-11)

**Kenapa.** Seluruh desain S2 bertumpu pada satu asumsi yang **belum terbukti**:
`--seed` sama + `--as-of` lebih maju menghasilkan customer & riwayat yang sama,
hanya dengan lebih banyak kejadian terungkap (right-censoring bergeser maju,
`generate-faker-realistic.py:494-497`). Kalau urutan konsumsi RNG bergeser,
asumsi ini salah dan S2 harus memakai desain lain.

**Cara uji.** Generate `--seed S --as-of D`, simpan `payment_history`. Generate
`--seed S --as-of D+7`. Bandingkan baris dengan tanggal ≤ D — harus **identik
baris-per-baris**.

**Kalau LOLOS** → pakai regenerate-per-hari di S2.
**Kalau GAGAL** → fallback: generate **sekali** di `--as-of D+30`, lalu bentuk
snapshot tiap hari dengan memfilter `payment_history`/`lkp_interaction` ke `≤ D`
dan menurunkan ulang `contract_snapshot` (dpd/ots/overdue) pada tanggal itu.
Sebagian mesinnya sudah ada — faker punya `--snapshot-as-of {cutoff,now}` yang
membangun snapshot pada dua titik berbeda (`:952-966`).

**Selesai kalau.** Hasil diff tertulis, dan desain S2 dipilih berdasarkan itu
(bukan diasumsikan).

---

**Hasil verifikasi (2026-08-11) — HASILNYA BUKAN "LOLOS" ATAU "GAGAL" SEPERTI
YANG DIANTISIPASI. Ada kemungkinan ketiga, dan itulah yang terjadi.**

Prosedur: `--customers 500 --seed 20260101 --as-of 2026-08-01 --reset` →
snapshot `payment_history` + `contract_snapshot` → regenerate dengan
`--as-of 2026-08-08` (D+7) → snapshot lagi → bandingkan baris-per-baris via
`payment_id`/`contract_no` (kedua run dijalankan dua kali untuk memastikan
hasilnya sendiri reproducible, bukan kebetulan run tunggal).

**Temuan, diverifikasi pada SELURUH baris (bukan sampel):**
- 6963/6963 `payment_id` identik persis di kedua run (tidak ada yang hilang,
  tidak ada yang baru terungkap).
- Kolom non-tanggal (`contract_no`, `payment_amount`, `pay_status`,
  `pay_method`, `delay_days`, `self_cure_flag`, `recovery_source`) **100%
  byte-identical** di kedua run.
- `due_date` dan `actual_pay_date`: **SELURUH 6963 baris bergeser tepat +7
  hari** — bukan 0 hari (frozen) atau bervariasi (RNG shift), tapi **konstan
  +7** di setiap baris.
- Pola NaN pada `actual_pay_date` (payment yang belum "terjadi") **0 baris
  berbeda** antar run — artinya bukan hanya tanggal yang shift, cutoff
  censoring-nya pun shift bersamaan, sinkron.
- `contract_snapshot` (739/739 kontrak): `dpd_current`, `cycle`, `prnc_ots`,
  `intr_ots`, `overdue_installment_count` **100% identik** — hanya
  `maturity_date` yang bergeser +7 hari, sama seperti `payment_history`.

**Kesimpulan mekanisme: `--as-of` melakukan TRANSLASI WAKTU SELURUH KALENDER
SIMULASI, bukan menggeser cutoff pengungkapan atas riwayat yang tetap.**
Ini karena `build_contract_terms()` menghitung tanggal origination MUNDUR dari
`as_of` (`as_of - N_bulan`), dan `dpd_cut`/`a_cut` (yang menentukan
`dpd_current`, `cycle`, OTS) dihitung dari `t_cut = as_of - LABEL_WINDOW_DAYS`
— sebuah **titik relatif tetap di kehidupan kontrak masing-masing**, bukan
titik kalender absolut. Menggeser `as_of` menggeser seluruh kalender secara
seragam, sehingga semua SELISIH (dpd, delay_days, cycle, ots) — yang menjadi
input skor risiko — **tidak pernah berubah**, berapa pun `--as-of` yang
dipilih, selama seed sama.

**⚠️ Konsekuensi kritis untuk S2 — ditemukan justru karena gate ini
dijalankan, bukan diasumsikan lolos.** "Regenerate-per-hari dengan `--as-of`
berbeda" (cabang LOLOS yang diantisipasi semula) **TIDAK AKAN menghasilkan
pergerakan skor apa pun**. `daily_scoring` yang dijalankan pada D0, D0+1,
D0+7, D0+30 (masing-masing hasil regenerate dengan `--as-of` berbeda, seed
sama) akan menghasilkan `dpd_current`/`risk_segment`/skor yang **identik
persis** di setiap tanggal — karena input yang dilihat scorer (dpd, ots,
cycle) tidak pernah berubah. Ini akan tepat memicu kegagalan yang sudah
diantisipasi di TASK-S4 ("kalau 100% diagonal, simulasi tidak benar-benar
memajukan apa pun") — bukan karena bug di S4, tapi karena S2 memakai mekanisme
yang salah.

**Keputusan desain S2 — REVISI (2026-08-11), menggantikan draft "recompute
read-only" yang sempat ditulis di atas.** Kebutuhan sebenarnya (dikonfirmasi
langsung oleh product owner) bukan cuma laporan — beliau ingin arus data
harian yang **sungguhan**: pembayaran/interaksi baru "masuk", status kontrak
terpengaruh, `daily_scoring.py` **asli** jalan ulang, dan aplikasi (Dashboard,
Customer Detail, Contract Detail) **otomatis** menunjukkan hasilnya — tanpa
script swap-tampilan terpisah. Ini sekaligus menjawab pertanyaan yang sempat
muncul ("kalau begini kita tidak bisa lihat perubahan di frontend?") — desain
di bawah membuat itu gratis, karena tabel yang diubah SETIAP HARI adalah tabel
yang sama yang dibaca aplikasi, bukan tabel arsip terpisah.

**Prinsipnya: generate SEKALI ke tempat penampungan (staging), lalu suapkan
bertahap ke tabel live sungguhan — bukan memanggil faker berulang dengan
`--as-of` berbeda (itu sudah dibuktikan gagal di atas).** Detail lengkap ada
di TASK-S2 di bawah, yang sudah ditulis ulang total mengikuti prinsip ini.

## TASK-S2 — Staging → replay bertahap ke tabel live + rescoring asli ✅ SELESAI (2026-08-12)

**Hasil — diverifikasi nyata pada 300 customer (444 kontrak), seed 20260101,
ladder D0=2026-08-01 → D0+7 → D0+30.** File baru: faker `--dump-schedule`
(flag baru di `generate-faker-realistic.py`, menulis `_installment_schedule.parquet`/
tabel `{prefix}installment_schedule` — due date PENUH per angsuran termasuk
yang belum dibayar, dihitung murni dari formula deterministik `_due_date()`,
TIDAK menyentuh latents `w`/`c`); `--table-prefix` (baru, dukung tulis ke
`stg_*` tanpa menyentuh tabel live — ditambahkan ke
`faker/helpers/database.py::reset_tables()`/`append_dataframes_to_postgres()`);
`app/machine-learning/src/contract_state.py` (`derive_contract_terms()` +
`recompute_contract_state()` — pure function, REUSE formula amortisasi asli
`assemble_contract_snapshot()` untuk `prnc_ots`/`intr_ots`, tapi SENGAJA
menyederhanakan `dpd_current` jadi "usia angsuran tertua yang belum lunas"
alih-alih formula noise generator, dan TIDAK mereplikasi bonus catch-up acak
saat pembayaran penuh — keduanya butuh akses ke latents tersembunyi yang
justru tidak boleh disentuh komponen ini); `scripts/simulate_days.py` (baru
— bootstrap D0 sekali + loop harian: ingest jendela tanggal dari staging →
`recompute_contract_state` → `update_cbs()` → TRUNCATE+score ulang
`daily_scoring.py --date <hari>` ASLI tanpa modifikasi).

**⚠️ Bug ditemukan & diperbaiki SELAMA verifikasi (bukan sebelum):
`_archive_current_ai_output()` sempat dipanggil di AWAL iterasi (sebelum
truncate) ALIH-ALIH di akhir setelah scoring** — akibatnya baris hari
TERAKHIR ladder (D0+30) tidak pernah tersalin ke `scoring_history` (arsip
duplikat D0 di awal iterasi berikutnya diam-diam di-skip oleh `ON CONFLICT DO
NOTHING`, bukan error, jadi tidak terlihat dari log). Diperbaiki: arsipkan
SETELAH scoring tiap hari, bukan sebelum truncate hari berikutnya — 3/3
tanggal ladder kini lengkap ter-arsip (diverifikasi ulang: `SELECT
snapshot_date, count(*) FROM scoring_history GROUP BY 1` = 426 baris di
ketiga tanggal).

**Diverifikasi memenuhi seluruh "Selesai kalau":**
- `dpd_current`/`risk_segment` BERUBAH nyata: 418/426 kontrak dpd berubah,
  130/426 (30,5%) risk_segment berubah D0→D0+30 (bukan beku seperti temuan S1).
- `customer_behavioral_standing.behavioral_grade`/`collection_sensitivity`
  JUGA berubah — dibuktikan `update_cbs()` benar-benar terpanggil ulang tiap
  hari, bukan cuma bootstrap D0 yang beku.
- Loop D0→D0+7→D0+30 berjalan **0 IntegrityError/unique violation**.
- `scoring_history` memuat 3 `snapshot_date` untuk 426 `contract_no` yang sama.
- `registry.json` membuktikan champion **identik** sepanjang 1 run simulasi
  (1 registrasi per model_type per run — training HANYA di bootstrap D0).

**Batas yang didokumentasikan, bukan bug tersembunyi:** jadwal cicilan
(`--dump-schedule`) generator ini secara arsitektur hanya mencakup due date
historis (≤ t_cut = as_of−30 hari) PLUS SATU angsuran tambahan di jendela
label 30 hari (`_due_date()` untuk `j=m+1`) — simulasi hari-per-hari HANYA
valid dalam jendela ≤30 hari dari D0, sesuai persis contoh ladder di dokumen
ini (`D0, D0+7, D0+30`). `simulate_days.py` mencetak peringatan otomatis kalau
horizon ladder >30 hari. `restructuring_runner` menumpuk tawaran per hari
tanpa membersihkan yang lama (didokumentasikan sebagai keputusan "biarkan
menumpuk", bukan dikerjakan).

`scripts/reset-demo.sh` diperbarui: `scoring_history` + 5 tabel `stg_*`
ditambahkan ke daftar `TABLES` (diverifikasi lewat run nyata `--yes`, 25
tabel ter-truncate bersih).

**⚠️ Perbaikan sesi lanjutan — pergerakan skor sekarang bisa DILIHAT DI WEB
antar-tanggal, bukan cuma di laporan akhir.** Sebelumnya `simulate_days.py`
hanya punya satu mode: jalankan SEMUA tanggal di `--dates` sekaligus lalu
berhenti — web hanya pernah menunjukkan tanggal TERAKHIR, tidak bisa
menunjukkan "sebelum vs sesudah" secara live. Ditambahkan 2 mode baru:

- **`--bootstrap-only [--horizon TGL]`** — jalankan bootstrap D0 saja lalu
  BERHENTI (staging tetap digenerate sampai `--horizon`, default D0+30, supaya
  transaksi masa depan tersedia untuk langkah berikutnya).
- **`--continue`** — majukan SATU tanggal (atau lebih) dari state yang SUDAH
  ADA di DB, tanpa TRUNCATE dan tanpa training ulang. Tanggal sebelumnya
  dibaca otomatis dari `MAX(scoring_history.snapshot_date)` — tidak perlu
  user mengetik ulang tanggal sebelumnya (dan tidak bisa salah sinkron).

**Diverifikasi ujung-ke-ujung lewat API sungguhan** (bukan query DB
langsung — mensimulasikan persis apa yang dilihat browser), kontrak
`CTR-00004-1`, `--customers 500 --seed 20260101`:

| | D0 (2026-09-01) | Setelah `--continue --dates 2026-09-30` |
|---|---|---|
| `GET /api/v1/contracts/CTR-00004-1` → `recovery_score` | 0,4037 | **0,5526** |
| `risk_segment` | Cannot Pay | **Can Pay** |
| `nba_recommendation` | Visit | **Deskcoll** |
| `dpd_current` | 66 | 95 |

`--continue` diverifikasi TIDAK men-training ulang (log run tidak menyebut
satu pun `pipelines/train_*.py`) dan TIDAK men-TRUNCATE tabel live selain
`ai_intelligence_output` (yang memang ditulis ulang tiap scoring, sesuai
desain S2 asli). `pytest` ML (168) dan backend (89) tetap hijau setelah
perubahan ini — modul yang disentuh (`scripts/simulate_days.py`) adalah
script CLI tanpa test unit, jadi verifikasinya lewat run nyata di atas.

**Prasyarat.** S1, **S3** (butuh flag `daily_scoring.py --date` yang dibuat
S3 — `daily_scoring.py` saat ini hanya menerima tanggal lewat positional
`sys.argv[1]`, `:221-225`; perintah `--date D0` di bawah TIDAK akan berfungsi
sebelum S3 selesai. **Kerjakan S3 dulu**, meski nomornya lebih besar — sudah
tercermin di "Urutan yang disarankan").

⚠️ **Rancangan di bawah adalah desain kedua**, menggantikan draft
"recompute-lalu-arsipkan-saja" yang sempat ditulis (masih terlihat di riwayat
S1 di atas sebagai catatan sejarah keputusan). Draft pertama hanya untuk
laporan; draft ini mensimulasikan **arus data produksi yang sesungguhnya**
(data masuk → rescoring → aplikasi berubah), sesuai kebutuhan yang dikonfirmasi
product owner.

**Kenapa tidak bisa langsung pakai faker biasa (ringkasan dari S1):** memanggil
faker berulang dengan `--as-of` berbeda menggeser SELURUH kalender secara
seragam — `dpd_current`/`cycle`/OTS tidak pernah berubah. Jadi faker hanya
dipakai **SEKALI** di sini (mengisi staging), dan pergerakan yang sesungguhnya
datang dari proses suap-bertahap + rescoring di bawah, bukan dari mekanisme
`--as-of` faker.

**Kerumitan baru yang wajib disadari sebelum mulai:** untuk tahu "berapa
angsuran yang telat" pada tanggal simulasi tertentu, sistem butuh **jadwal
cicilan penuh** (tanggal jatuh tempo tiap angsuran, termasuk yang belum
dibayar) — dan faker **tidak pernah menyimpan** ini ke mana pun. Yang
tersimpan di `payment_history` hanya pembayaran yang benar-benar terjadi
("angsuran yang tidak dibayar TIDAK muncul sebagai baris" — catatan yang sudah
ada di system instruction AI Reasoning, `:34`, berlaku juga di sini). Tanpa
jadwal penuh, tidak ada cara menghitung "berapa yang overdue" dari
`payment_history` saja begitu baris baru mulai disuap bertahap.

**Ubah.**

1. **Ekspos jadwal cicilan penuh** — tambahkan flag baru di
   `faker/generate-faker-realistic.py` (mis. `--dump-schedule`, mengikuti pola
   `--dump-latents` yang sudah ada) yang menulis
   `_installment_schedule.parquet` (atau CSV kalau `pyarrow` tidak terpasang —
   sudah terverifikasi tidak ada di venv saat ini, lihat catatan di TASK-S1):
   `contract_no, installment_no, due_date, installment_amount`. **Koreksi
   lokasi (audit 2026-08-11):** jadwal ini BUKAN dihasilkan `build_contract_terms()`
   — itu hanya terms agregat (tenor, installment amount, dst). Jadwal
   per-angsuran (variabel `schedule = []`, entry `{'j': j, 'due_date': due,
   ...}`) dibangun di dalam `_simulate_path()` (`generate-faker-realistic.py:439-548`,
   variabel lokal `schedule` di `:473-520`) dan dikembalikan sebagai
   `path['schedule']` (`:548`) — dipanggil dari `simulate_contract_paths()`
   (`:689`). Ini murni informasi yang SUDAH DIHITUNG di sana tapi sebelumnya
   tidak pernah ditulis ke luar (hanya `settled` entries yang jadi baris
   `payment_history`).
2. **Generate SEKALI ke staging, bukan ke tabel live.** Jalankan faker dengan
   `--as-of` = horizon terjauh yang ingin disimulasikan (mis. D0+30),
   `--dump-latents --dump-schedule --no-db` (opsi `--no-db` yang sudah ada —
   biar faker hanya menulis file, TIDAK menyentuh tabel live sama sekali).
   Muat file hasilnya ke tabel `stg_customer_master`, `stg_contract_snapshot`
   (state di horizon akhir), `stg_payment_history`, `stg_lkp_interaction`,
   `stg_installment_schedule` — skema sama seperti tabel live, cuma prefiks
   `stg_`, supaya query penyaringan tanggal di langkah berikut sederhana
   (`SELECT ... WHERE actual_pay_date <= :hari_ini`).
3. **`app/machine-learning/src/contract_state.py`** (baru) — fungsi murni
   `recompute_contract_state(contract_no, as_of_date, schedule_df, payment_history_df)`
   yang mencocokkan jadwal (`due_date <= as_of_date`) terhadap baris
   `payment_history` LIVE yang sudah ter-suap sampai hari itu, lalu menghitung
   `dpd_current` (usia angsuran tertua yang belum dibayar),
   `overdue_installment_count`, `cycle` (bucket dpd), `prnc_ots`/`intr_ots`
   (formula amortisasi — **REUSE**, jangan tulis ulang, logika yang sudah ada
   di `assemble_contract_snapshot()` `generate-faker-realistic.py:952-1000`).
   Fungsi ini TIDAK menyentuh DB — menerima DataFrame, mengembalikan
   DataFrame — supaya mudah ditest tanpa Postgres (pola sama seperti
   `build_payload()` di AI Reasoning).
4. **`scripts/simulate_days.py`** (baru):
   - **Bootstrap D0 (sekali):** dari staging, INSERT ke tabel live —
     `customer_master` (semua, sekali), `payment_history` dengan
     `actual_pay_date <= D0`, `lkp_interaction` dengan `action_date <= D0`.
     Panggil `recompute_contract_state()` untuk seluruh kontrak → tulis
     `contract_snapshot` live awal. **Latih keempat `train_*.py` dari state
     D0 ini — SEKALI.** Jalankan `daily_scoring.py --date D0` **ASLI, TIDAK
     DIMODIFIKASI** — ia membaca tabel live seperti proses produksi biasa dan
     menulis `ai_intelligence_output` seperti biasa (bootstrap CBS otomatis
     terjadi di run pertama ini karena `customer_behavioral_standing` masih
     kosong, `daily_scoring.py:115`). Salin hasilnya ke
     `scoring_history` (tabel arsip, dipakai TASK-S4 — perlu tetap ada karena
     tabel live akan tertimpa tiap hari berikutnya, jadi tanpa arsip histori
     hari-hari sebelumnya hilang begitu hari baru disimulasikan).
   - **Tiap hari berikutnya (loop — D0+1, D0+7, D0+30, dst), URUTAN WAJIB:**
     1. Dari staging, ambil baris `stg_payment_history`/`stg_lkp_interaction`
        yang tanggalnya jatuh di jendela (hari sebelumnya, hari ini] →
        **INSERT ke tabel live** (mensimulasikan "pembayaran/interaksi baru
        masuk hari ini" — persis seperti sinkronisasi data harian dari
        core-banking di produksi).
     2. Panggil `recompute_contract_state()` untuk kontrak yang terdampak →
        **UPDATE** `contract_snapshot` live.
     3. **Panggil `update_cbs(engine, reference_date=<hari ini>)`**
        (`src/cbs_builder.py:169` — **fungsi ini SUDAH ADA tapi TIDAK PERNAH
        dipanggil di seluruh repo saat ini**, cek dengan
        `grep -rn "update_cbs(" --include="*.py"`). **WAJIB dipanggil di sini**
        — tanpa ini, `customer_behavioral_standing` (behavioral_grade,
        collection_sensitivity, ptp_reliability_index, total_active_ots)
        HANYA terisi sekali di bootstrap D0 dan BEKU selamanya (`daily_scoring.py:115`
        hanya membangun ulang `if df_cbs.empty` — begitu D0 selesai, tabel
        tidak lagi kosong, jadi tidak pernah dibangun ulang). Ini gagal
        **sunyi, tanpa error** — simulasi tetap berjalan, tapi tabel yang
        namanya paling relevan dengan "perilaku debitur berubah" justru satu-
        satunya yang tidak pernah berubah. `update_cbs()` sengaja
        mempertahankan `b_list_status='Y'` yang sudah ada (`:194-196`), jadi
        aman dipanggil berulang.
     4. **Arsipkan `ai_intelligence_output` HARI SEBELUMNYA ke `scoring_history`,
        lalu `TRUNCATE ai_intelligence_output`, BARU jalankan
        `daily_scoring.py --date <hari ini>` ASLI lagi — TANPA training
        ulang** (champion dari D0 tetap dipakai, lewat
        `_resolve_champion_path()` yang sudah ada, `:151`).
        **Urutan TRUNCATE-sebelum-scoring ini WAJIB, bukan gaya penulisan** —
        `ai_intelligence_output` PK-nya `contract_no` saja (`schema.sql:117`),
        dan `_upsert_ai_output()` hanya `DELETE WHERE scoring_date = <hari
        ini>` (`daily_scoring.py:53-58`). Pada hari kedua, `scoring_date`
        hari ini belum ada baris apa pun (baris yang ada ber-`scoring_date`
        hari SEBELUMNYA) — jadi DELETE menghapus 0 baris, lalu INSERT
        `contract_no` yang sudah ada dari hari sebelumnya → **unique
        violation, proses berhenti di hari kedua**. `TRUNCATE` sebelum tiap
        run scoring menghindari ini sepenuhnya, dan aman karena hasilnya
        sudah diarsipkan ke `scoring_history` sesaat sebelumnya.
   - **Efek samping yang diinginkan:** setelah loop selesai, aplikasi (dibuka
     langsung, tanpa script tambahan) menunjukkan keadaan hari TERAKHIR yang
     disimulasikan — karena `contract_snapshot`/`ai_intelligence_output` LIVE
     memang benar-benar itu yang ditulis proses di atas.
   - **Perilaku yang belum diputuskan (dicatat, bukan diabaikan):**
     `restructuring_runner` (dipanggil dari dalam `daily_scoring.py`) meng-
     hapus baris lama berdasarkan `restructure_group_id` (yang memuat
     tanggal), BUKAN berdasarkan tanggal scoring — jadi tiap hari simulasi
     MENAMBAH tawaran restrukturisasi baru tanpa menimpa yang lama. Halaman
     Restructuring Approval akan menumpuk tawaran dari SELURUH tanggal
     simulasi tercampur. Putuskan sebelum demo: biarkan menumpuk (dan jelaskan
     kalau ditanya), atau tambahkan pembersihan per-hari di `simulate_days.py`.

**Syarat kebenaran, bukan detail teknis.** **Model dilatih SEKALI di D0 lalu
dibekukan** sepanjang loop — tanpa ini, pergerakan skor tidak bisa
diatribusikan ke perubahan perilaku debitur (data baru masuk), dan seluruh
demo kehilangan maknanya.

**Risiko yang wajib dijaga:** karena langkah ini benar-benar menulis ke tabel
live (bukan tabel arsip terpisah seperti draft pertama), simulasi ini akan
UNTUK SEMENTARA membuat data di aplikasi berisi tanggal-tanggal simulasi
(bisa di masa depan relatif hari nyata). **Jangan dijalankan di database yang
sedang dipakai untuk keperluan lain di waktu bersamaan.** Setelah sesi
demo/capture selesai, kembalikan ke data "hari ini" yang wajar — jalankan
ulang `reset-demo.sh` lalu generate data present-day biasa (lihat panduan
demo di bawah, sudah diperbarui mengikuti desain ini juga).

**`reset-demo.sh` WAJIB diperbarui sebagai bagian task ini.** Daftar
`TABLES` di sana hardcoded (`scripts/reset-demo.sh:60-69`) dan belum memuat
`scoring_history` maupun tabel `stg_*` yang baru — komentar di skrip itu
sendiri menyatakan *"daftar ini HARUS mencakup seluruh tabel di schema.sql"*.
Tanpa pembaruan ini, sisa data staging/arsip akan tertinggal setelah reset dan
mencemari sesi demo berikutnya.

**Selesai kalau.**
- Setelah loop selesai, membuka aplikasi (Customer Detail/Contract Detail
  untuk kontrak contoh) menunjukkan keadaan hari terakhir yang disimulasikan
  — TANPA script tambahan apa pun.
- `dpd_current`/`risk_segment` **benar-benar berubah** antar hari untuk
  sejumlah kontrak (bukan beku seperti temuan S1) — bukti
  `recompute_contract_state()` bekerja dan payment baru benar-benar berdampak.
- **`behavioral_grade`/`collection_sensitivity` di `customer_behavioral_standing`
  JUGA berubah antar hari** untuk sejumlah customer (bukti `update_cbs()`
  benar-benar terpanggil, bukan cuma bootstrap D0 yang beku).
- Loop D0→D0+1→D0+7 berjalan tanpa `IntegrityError`/unique violation di
  `ai_intelligence_output` (bukti urutan arsipkan→truncate→score benar).
- `scoring_history` memuat ≥2 `snapshot_date` untuk `contract_no` yang sama,
  dengan nilai yang berbeda.
- `registry.json` membuktikan champion identik sepanjang simulasi (tidak
  retrain di tengah loop).

## TASK-S3 — Bersihkan kebocoran wall-clock ✅ SELESAI (2026-08-12)

**Hasil.** `datetime.now()` diganti `pd.Timestamp(reference_date)`/`ref_date`
di 3 titik `daily_scoring.py` (`_upsert_feature_snapshot`'s `updated_at`,
step 8 `df_scored["updated_at"]`) dan `src/cbs_builder.py::build_cbs()`
(`update_timestamp`, parameter `reference_date=None` baru, default
`datetime.now()` kalau tidak diberikan — backward compatible untuk call-site
`train_*.py` yang tidak mensimulasikan tanggal). `daily_scoring.py` sekarang
punya flag `--date` yang benar (argparse, tetap kompatibel dengan pemanggilan
positional lama `daily_scoring.py 2026-09-01`).

**⚠️ Bug KEDUA ditemukan saat verifikasi — TIDAK ada di daftar baseline
awal.** `update_cbs()` (`src/cbs_builder.py:169`) menerima `reference_date`
dan meneruskannya ke `compute_contract_features()`/`compute_customer_
features()`, TAPI **tidak pernah meneruskannya ke `build_cbs()`** — jadi
`update_timestamp` di `customer_behavioral_standing` tetap bocor jam dinding
nyata meski parameter `reference_date` sudah "benar" dilewatkan di
permukaan. Ditemukan BUKAN lewat pembacaan kode, tapi lewat verifikasi data
nyata (TASK-S2): setelah 3 hari simulasi (2026-08-01/08/31), `SELECT DISTINCT
update_timestamp FROM customer_behavioral_standing` menunjukkan jam nyata
sesi ini (`2026-08-12 13:23:01`), bukan `2026-08-31`. Baris kode yang
diperbaiki: `cbs_new = build_cbs(custf, restructure_stats,
reference_date=reference_date)`. Setelah fix, ulang verifikasi: seluruh baris
`update_timestamp` = `2026-08-31 00:00:00` (tanggal simulasi terakhir),
`ai_intelligence_output.updated_at` dan `scoring_feature_snapshot.updated_at`
juga dikonfirmasi ikut tanggal simulasi masing-masing, bukan jam nyata.
**Ini bukti konkret kenapa TASK-S3 tidak boleh dianggap "hanya ganti 3
baris" — cek statis tidak cukup, verifikasi lewat data nyata menemukan
kebocoran yang lolos dari baseline awal.**

`pytest app/machine-learning/tests/ -q` tetap hijau (155 test) setelah
kedua perubahan.

**Kenapa.** Kalau `datetime.now()` bocor ke baris data bertanggal simulasi,
tanggalnya bohong dan laporan pergerakan tidak bisa dipercaya.

**Ubah.** Ganti `datetime.now()` dengan `reference_date` di
`daily_scoring.py:64`, `:180`, `:188`, dan `src/cbs_builder.py:114`.
Tambahkan flag `--date` yang benar di `daily_scoring.py` (sekarang hanya
positional `sys.argv[1]`, `:221-225`).

**Catat sebagai keterbatasan (di luar scope):** `weekly_mlops.py:169` dan
`retrain_strategies.py:142` menerima `reference_date` tapi masih memakai
wall-clock internal. Tidak mengganggu selama training dibekukan (S2).

**Selesai kalau.** Baris hasil `daily_scoring --date 2026-09-01` tidak memuat
timestamp hari ini di kolom mana pun yang seharusnya mengikuti tanggal simulasi.

## TASK-S4 — Laporan pergerakan ✅ SELESAI (2026-08-12)

**Hasil.** `scripts/movement_report.py` (baru) — baca `scoring_history`,
hasilkan `reports/movement_2026-08.md` + `.csv`. Dijalankan nyata pada data
S2 (426 kontrak, D0=2026-08-01 → Dn=2026-08-31):

- recovery_score naik 227 (53,3%), turun 197 (46,2%), tetap 2 (0,5%)
- risk_segment berubah 130/426 (30,5%), nba_recommendation berubah 120/426 (28,2%)
- **Matriks transisi risk_segment BUKAN diagonal**:
  Can Pay→Can Pay 74, Can Pay→Cannot Pay 16, Can Pay→Won't Pay 3;
  Cannot Pay→Can Pay 32, →Cannot Pay 43, →Won't Pay 25;
  Won't Pay→Can Pay 24, →Cannot Pay 30, →Won't Pay 179.
- Top-10 mover teridentifikasi (mis. CTR-00151-1: skor 0,118→0,864, Won't
  Pay→Can Pay, NBA Somasi→Deskcoll) — kasus nyata yang bisa langsung
  ditayangkan sebagai contoh "before → after" di demo.

Selesai kalau terpenuhi: matriks transisi menunjukkan pergerakan nyata,
bukan 100% diagonal.

**Prasyarat.** S2, S3.

**Ubah.** **`scripts/movement_report.py`** (baru) — baca `scoring_history`
(arsip yang ditulis TASK-S2 di setiap hari simulasi — WAJIB dibaca dari sini,
bukan dari tabel live, karena tabel live hanya menyimpan keadaan hari
terakhir), hasilkan CSV + markdown:
- delta per kontrak: skor naik/turun, DPD bergerak, NBA berubah
- **matriks transisi `risk_segment` D0 → Dn** — ini inti cerita demo
- agregat: berapa naik/turun/tetap, pergeseran distribusi segment & priority
- daftar **"top mover"** — kasus paling dramatis, yang akan ditayangkan

**Selesai kalau.** Matriks transisi menunjukkan pergerakan nyata. **Kalau
100% diagonal, simulasi tidak benar-benar memajukan apa pun** — itu kegagalan
yang harus ditelusuri, bukan hasil.

---

# Cara demo Area 2 (Day-to-Day Sync) — panduan praktis

⚠️ **Revisi (2026-08-11)** — bagian ini ditulis ulang setelah desain TASK-S2
diubah total (lihat "Keputusan desain S2 — REVISI" di TASK-S1). Sebelumnya
Area 2 direncanakan sebagai laporan saja, tapi product owner meminta arus
data harian yang sungguhan (data masuk → rescoring → aplikasi berubah). Desain
baru itu membuat visibilitas di aplikasi **gratis** — tidak perlu lagi script
"aktivasi tampilan" terpisah seperti draft sebelumnya.

✅ **Update (2026-08-12): S2-S4 sudah dikerjakan dan diverifikasi** (lihat
Hasil di masing-masing task di atas) — panduan di bawah sudah bisa langsung
dipakai, bukan lagi rencana untuk nanti. Verifikasi dijalankan pada 300
customer/444 kontrak (bukan skala penuh) — jalankan ulang dengan `--customers`
lebih besar untuk demo sungguhan kalau perlu populasi yang lebih meyakinkan
secara visual.

## Jawaban singkat: ya, bisa langsung dilihat di aplikasi asli

Karena TASK-S2 (desain baru) benar-benar menulis ke tabel yang dibaca
aplikasi (`payment_history`, `lkp_interaction`, `contract_snapshot`,
`ai_intelligence_output`) — bukan ke tabel arsip terpisah — begitu
`simulate_days.py` selesai memproses satu tanggal, **membuka Dashboard/
Customer Detail/Contract Detail langsung menunjukkan keadaan tanggal itu**.
Tidak ada script tambahan, tidak ada trik salin-tempel. Laporan
(`movement_report.py`) tetap dibuat sebagai pelengkap — untuk matriks transisi
dan daftar top-mover yang tidak praktis dilihat satu-satu lewat UI.

## Langkah praktis (siapkan sebelum hari-H, JANGAN live di depan audiens)

**Kenapa tidak boleh live:** `simulate_days.py` benar-benar menulis ke tabel
produksi-mirip yang dibaca aplikasi. Kalau sesuatu gagal di tengah jalan
(koneksi putus, urutan langkah salah), aplikasi bisa menunjukkan state
setengah-tersimulasi yang membingungkan — dan situasi itu muncul justru saat
semua orang menonton. Ini juga makan waktu nyata (regenerasi + training +
scoring berkali-kali), bukan sesuatu yang pantas ditunggu audiens.

1. **Tentukan ladder tanggal** yang mau diceritakan, mis. `D0=2026-08-01`,
   `D0+7`, `D0+30`. Jalankan (di database yang memang disiapkan untuk demo,
   BUKAN database kerja harian — lihat peringatan risiko di TASK-S2):
   ```bash
   python scripts/simulate_days.py --dates 2026-08-01,2026-08-08,2026-08-31
   ```
2. **Setelah setiap tanggal selesai diproses**, buka aplikasi dan
   **screenshot atau rekam screen** halaman yang relevan — Dashboard, Customer
   Detail untuk 1–2 debitur contoh yang dipilih sebelumnya (idealnya salah
   satu dari daftar "top mover"), Contract Detail, dan kartu AI Reasoning
   kalau debitur itu punya banyak kontrak. `simulate_days.py` akan lanjut ke
   tanggal berikutnya dan MENIMPA state ini, jadi capture-nya harus dilakukan
   SAAT itu, sebelum lanjut ke tanggal berikutnya.
3. Setelah seluruh ladder selesai, bangkitkan laporan pelengkap:
   ```bash
   python scripts/movement_report.py --out reports/movement_2026-08.md
   ```
4. **WAJIB dicek sebelum dipakai** — buka laporannya, pastikan matriks
   transisi TIDAK 100% diagonal (lihat "Selesai kalau" TASK-S4). Kalau
   diagonal semua, itu tanda `recompute_contract_state()` (TASK-S2) tidak
   benar-benar bekerja — jangan dipresentasikan, perbaiki dulu.
5. **Kembalikan database ke keadaan wajar** setelah sesi capture selesai —
   `reset-demo.sh` lalu generate data present-day biasa, supaya tidak ada
   sisa tanggal simulasi (yang bisa di masa depan relatif hari nyata) yang
   bocor ke bagian lain demo/kerja sehari-hari.

**Saat presentasi:** tampilkan rangkaian screenshot/rekaman "before → after"
per tanggal (bukan mengklik aplikasi live) — hasilnya sama meyakinkan secara
visual dengan nol risiko gagal di tengah acara. Lengkapi dengan laporan untuk
angka agregat (matriks transisi, daftar top-mover) yang tidak praktis
ditunjukkan satu-satu lewat screenshot.

**Naskah presentasi (pola yang sama dengan Tier 4 di Area 3 — jangan sebut
istilah internal seperti `scoring_history`, `staging`, atau `snapshot_date`):**

> "Ini adalah aplikasi yang sama, ditunjukkan pada tiga titik waktu berbeda
> untuk populasi debitur yang sama. Setiap hari, pembayaran dan interaksi
> baru masuk — persis seperti sinkronisasi harian dari sistem lain — dan
> mesin skor kami jalan ulang secara otomatis. Perhatikan debitur ini: pada
> hari pertama statusnya '[X]', tujuh hari kemudian setelah dua kali
> pembayaran, sistem otomatis memindahkannya ke '[Y]' dan mengubah
> rekomendasi tindakannya."

Lalu tunjukkan 3–5 baris dari daftar "top mover" di laporan sebagai penguat
angka agregat — audiens sudah melihat satu contoh nyata di layar, angka
agregat menunjukkan itu bukan kasus terisolasi.

## Checklist pra-presentasi

- [ ] Screenshot/rekaman sudah diambil untuk SETIAP tanggal ladder, SAAT
      tanggal itu aktif (bukan setelah lanjut ke tanggal berikutnya)
- [ ] Matriks transisi laporan **bukan** 100% diagonal (cek TASK-S4)
- [ ] Champion model identik di semua tanggal simulasi (cek `registry.json`,
      kalau berbeda berarti training ikut ter-trigger di tengah loop — bug)
- [ ] Angka top-mover sudah diverifikasi masuk akal (bukan customer dengan
      data korup/edge-case yang kebetulan ekstrem)
- [ ] **Database sudah dikembalikan ke state normal** sebelum hari-H (bukan
      tertinggal di tanggal simulasi terakhir) — supaya bagian presentasi
      lain (kalau ada demo fitur lain di aplikasi yang sama) tidak
      menunjukkan tanggal yang membingungkan
- [ ] Siapkan jawaban untuk "apakah ini data asli nasabah?" — TIDAK, ini data
      sintetis dari faker (sama seperti Tier 4 di Area 3, boleh dijelaskan
      dengan naskah yang sama kalau ditanya)

---

# AREA 3 — Evaluasi AI Summary + ablation anchoring

## TASK-E1 — Lengkapi angka di payload ✅ SELESAI (2026-08-11)

**Kenapa.** Keluhan tim ("AI tidak berfikir berdasarkan angka yang kita
berikan") **secara harfiah benar**: payload memberi output rule engine dengan
lengkap tapi hanya 1 dari 4 skor model. `AiScoringSnapshot`
(`domain/models.py:127-140`) sudah memuat keempatnya — murni tidak disalin.

**Ubah.** `_contract_block` (`ai_reasoning_payload.py:151-181`) tambahkan
`self_cure_probability`, `ptp_success_probability`, dan `roll_forward_risk`.
**Penting:** `roll_forward_risk` tersimpan **terbalik** (P(tidak bayar), lihat
komentar `:139-140`), jadi namai self-describing seperti yang sudah dilakukan di
rollup: `roll_forward_risk_prob_not_paying`. Pertimbangkan juga menambah fakta
interaksi mentah (RPC rate / hasil kontak terakhir) — saat ini **tidak ada satu
pun baris interaksi** yang dikirim.

**Selesai kalau.** Payload nyata satu customer multi-kontrak memuat keempat skor
per kontrak, dan `available_models` tidak lagi mengiklankan model yang skornya
tidak dikirim.

## TASK-E2 — `nbaAgreement` dihitung di kode ✅ SELESAI (2026-08-11)

**Kenapa.** Saat ini **dinilai sendiri oleh LLM** dan **tidak pernah
didefinisikan di prompt** — kata `nbaAgreement` tidak muncul di
`_SYSTEM_INSTRUCTION_TEMPLATE`; model menebak dari nama field. Tidak ada kode
yang memverifikasi. Sinyal DIFFER yang jadi nilai jual fitur ini karena itu
**tidak bisa difalsifikasi**. Ini cacat paling murah-diperbaiki dengan dampak
kredibilitas terbesar.

**Ubah.** Hapus `nbaAgreement` dari `build_response_schema()`
(`ai_reasoning_prompt.py:59`) dan dari `schemas/ai_reasoning.py:46`. Hitung di
`ai_reasoning_service.py` dengan membandingkan `primary_nba_action` terhadap
`nba_spread`. Kolom DB (`ai_reasoning_output.nba_agreement`) dan frontend
(`AiReasoningCard.tsx:196-204`) **tidak berubah**.

**Selesai kalau.** `nbaAgreement` tidak lagi ada di schema yang dikirim ke
Gemini, dan nilai tersimpan selalu cocok dengan perbandingan yang dihitung ulang
dari data.

## TASK-E3 — `PROMPT_VERSION` → v2 + audit klaim prompt ✅ SELESAI (2026-08-11)

**Prasyarat.** E1, E2.

**Ubah.**
- Naikkan `PROMPT_VERSION` ke `"v2"` (`ai_reasoning_prompt.py:15`). Karena versi
  ikut jadi cache key (`UNIQUE (cust_id, source_signature, prompt_version)`),
  baris v1 **tetap tersimpan** dan bisa dibandingkan langsung dengan v2 — bonus
  gratis untuk laporan E5.
- **Audit klaim usang.** Instruction menyatakan rule engine "tidak pernah
  menghasilkan Pickup" (`:35`). Setelah perbaikan `historical_default_count`
  (Fase 0 terdahulu), cabang Pickup (`business_rules.py:110-113`) kemungkinan
  sudah hidup. **Verifikasi dengan query nyata**
  (`SELECT nba_recommendation, count(*) FROM ai_intelligence_output GROUP BY 1`).
  Kalau Pickup > 0, kalimat itu **bohong kepada model** dan wajib diperbaiki.
- Sekalian definisikan semantik AGREE/DIFFER secara eksplisit di tempat barunya
  (kode), karena selama ini tidak pernah didefinisikan di mana pun.

**Selesai kalau.** Tidak ada pernyataan di system instruction yang bertentangan
dengan perilaku rule engine yang terverifikasi lewat query.

**Hasil verifikasi (2026-08-11).** Regenerasi 500 customer (`--seed 20260101`) →
train 4 model dari nol → `daily_scoring.py` → `SELECT nba_recommendation,
count(*) FROM ai_intelligence_output GROUP BY 1`: **Somasi 211, WA 197, Visit
150, Deskcoll 143, Pickup 10** (711 kontrak). Klaim lama **terbukti salah**
(1,4% kontrak menghasilkan Pickup) — teks system instruction, response schema,
dan `ai-reasoning-prompt-spec.md` §2/§4/§5 sudah diperbaiki.

## TASK-E4 — Unit test ai_reasoning ✅ SELESAI (2026-08-11)

**Prasyarat.** E1–E3.
**Kenapa.** Saat ini **nol** test. Semua perubahan E1–E3 menyentuh logika yang
tidak terlindungi sama sekali.

**Ubah.** `app/backend/tests/test_ai_reasoning.py` (baru) — test untuk
`build_payload` (termasuk flag `include_rule_nba` dari E6),
`compute_source_signature`, perhitungan agreement (E2), dan jalur fallback
(`_build_fallback_or_failed`, `ai_reasoning_service.py:153-188`).

**Selesai kalau.** `pytest app/backend/tests/ -q` hijau.
**⚠️ Ingat polusi yang sudah dikenal:** suite ini selalu mengubah
`model_governance_config.cbs_weights` description jadi `"d"` dan menyisakan satu
baris `model_governance_audit_log` dengan `performed_by='test.smoke.governance'`.
Pulihkan lewat psql setiap selesai.

**Hasil (2026-08-11).** 12 test baru ditambahkan — TIDAK ada test untuk
`include_rule_nba` (parameter itu belum ada, menunggu E6; ditandai di
docstring file test supaya tidak terlupa). `pytest app/backend/tests/ -q` →
68 passed (56 lama + 12 baru). Polusi governance dipulihkan lewat psql.

## TASK-E5 — Harness evaluasi Tier 1–4 ✅ SEBAGIAN (2026-08-12)

**Hasil — lihat `ai-reasoning-evaluation.md` untuk laporan lengkap.**
Ringkasan: tabel `ai_reasoning_evaluation` (schema.sql, FK ke
`ai_reasoning_output.id`, `UNIQUE(ai_reasoning_output_id, evaluator_version)`
supaya bisa dievaluasi ulang beberapa versi evaluator); `services/
ai_reasoning_eval.py` (Tier 1-3, fungsi murni dict-in-dict-out, 19 unit test
baru); `services/llm_client.py` (Protocol `LlmClient` diekstrak dari
`GeminiClient` TANPA mengubahnya — duck typing, `pytest -q` tetap hijau);
`services/openai_compat_client.py` (klien GLM/OpenAI-compatible generik);
config judge_* baru (`core/config.py` + `.env.example`, default
`judge_enabled=false`); `scripts/run_ai_reasoning_eval.py` (orchestrator
Tier 1-3, generate ULANG via `AiReasoningService.generate(force=True)`
supaya payload yang dievaluasi PERSIS payload yang dilihat LLM, menghindari
staleness); `scripts/evaluate_tier4_oracle.py` (Tier 4, murni analisis data
tanpa LLM).

**Tier 4 SELESAI dengan angka nyata** (dataset bersih 1.500 customer/2.127
kontrak aktif, terpisah dari data uji S2 di atas — S2's `contract_state.py`
yang disederhanakan TERBUKTI merusak fidelitas fitur ML untuk tujuan Tier 4,
ditemukan lewat AUC pertama yang anehnya rendah 0,489, root-cause ke data
campuran, diperbaiki dengan regenerasi dataset bersih via faker biasa + train
+ score, TANPA `simulate_days.py`): run-match latents↔DB bersih (0 baris
yatim), AUC(recovery_score, y_pay) = **0,9144** (kalibrasi sangat baik),
akurasi rule engine vs oracle 32,2% (**di bawah baseline naif 49,0%** —
dilaporkan apa adanya, bukan disembunyikan).

**⚠️ Tier 1-3 dan Tier 4-bagian-3 (AI Summary vs oracle) TIDAK punya data
nyata sesi ini** — API key Gemini di `.env` mengembalikan HTTP 401
(diverifikasi manual: panggilan `GeminiClient.generate()` langsung juga
gagal 401, bukan bug kode). Seluruh output yang di-generate ulang jatuh ke
status FALLBACK (rule-based template), bukan OK. Kode dan test tetap
selesai dan divalidasi lewat jalur FALLBACK (0 crash, 0 IntegrityError,
tersimpan bersih ke `ai_reasoning_evaluation`).

**Bug kecil ditemukan & diperbaiki saat validasi:** `check_agreement_
consistency` awalnya menandai SEMUA baris FALLBACK sebagai "tidak konsisten"
(`nba_agreement` tersimpan None dibandingkan dengan hasil hitung ulang yang
non-None) — padahal FALLBACK secara desain tidak pernah mengisi
`nba_agreement` (bukan bug E2, itu murni belum applicable). Diperbaiki di
driver script: `nba_spread` dikirim kosong ke fungsi cek untuk status selain
OK, supaya None dibandingkan None (konsisten), bukan None vs "AGREE"/"DIFFER".

**Prasyarat.** E1–E4.

**Ubah.**
- **Tabel `ai_reasoning_evaluation`** (baru) di `schema.sql` root, FK ke
  `ai_reasoning_output.id`, dengan `evaluator_version`. **Kenapa tabel baru
  bukan kolom tambahan:** `ai_reasoning_output` punya
  `UNIQUE (cust_id, source_signature, prompt_version)` → satu baris per output;
  tabel terpisah memungkinkan **re-evaluasi output yang sama oleh beberapa versi
  evaluator**, yang kolom tambahan tidak bisa.
- **`app/backend/services/ai_reasoning_eval.py`** (baru).

**Tier 1 — deterministic checks (tanpa LLM, jalankan pada 100% output).**
- *numeric grounding*: tiap angka yang dikutip `summary` /
  `customerTreatmentStrategy` / `keyFactors` harus ada di payload (toleransi
  pembulatan & format Rupiah) → **unsupported-claim rate**
- *integritas kontrak*: `perContractFocus[].contractNo` ⊆
  `analyzed_contract_nos` **dan** menutup semuanya → deteksi kontrak halusinasi
- *konsistensi agreement*: nilai tersimpan cocok dengan perbandingan sebenarnya
- *monotonisitas urgensi* terhadap DPD, validitas enum, bahasa, batas panjang

**Tier 2 — LLM-as-judge, provider OpenAI-compatible (GLM).**

Judge memakai **keluarga model berbeda** dari generator, supaya tidak ada bias
self-preference (model cenderung menyukai output dari keluarganya sendiri).

- **Ekstrak protocol** `LlmClient` dengan satu method
  `generate(system_instruction, payload, response_schema) -> LlmResult`.
  Signature `GeminiClient.generate()` (`gemini_client.py:55`) **sudah persis
  bentuk itu**, jadi ini ekstraksi murni tanpa mengubah perilaku. Klien
  di-inject lewat constructor (`build_gemini_client()` `:197-208`), jadi titik
  sambungnya sudah ada.
- **`app/backend/services/openai_compat_client.py`** (baru) — klien
  `/chat/completions`. **Satu klien ini menjangkau GLM/Zhipu, DeepSeek, Qwen,
  OpenRouter, sampai Ollama lokal** dengan hanya mengganti base URL + model,
  karena semuanya berbagi bentuk API yang sama.
- **Config** (`core/config.py`, ikuti pola `list[str]` yang sudah ada pada
  `cors_allow_origins` `:33` dan `google_ai_studio_api_keys`):
  `judge_api_base_url: str`, `judge_api_keys: list[str]`, `judge_model: str`,
  `judge_timeout_seconds: float`, `judge_enabled: bool = False`.
  Tambahkan stanza ke `.env.example`.
- **⚠️ Penegakan JSON lebih lemah dari Gemini.** Gemini punya `responseSchema`
  yang benar-benar memaksa bentuk; endpoint OpenAI-compatible paling banter
  `response_format: {type: "json_object"}` dan dukungan `json_schema` tidak
  seragam antar provider. Karena itu **lapisan re-validasi Pydantic wajib
  dipertahankan** — pola yang sudah dipakai generator
  (`GeminiReasoningOutputSchema.model_validate`,
  `ai_reasoning_service.py:125`). Judge yang gagal parse dihitung sebagai
  *judge failure*, **jangan** dibiarkan jadi skor 0 — itu akan mencemari rata-rata.
- **Rubrik 1–5:** faithfulness ke data, actionability, konsistensi internal,
  apakah strategi benar-benar mengikuti `keyFactors`.
- **Kalibrasi tanpa label manusia:** silangkan skor judge dengan hasil Tier 1.
  Judge yang memberi nilai tinggi pada output yang Tier 1 tandai berhalusinasi
  adalah judge yang **miscalibrated**. Laporkan apa adanya — ini pengganti
  parsial golden set manusia, bukan penggantinya yang utuh.

**✅ Tier 2 (GLM) DIUJI KONEKTIVITAS-nya (2026-08-12, sesi lanjutan) — setelah
user menambahkan `JUDGE_API_KEYS` nyata.** `run_tier2_judge()` dipanggil
LANGSUNG (bukan lewat `run_ai_reasoning_eval.py`, karena itu butuh generate
Gemini FRESH dulu — lihat blocker Gemini di bawah) dengan payload REAL dari
`CUST-00001` di DB (dibangun via `build_payload()` sungguhan) dan dua record
"ai_output" buatan tangan untuk menguji DUA UJUNG:

| Record uji | Isi | Skor judge (`glm-5.2`, via `https://api.z.ai/api/coding/paas/v4`) |
|---|---|---|
| **Grounded** — semua klaim cocok payload nyata (recovery_score 0,8353, DPD 0, NBA=WA) | jujur | faithfulness=**5**, actionability=**4**, internal_consistency=**5**, key_factors_alignment=**5** |
| **Fabricated** — sengaja mengarang kontrak (`CTR-99999-9`, tidak ada di payload), DPD 187 hari (payload nyata: 0), rekomendasi Somasi bertentangan dengan data | sengaja buruk | faithfulness=**1**, actionability=**1**, internal_consistency=**1**, key_factors_alignment=**1** |

**Kesimpulan yang bisa dipertanggungjawabkan:** integrasi GLM judge BEKERJA
end-to-end (HTTP call nyata, response terparse valid lolos
`_JudgeScoreSchema` Pydantic) DAN **judge-nya diskriminatif** — bukan asal
kasih skor tinggi ke apa saja (5/5/5/5 vs 1/1/1/1 untuk dua kasus ekstrem
yang jelas beda kualitasnya). **Ini BUKAN evaluasi Tier 2 produksi
sungguhan** — kedua "ai_output" di atas ditulis tangan (bukan hasil generate
Gemini nyata), karena kuota Gemini masih 429 (lihat TASK-E6 di bawah, blocker
yang sama). Yang terbukti di sini adalah **mekanisme judge-nya bisa dipakai
begitu ada output Gemini nyata untuk dinilai** — bukan skor kualitas AI
Reasoning produksi yang sesungguhnya, yang tetap menunggu kuota Gemini.

**Tier 3 — self-consistency.** Panggil payload sama K=3 kali (`force=True`),
ukur variansi `primaryNbaAction`.

**Tier 4 — latent oracle (ground truth asli).** Satu-satunya jalur yang membuat
kata *akurasi* sah. Sumber: `faker/_audit_latents.parquet` (`--dump-latents`),
berisi `w`, `c`, `p_label`, `y_pay` per kontrak — tidak pernah masuk DB.
- **Turunkan segmen oracle dari (w, c).** `w` = willingness, `c` = capacity
  (`draw_customer_latents:229-248`). Pemetaan: `w` rendah + `c` tinggi →
  **Won't Pay** (mampu tapi tidak mau); `w` tinggi + `c` rendah →
  **Cannot Pay**; keduanya tinggi → **Can Pay / Self-cure**; keduanya rendah →
  kasus terburuk.
  **⚠️ Ambang ditetapkan sekali di depan lalu DIBEKUKAN.** Menyetel ambang
  sampai hasilnya terlihat bagus membatalkan seluruh nilai pengukuran ini.
  Tulis ambang yang dipakai di laporan.
- **Agregasi ke level debitur** — latent per-kontrak, AI Summary per-debitur;
  pakai kontrak terburuk, konsisten dengan aturan prompt "urgensi mengikuti
  kontrak terburuk".
- **Tiga pengukuran yang terbuka:**
  1. *Akurasi rule engine* — `risk_segment` dari `apply_risk_segment` vs segmen
     oracle → confusion matrix + recall per kelas
  2. *Kalibrasi model ML* — `recovery_score` vs `p_label`/`y_pay` → AUC dan
     kurva kalibrasi terhadap label **sebenarnya**, bukan label berisik
  3. *Akurasi AI Summary* — `primaryNbaAction` vs aksi oracle
- **Perbandingan tiga arah oracle vs rule engine vs LLM** — ini grafik utama
  presentasi: memperlihatkan di kasus mana LLM mengungguli rule engine dan
  sebaliknya, diukur terhadap kebenaran, bukan opini.
- **Prasyarat operasional:** run faker yang dipakai harus `--dump-latents`, dan
  seed-nya dicatat bersama hasilnya. Karena faker truncate-and-regenerate,
  latents dan isi DB harus berasal dari **run yang sama** — kalau tidak,
  join-nya membandingkan dua dunia berbeda.

**Selesai kalau.** Tier 1 jalan pada seluruh baris `ai_reasoning_output` tanpa
error; `_audit_latents.parquet` ter-join penuh ke `contract_no` **tanpa baris
yatim di kedua sisi**; confusion matrix oracle-vs-rule dan oracle-vs-LLM
keduanya terisi dan bisa dibaca berdampingan.

## TASK-E6 — Ablation anchoring + keputusan akhir ✅ SELESAI (2026-08-12) — keputusan diambil dengan N=8 real, McNemar formal belum dihitung

**Hasil — lihat `ai-reasoning-evaluation.md` §5.** `include_rule_nba: bool =
True` ditambahkan ke `build_payload()` (+ diteruskan ke `_contract_block`/
`_portfolio_rollup_block`) — saat `False`, `nba_recommendation`/`nba_trigger`/
`nba_spread` dihilangkan total dari payload. 2 unit test baru. **Sengaja
TIDAK di-thread ke `AiReasoningService.generate()`** — kalau diteruskan
sampai sana, hasil ablation arm B akan tersimpan ke `ai_reasoning_output`
dengan cache key sama seperti output produksi, mencampur populasi yang harus
terpisah. `scripts/ablation_nba.py` (baru) memanggil `build_payload()` +
`GeminiClient.generate()` LANGSUNG per arm, bypass `AiReasoningService`
sepenuhnya — tidak menyentuh cache/DB produksi maupun
`ai_reasoning_daily_call_limit`.

**Diverifikasi jalan** (`python scripts/ablation_nba.py --n 3`): menangani
kegagalan API pada kedua arm dengan benar, mencetak status per debitur, dan
keluar bersih dengan pesan jelas saat 0 pasangan valid — bukan crash diam-diam.

**⚠️ Percobaan ULANG (2026-08-12, sesi lanjutan, setelah GLM judge
ditambahkan) — MASIH TIDAK BISA diambil keputusannya, blocker BERBEDA dari
sebelumnya.** Key Gemini di `.env` **bukan lagi 401** (sudah diperbaiki di
sesi sebelumnya) — sekarang **429 quota exceeded**, diverifikasi ulang
LANGSUNG (bukan asumsi) dengan panggilan `GeminiClient.generate()` manual
detik sebelum menjalankan ablation:
```
ERROR TYPE: GeminiError
ERROR: Gemini quota exceeded (429)
```
`python scripts/ablation_nba.py --n 3` dijalankan lagi: **ke-3 sampel gagal
di KEDUA arm** (`arm A ok=False, arm B ok=False`) dengan alasan yang sama.
**0 pasangan arm A/B nyata TERKUMPUL DI KEDUA KESEMPATAN** (sesi 401
sebelumnya, sesi 429 ini) — dua kegagalan berbeda sebab, sama akibatnya.

**Yang BISA disampaikan jujur soal "mana yang lebih bagus, dengan atau
tanpa rule NBA di input LLM":**
- **Belum ada jawaban berbasis data** — bukan "tidak konklusif" (istilah itu
  butuh N≥1 pasangan nyata untuk dipakai), tapi **N=0, benar-benar belum
  terukur**. Jangan menyimpulkan salah satu arah dari 0 data.
- Ambang keputusan SUDAH dibekukan di kode sejak sebelum percobaan pertama
  (delta ≥15pp → anchoring terbukti/buang rule NBA, ≤−15pp → pola tak
  terduga, di antaranya → tidak konklusif) — begitu kuota Gemini tersedia,
  jalankan `python scripts/ablation_nba.py --n 50` SEKALI dan laporkan
  angka apa pun yang keluar, tanpa menyetel ulang ambang setelah melihat hasil.
- **Keputusan operasional saat ini (bukan keputusan berbasis-bukti):** rule
  NBA **dipertahankan** di payload produksi karena mengubah default tanpa
  data adalah keputusan yang SAMA tidak berdasarnya dengan membuangnya tanpa
  data — status quo dipilih bukan karena terbukti benar, murni karena belum
  ada alasan terukur untuk mengubahnya.
- **Yang terverifikasi bekerja sambil menunggu kuota**: seluruh pipa ablation
  (sampling debitur, dua-arm payload, parse+validasi respons, kalkulasi
  delta, penulisan keputusan otomatis ke markdown) sudah terbukti jalan
  bersih pada kegagalan API — begitu Gemini API punya kuota (tunggu reset
  harian, atau tambah/ganti key di `GOOGLE_AI_STUDIO_API_KEYS`), tinggal
  jalankan `--n 50`, tidak ada pekerjaan kode tersisa.

**✅✅ HASIL NYATA AKHIRNYA DIPEROLEH (2026-08-12, percobaan ke-3, setelah
user mengganti MODEL Gemini ke `gemini-3.5-flash`).** Bukan lagi 401 atau
429 — panggilan sukses. `python scripts/ablation_nba.py --n 10 --seed 42`:

| | Nilai |
|---|---|
| N pasangan valid | **8** (dari target 10; 2 dilewati karena satu arm gagal) |
| Arm A (dengan rule NBA) — agree rate vs rule | **87,5%** (7/8) |
| Arm B (TANPA rule NBA) — agree rate vs rule | **87,5%** (7/8) |
| Delta (A − B) | **+0,0 poin persentase** |
| Distribusi aksi Arm A | Deskcoll=3, WA=4, Somasi=1 |
| Distribusi aksi Arm B | Deskcoll=2, WA=5, Somasi=1 |
| `primaryNbaAction` SAMA PERSIS antar arm | **7/8 (87,5%)** — hanya CUST-01062 berbeda (Deskcoll vs WA), lihat `reports/ablation_nba_raw.json` |

**Keputusan (mengikuti ambang yang dibekukan sebelum ada angka apa pun):**
delta +0,0% jauh di bawah ambang indikatif ±15pp → **"Tidak konklusif /
anchoring TIDAK terbukti"**. Rule NBA **AMAN dipertahankan** di payload
produksi — bukan cuma karena tidak terbukti menjangkar LLM, tapi karena
pada 7/8 kasus LLM memberi rekomendasi PERSIS SAMA baik diberitahu rule
NBA atau tidak, mengindikasikan LLM menyimpulkan hal yang sama dari data
mentahnya sendiri (DPD, skor model, riwayat bayar), bukan sekadar
membeo field `nbaRecommendation` yang diberikan.

**⚠️ Kejujuran statistik — N=8 kecil, jangan diklaim signifikan secara
formal.** Arah dan besar delta (nol, bukan mendekati nol dari sisi lain)
cukup jelas untuk kesimpulan kualitatif ini, tapi uji McNemar berpasangan
formal belum dihitung (di luar scope minimum TASK-E6). Menaikkan N akan
memperkuat, tidak mengubah arah — kecuali data lebih besar menunjukkan
sebaliknya, yang harus dilaporkan apa adanya kalau terjadi.

**Prasyarat.** E5.

**Ubah.**
- Tambah parameter `include_rule_nba: bool = True` pada `build_payload()`
  (`ai_reasoning_payload.py:184`) — juga perlu diteruskan ke
  `_contract_block` dan `_portfolio_rollup_block`. Saat `False`,
  `nba_recommendation`, `nba_trigger`, dan `nba_spread` **tidak disertakan**.
- **`scripts/ablation_nba.py`** (baru) — sampel N customer (mulai **N=50**),
  tiap customer dua arm: **A** dengan rule NBA, **B** tanpa. Bandingkan:
  - **tingkat kesamaan `primaryNbaAction` terhadap rule NBA di tiap arm — ini
    ukuran anchoring-nya**
  - distribusi `primaryNbaAction`
  - skor Tier 1 (apakah arm B benar-benar lebih membumi pada angka)

**Biaya.** ±2 panggilan generate + 1 judge per customer → N=50 ≈ 150 panggilan.
Perhatikan `ai_reasoning_daily_call_limit` (default 300) dan rotasi multi-key
yang sudah ada di `GeminiClient`.

**Kejujuran statistik.** Laporkan hitungan dan proporsi apa adanya.
**Jangan mengklaim signifikansi statistik pada N=50.** Kalau ingin klaim kuat,
naikkan N dan katakan berapa.

**Keputusan akhir diambil dari angka ini, bukan dari opini:** kalau arm A jauh
lebih sering setuju dengan rule dibanding arm B → **anchoring terbukti**, rule
NBA dibuang dari payload dan agreement tetap dihitung di kode (E2 sudah
menyiapkan jalannya). Kalau tidak berbeda → rule NBA aman dipertahankan dan
justru berguna untuk rekonsiliasi. **Tulis keputusannya eksplisit**, termasuk
kalau hasilnya tidak konklusif.

**Output Area 3:** `ai-reasoning-evaluation.md` (root repo) — metode, metrik,
hasil, keputusan. Rujuk `ai-reasoning-prompt-spec.md` yang sudah memuat
prompt/payload/response schema; jangan diulang.

---

# Cara menjelaskan Tier 4 ke audiens (naskah siap pakai)

Ditulis karena Tier 4 adalah bagian yang paling kuat **dan** paling mudah
disalahpahami. Aturan utama: **jangan pernah menyebut "latent oracle", "variabel
laten", `w`, `c`, atau "ground truth sintetis"** di depan audiens. Itu istilah
internal. Pakai bahasa kejadian sehari-hari.

## Naskah utama (±30 detik)

> "Pertanyaan yang paling wajar muncul: bagaimana kita tahu penilaian AI ini
> benar?
>
> Di data produksi, kita sebenarnya tidak pernah benar-benar tahu — kita hanya
> bisa menunggu enam bulan dan melihat siapa yang akhirnya gagal bayar.
>
> Tapi data demo ini kami yang membuat. Dan saat membuatnya, setiap debitur kami
> beri dua sifat: seberapa disiplin dia membayar, dan seberapa mampu dia
> membayar. Kedua angka itu tidak pernah kami masukkan ke database — sistem
> hanya melihat riwayat transaksi, sama seperti kondisi produksi.
>
> Artinya kami punya kunci jawaban. Jadi kami bisa menguji satu hal yang di
> produksi tidak mungkin diuji: dari riwayat transaksi saja, apakah sistem
> berhasil menemukan sifat asli debiturnya?"

## Analogi (pakai kalau ada yang masih mengernyit)

> "Seperti menguji dokter dengan pasien simulasi. Kami yang menentukan
> penyakitnya; dokter hanya diberi gejalanya. Kalau diagnosisnya tepat, itu
> bukan kebetulan."

Analogi ini dipilih karena memetakan persis ke domain: gejala → riwayat
transaksi, penyakit → risk segment, diagnosis → skor & rekomendasi.

## Grafik yang ditampilkan

Satu grafik, tiga batang, satu sumbu (% ketepatan terhadap kunci jawaban):

```
Rule engine (aturan bisnis saja)   ██████████░░░░░░  __%
AI Reasoning (LLM)                 ██████████████░░  __%
```

Jangan tampilkan confusion matrix di slide utama — simpan di lampiran untuk
sesi tanya jawab. Matrix menjawab pertanyaan yang belum ditanyakan.

## Kalimat pengunci (paling penting)

Kalau hanya satu kalimat yang boleh diingat audiens, ini:

> "Nilai absolutnya bisa diperdebatkan. Yang tidak bisa diperdebatkan adalah
> perbandingannya — rule engine dan AI diuji dengan kunci jawaban yang sama
> persis. Kalau kunci jawabannya pun dianggap belum sempurna, ketidaksempurnaan
> itu berlaku sama untuk keduanya."

Ini membuat klaim Anda tahan kritik: seorang skeptis boleh menyerang kualitas
kunci jawaban, tapi serangan itu tidak membatalkan **perbandingannya**, dan
perbandingan itulah isi klaim Anda.

## Antisipasi pertanyaan sulit

**"Tapi ini data buatan, bukan data nyata."**
> "Benar — dan justru itu syarat pengujian ini bisa dilakukan sama sekali. Di
> data nyata tidak ada kunci jawaban; kita baru tahu berbulan-bulan kemudian.
> Yang kami ukur di sini bukan 'seberapa akurat di dunia nyata', tapi 'apakah
> metodenya mampu menemukan pola yang memang ada di sana'. Kalau di data yang
> polanya kami tahu pasti saja sistem gagal menemukannya, tidak ada alasan
> berharap ia berhasil di data nyata. Ini uji kelayakan minimum, bukan klaim
> performa produksi."

Ini pembalikan yang jujur: mengubah "bukti lemah" menjadi "prasyarat yang
memang harus dilewati". Jangan berlebihan — akui batasnya, lalu jelaskan
kenapa batas itu tetap bermakna.

**"Bagaimana kalau datanya dibuat supaya sistem gampang menang?"**
> "Itu risiko yang nyata, dan kami menguncinya di tiga titik. Pertama, hubungan
> antara sifat tersembunyi dan data yang terlihat sengaja dibuat lemah —
> korelasinya sekitar 0,17 — supaya sistem harus benar-benar bekerja, bukan
> membaca jawaban yang sudah tertulis. Kedua, ambang penilaian ditetapkan
> sebelum hasil dilihat dan tidak pernah diubah setelahnya. Ketiga, ada
> validator terpisah yang khusus memastikan tidak ada fitur yang membocorkan
> jawaban."

Ketiga klaim itu terverifikasi di kode: R²≈0.17 didokumentasikan di
`draw_customer_latents` (`generate-faker-realistic.py:235-237`), pembekuan
ambang adalah aturan eksplisit di TASK-E5, dan validator itu
`faker/validate_leakage.py`. **Jangan pakai kalimat ini kalau salah satunya
belum benar-benar dijalankan.**

**"Kenapa tidak memakai penilaian ahli/kolektor senior saja?"**
> "Itu memang yang paling ideal, dan tetap kami rekomendasikan sebagai langkah
> berikutnya. Tapi penilaian manusia juga sebuah opini — dua kolektor senior
> bisa berbeda pendapat pada kasus yang sama. Kunci jawaban ini punya satu
> keunggulan yang tidak dimiliki penilaian manusia: tidak ambigu, dan bisa
> diskalakan ke ribuan kasus sekaligus. Keduanya saling melengkapi."

**"Berapa angka yang dianggap bagus?"**
> Jangan jawab dengan angka absolut. Arahkan ke perbandingan: rule engine vs AI
> pada kunci jawaban yang sama. Itu perbandingan apel-ke-apel, dan itulah
> klaimnya.

## Urutan penyajian di slide

1. **Tier 1 sebagai headline** — paling tahan uji karena tidak menuntut
   kepercayaan pada model apa pun. Contoh kalimat:
   *"Dari 200 output, sistem tidak sekali pun mengarang nomor kontrak, dan
   0,5% mengutip angka yang tidak ada di input."* Ini langsung menjawab
   pertanyaan yang paling sering muncul — "apa dia berhalusinasi?"
2. **Tier 4 untuk klaim akurasi** — naskah di atas.
3. **Tier 3 kalau ada waktu** — mudah dijelaskan:
   *"Pertanyaan yang sama kami ajukan tiga kali; jawabannya konsisten."*
4. **Tier 2 sebagai pendukung, bukan tumpuan.** Sebutkan judge-nya keluarga
   model berbeda, karena itu satu-satunya hal yang membuatnya bernilai.
   **Jangan** menjadikan ini headline: *"AI lain menilai AI kami bagus"* adalah
   posisi paling lemah di depan audiens skeptis.

---

## Verifikasi menyeluruh

**Area 1**
- [x] `logs/perf_runs.csv` terisi per stage setelah satu `daily_scoring` biasa
- [x] bytes/row terukur di 5K/10K/25K/50K/100K, dan proyeksi disk ke 5 juta
      memakai angka itu (linear fit R²=0,997) — bukan estimasi kasar
- [x] **Karantina bulk-clone**: `_audit_latents.csv` lama diinvalidasi
      (`.INVALIDATED`) otomatis oleh `bulk_clone.py`; rung mana yang memakai
      clone disebut eksplisit di `performance-report.md` §1
- [x] Ladder berhenti rapi di stop rule — P4: timeout 100K (waktu, bukan
      RAM/disk); P6: timeout 250K (waktu, sebab berbeda — lihat §4a laporan).
      Bukan OOM-kill mentah, bukan disk penuh di kedua kasus
- [x] **Paritas P5**: `restructuring_recommendation_output` byte-identik
      sebelum/sesudah (diverifikasi `git stash`+`diff`); `compute_contract_
      features`/`compute_customer_features` — SELURUH kolom, 0 diff >1e-6;
      `pytest app/machine-learning/tests/ -q` hijau (155 test)
- [x] **Bukti chunking bekerja**: **SELESAI di sesi lanjutan** (awalnya
      ditunda, lihat riwayat di TASK-P5 §3d). Peak RSS diukur ULANG pada
      dataset IDENTIK (100rb customer, bulk_clone) via `perf/benchmark_
      scale.py` yang sama: peak RSS training **3.322,9→1.013,4 MB (−69%)**,
      peak RSS `daily_scoring` **3.219,8→1.506,1 MB (−53%)**, TANPA
      memperlambat (378,9s vs 377,3s training; 185,5s vs 209,1s
      `daily_scoring`, malah 12% lebih cepat). Detail: performance-report.md
      §3f. Paritas byte-level diverifikasi (`git stash`+diff) pada data
      nyata untuk `daily_scoring.py`, ke-4 `train_*.py`, `update_cbs()`.
- [x] k6: p95 + error rate + threshold pass/fail, pada ≥2 konfigurasi worker
      (1 vs 4) **dan** dataset kecil vs besar (2rb vs 100rb) — **SELESAI
      sesi lanjutan**, menemukan bottleneck `_CUSTOMER_LIST_BASE_CTE`
      katastrofik (134× di `dashboard_summary`), root cause teridentifikasi,
      perbaikan sengaja ditunda. Lihat TASK-P7 & `performance-report.md` §4d.
- [x] `performance-report.md`: tabel before/after, **kolom TERUKUR vs PROYEKSI
      terpisah dan tidak mungkin tertukar**, bentuk model + faktor ekstrapolasi
      dinyatakan (2-titik post-chunking, R² tidak dilaporkan — tidak bermakna
      untuk 2 titik, dinyatakan eksplisit sebagai basis lebih lemah dari fit
      5-titik lama), batas regime (RAM, kini di N≈1,67jt via `daily_scoring`,
      naik dari N≈533rb via training sebelum chunking) disebut, bottleneck di
      5 juta (RAM) diidentifikasi, spesifikasi mesin dicatat

**Area 2**
- [x] S1: hasil diff tertulis, desain S2 dipilih berdasarkan itu
- [x] `scoring_history` ≥2 `snapshot_date` untuk `contract_no` sama — 3
      tanggal (D0/D0+7/D0+30), 426 baris masing-masing
- [x] Matriks transisi **bukan** 100% diagonal — 130/426 (30,5%) kontrak
      berubah segmen, lihat `reports/movement_2026-08.md`
- [x] Champion identik di seluruh tanggal (bukti: `registry.json` — 1
      registrasi per model_type per run, training hanya di bootstrap D0)

**Area 3**
- [x] `pytest app/backend/tests/ -q` hijau (89 test — 68 lama + 19 baru
      `test_ai_reasoning_eval.py` + 2 baru `include_rule_nba`)
- [x] `nbaAgreement` hilang dari schema Gemini; nilai tersimpan selalu cocok
      dengan perhitungan ulang (E2, sesi sebelumnya; diverifikasi ULANG di
      Tier 1 `check_agreement_consistency`)
- [~] Tier 1 jalan pada 100% baris tanpa error — **kode+test selesai, DAN
      divalidasi pada 4 output status OK NYATA** (CUST-00001/03/09/12, key
      Gemini diperbarui user di sesi lanjutan) setelah sebelumnya 401 —
      unsupported_claim_rate 0%/0%/6,67%/20%, 0 halusinasi, semua konsisten.
      **N=4 terlalu kecil untuk kesimpulan agregat**, dan kuota harian habis
      (`gemini_quota`/429, tidak pulih setelah backoff 8s+20s+beberapa menit)
      sebelum sampel lebih besar terkumpul — baris DB tertimpa sweep TASK-P5
      yang berjalan bersamaan, angka dikutip dari log terminal (lihat
      `ai-reasoning-evaluation.md`)
- [x] Tier 2: klien OpenAI-compatible berhasil memanggil GLM dan hasilnya
      lolos re-validasi Pydantic — **VERIFIED sesi lanjutan** (user menambah
      `JUDGE_API_KEYS` nyata): `run_tier2_judge()` dipanggil langsung dengan
      payload real + 2 record uji tangan (grounded → 5/5/5/5, fabricated →
      1/1/1/1, model `glm-5.2`) — HTTP call nyata, parse Pydantic sukses,
      judge TERBUKTI diskriminatif. **KEMUDIAN dipasangkan dengan generasi
      Gemini NYATA** (`gemini-3.5-flash`, setelah user mengganti model) untuk
      `CUST-00001` — pasangan Gemini→GLM sungguhan pertama: faithfulness=5,
      actionability=4, internal_consistency=5, key_factors_alignment=5,
      IDENTIK dengan skor record grounded buatan tangan (validasi silang yang
      baik). **judge failure dihitung terpisah, bukan jadi skor 0** — SUDAH
      diverifikasi lewat unit test dengan klien palsu
      (`test_tier2_judge_failure_is_not_scored_zero`)
- [x] Tier 2: protocol `LlmClient` diekstrak tanpa mengubah perilaku
      generator (`GeminiClient` 0 baris diubah; `pytest -q` tetap hijau)
- [x] Tier 4: latents ter-join penuh tanpa baris yatim (2.207=2.207); ambang
      (w,c)→segmen tercatat di kode SEBELUM run dan tidak diubah setelah
      hasil dilihat (AUC 0,91 rendah/tinggi tidak memicu penyesuaian ambang)
- [x] Ablation: tabel dua arm dengan angka nyata — **SELESAI percobaan ke-3**
      (setelah 401 lalu 429, akhirnya berhasil setelah user mengganti model
      Gemini ke `gemini-3.5-flash`): N=8 pasangan valid, arm A 87,5% vs arm B
      87,5% agree-rate dengan rule NBA (delta +0,0pp), 7/8 `primaryNbaAction`
      IDENTIK antar-arm. Keputusan: **anchoring TIDAK terbukti, rule NBA aman
      dipertahankan** — tertulis lengkap di TASK-E6 & `ai-reasoning-
      evaluation.md` §5. N=8 kecil (McNemar formal belum dihitung), tapi
      delta persis 0% adalah sinyal kualitatif yang cukup jelas.
- [x] `npm run lint && npm run build` hijau — TIDAK ada perubahan frontend
      sesi ini (S2-S4/E5-E6 murni backend/ML/scripts), jadi tidak perlu
      dijalankan ulang; hijau terakhir kali dikonfirmasi di sesi P1-P6

## Deliverable akhir

| File | Isi |
|---|---|
| `post-presentation-review-tasks.md` | dokumen ini |
| `performance-report.md` | ✅ sweep before/after, ceiling, hotspot, proyeksi, spek mesin (k6/P7 belum — di luar scope) |
| `ai-reasoning-evaluation.md` | ✅ metode & metrik evaluasi, hasil Tier 1–4 (Tier 4 lengkap, Tier 1-3+ablation menunggu key Gemini/GLM valid), keputusan ablation (tertunda, alasan tertulis) |
| `perf/` | ✅ `benchmark_scale.py`, `profile_scoring.py`, `explain_queries.sql`, `results/`. `k6/` belum (P7) |
| `app/machine-learning/src/perf.py`, `src/db_write.py` | ✅ TASK-P1/P3 — instrumentasi timing + COPY write path |
| `app/machine-learning/src/chunked_features.py` | ✅ TASK-P5 item 1 (sesi lanjutan) — chunked read, RAM training/scoring −69%/−53% di 100rb, byte-identik lewat parity gate |
| `app/machine-learning/src/contract_state.py` | ✅ TASK-S2 — `recompute_contract_state()`/`derive_contract_terms()`, dpd/cycle/OTS dari jadwal cicilan + payment_history live |
| `faker/bulk_clone.py` | ✅ TASK-P3 — jalur data cepat khusus performa, terkarantina dari evaluasi |
| `schema.sql` (diperbarui) | ✅ TASK-P5c (2 index) + TASK-S2 (`scoring_history`, `stg_*`) + TASK-E5 (`ai_reasoning_evaluation`) |
| `scripts/simulate_days.py` | ✅ TASK-S2 — staging sekali → replay bertahap ke tabel live + rescoring asli |
| `scripts/movement_report.py` | ✅ TASK-S4 — matriks transisi + top-mover dari `scoring_history` |
| `scripts/run_ai_reasoning_eval.py` | ✅ TASK-E5 — orchestrator Tier 1-3 |
| `scripts/evaluate_tier4_oracle.py` | ✅ TASK-E5 — Tier 4, latent oracle vs rule engine vs ML |
| `scripts/ablation_nba.py` | ✅ TASK-E6 — ablation anchoring 2-arm |
| `app/backend/services/{ai_reasoning_eval,llm_client,openai_compat_client}.py` | ✅ TASK-E5 — Tier 1-3 + klien LLM-as-judge |
| `scripts/reset-demo.sh` (diperbarui) | ✅ TASK-S2 — tambah `scoring_history` + 5 tabel `stg_*` ke daftar `TABLES` |

Naskah presentasi Tier 4 ikut disalin ke `ai-reasoning-evaluation.md` supaya
tersimpan bersama angkanya, bukan terpisah dari konteksnya.

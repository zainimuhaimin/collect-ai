# CollectAI — Laporan Performance & Skalabilitas

> Ditulis 2026-08-12 sebagai output TASK-P1–P6 (`post-presentation-review-tasks.md`,
> Area 1). Semua angka **TERUKUR** dijalankan nyata di mesin ini pada tanggal
> yang tertulis — bukan estimasi, kecuali ditandai eksplisit **PROYEKSI**.

**Mesin uji:** Mac14,2 (Apple M2), 8 core, RAM 16 GB, disk bebas ~14 GB di awal
sesi pengujian (turun ke ~8,5 GB di akhir sesi karena data uji sendiri —
lihat catatan disk di §5).

---

## Ringkasan eksekutif

| # | Temuan | Dampak |
|---|---|---|
| 1 | `restructuring_runner.py` O(n²) — filter ulang seluruh dataframe di dalam loop per-kontrak | **5,2× lebih cepat** setelah fix (349,0s → 66,6s @ ~48,6rb kontrak) |
| 2 | `feature_engineering.py` — loop Python per customer (`np.polyfit`) + 8 kolom `.agg()` lambda custom | **6,0× lebih cepat** setelah vektorisasi (145,9s → 24,3s @ 50rb customer) |
| 3 | Ladder sweep sebelum fix: **patah di 100rb customer** (timeout 20 menit, BUKAN RAM/disk) | Setelah fix: **100rb selesai dalam 209s** — 100rb bukan lagi ceiling waktu |
| 4 | Index baru pada `lkp_interaction`/`payment_history` (bukti EXPLAIN, bukan spekulatif) | Query dashboard/contract-list dari Sort+Index Scan → **Index Only Scan** |
| 5 | RAM 16GB diproyeksikan penuh di **~530rb customer** (angka SEBELUM chunking — lihat §4 untuk revisi) | Koreksi ke atas dari estimasi awal — diukur, bukan ditebak |
| 6 | 5.000.000 customer **tidak terukur di mesin ini** — proyeksi linier menyilang batas RAM/disk jauh sebelum 5 juta | Wajib PROYEKSI, bukan TERUKUR (lihat §4) |
| 7 | **(Sesi lanjutan) Chunked read** — item TASK-P5 yang awalnya ditunda, akhirnya dikerjakan | Peak RSS training **−69%**, `daily_scoring` **−53%** di 100rb customer, TANPA memperlambat (lihat §3f) |
| 8 | **(TASK-P7) Load test k6 menemukan bottleneck API KATASTROFIK** — `_CUSTOMER_LIST_BASE_CTE` dihitung ulang PENUH (2×) per request, tidak berskala dengan LIMIT/OFFSET | `dashboard_summary` p95 **685ms → 92.000ms (134×)** dari 2rb→100rb customer. Belum diperbaiki — lihat §4d |

---

## 1. Metodologi

- **Instrumentasi** (`app/machine-learning/src/perf.py`, TASK-P1): setiap stage
  `daily_scoring.py` dan ke-4 `train_*.py` dibungkus `stage_timer` — durasi,
  peak RSS (`resource.getrusage`, dinormalisasi macOS bytes → MB), jumlah baris,
  ditulis ke `app/machine-learning/logs/perf_runs.csv`.
- **Data volume besar** (`faker/bulk_clone.py`, TASK-P3): rung ≥30.000 customer
  memakai bulk-clone (benih 20.000 customer lewat simulator asli + replikasi
  berperturbasi, ditulis via `COPY`). **Rung ini TIDAK VALID untuk evaluasi
  akurasi** — lihat karantina di bawah.
- **Harness sweep** (`perf/benchmark_scale.py`, TASK-P4): per rung — reset DB →
  muat data → 4× `train_*.py` (wajib sebelum scoring) → `daily_scoring.py` →
  catat rows/DB size/RSS dari `perf_runs.csv`. Stop rule: timeout per-stage,
  ambang sisa disk.
- **Profiling** (`perf/profile_scoring.py` + `perf/explain_queries.sql`,
  TASK-P2): `cProfile` membungkus `run_daily_scoring()` pada 50.000 customer;
  `EXPLAIN (ANALYZE, BUFFERS)` pada 4 query backend paling sering dipanggil.

**⚠️ Karantina bulk-clone (WAJIB dibaca sebelum memakai angka manapun di
laporan ini untuk klaim akurasi).** Semua rung ≥30rb customer di tabel-tabel
berikut memakai `faker/bulk_clone.py` — baris hasil clone diberi prefiks ID
`PCxxxx-` dan `_audit_latents.parquet/csv` lama otomatis diinvalidasi
(`.INVALIDATED`) begitu bulk-clone dijalankan. **Setiap angka performa di
laporan ini sah untuk klaim TIMING/RAM/DISK. TIDAK SATU PUN sah untuk klaim
akurasi model** — itu domain `ai-reasoning-evaluation.md` (Area 3, TASK-E5)
yang memakai data dari simulator asli dengan `--dump-latents` murni.

---

## 2. Hotspot ditemukan (TASK-P2) — profiling nyata 50.000 customer

`perf/profile_scoring.py` (cProfile) pada dataset 50.000 customer / 69.210
kontrak menemukan:

| Peringkat | Lokasi | Kontribusi (cProfile, inflasi ~5-10× dari overhead tracing) | Root cause presisi |
|---|---|---|---|
| **#1** | `restructuring_runner.py:256/274` | 361s / 590s total (61%) | **O(n²)**: `merged[merged["cust_id"]==row["cust_id"]]` di DALAM loop `for _, row in merged.iterrows()` — filter ulang seluruh dataframe n kali |
| **#2** | `feature_engineering.py::_compute_delay_trend` | 126,8s (48.550 panggilan) | Loop Python per customer memanggil `np.polyfit` satu-per-satu — punya bentuk tertutup OLS yang bisa divektorisasi total |
| **#3** | `feature_engineering.py` — 9 kolom `.agg()` lambda custom | 76,7s | `_python_agg_general` pandas — lambda custom TIDAK divektorisasi C, jatuh ke iterasi Python per grup |
| #4 | `_CUSTOMER_LIST_BASE_CTE` (backend, `customer_repository.py`) | 226,9ms/panggilan (EXPLAIN) | 2× Seq Scan `contract_snapshot` + sort spill-to-disk |
| #5 | `latest_ptp` (dashboard + contract list, `lkp_interaction`) | Incremental Sort setelah Index Scan | Index existing (`contract_no, ptp_status`) tidak cocok `ORDER BY action_date` |

**Catatan kejujuran:** #1-#3 TIDAK ADA di baseline hipotesis awal plan (yang
menduga `daily_scoring.py`'s `SELECT *` sebagai dinding utama) — ditemukan
lewat profiling NYATA, bukan dugaan. #1 (restructuring) ternyata **jauh lebih
besar** dari yang diduga siapa pun sebelum diukur.

Query yang SUDAH cepat (tidak perlu index baru): `get_customer_profile`
(LATERAL join outstanding, 23,6ms — index scan langsung via PK).

Beberapa index ber-`idx_scan=0` ditemukan (`idx_ai_output_cust`,
`idx_restructure_group_cust`, dll) — **kemungkinan** karena endpoint
terkait tidak tersentuh selama sesi profiling ini, BUKAN bukti pasti tidak
berguna secara global. Tidak dihapus tanpa audit call-site kode terpisah.

---

## 3. Perbaikan diterapkan (TASK-P5) — sebelum vs sesudah, TERUKUR

### 3a. Fix O(n²) `restructuring_runner.py`

`groupby("cust_id")` SEKALI sebelum loop → lookup O(1) per baris, bukan
filter O(n) berulang n kali.

**Paritas:** `restructuring_recommendation_output` JOIN `restructuring_group_map`
(5.869 baris, 4.167 kontrak) — **byte-untuk-byte identik** sebelum/sesudah
(diverifikasi `git stash` + `diff`, jalur kode sama, isolasi ketat).

| n_kontrak | Sebelum (`restructuring_assessment` stage) | Sesudah |
|---|---|---|
| ~4.900 | 6,8s | — |
| ~9.800 | 18,4s | — |
| ~24.300 | 86,2s | — |
| ~48.650 | 349,0s | **66,6s** (n≈48.610) |

Pertumbuhan sebelum fix jelas super-linear (rasio waktu > rasio n secara
konsisten) — persis pola O(n²). **5,2× lebih cepat** pada volume yang hampir
sama.

### 3b. Vektorisasi `feature_engineering.py`

`_compute_delay_trend_batch()` (rumus tertutup OLS, vektor untuk semua
customer sekaligus) + 8 dari 9 kolom `.agg()` lambda diganti boolean/numeric
pre-computed + `.agg("sum")` biasa (C-level, bukan Python).

**Paritas:** SELURUH 38 kolom `compute_contract_features` (72.070 baris) dan
SELURUH 20 kolom `compute_customer_features` (50.000 baris) — **0 perbedaan
di atas toleransi 1e-6** (sisa ~1e-14, floating-point noise SVD vs rumus
tertutup).

| Versi | Waktu @ 50.000 customer |
|---|---|
| Sebelum | 145,9s |
| + fix delay_trend | 68,4s (2,1×) |
| + fix 8 lambda agg | **24,3s (6,0× total)** |

**1 lambda tidak disentuh** (`recovery_source` mode) — pandas tidak punya
reduksi vektor "mode per grup" yang aman menjaga tie-break identik; risiko
lebih besar dari manfaat untuk 1 dari 9 kolom.

### 3c. Index baru + atomicity

`idx_lkp_contract_action_date (contract_no, action_date DESC)` dan
`idx_payment_contract_due_date (contract_no, due_date DESC)` ditambahkan ke
`schema.sql` — diverifikasi EXPLAIN: query jadi Index Only Scan / Index Scan
langsung, tanpa sort terpisah.

**Trade-off disk (diukur, bukan estimasi):**

| Index | Ukuran | vs tabel induk |
|---|---|---|
| `idx_lkp_contract_action_date` | 57 MB | +23% (`lkp_interaction` 251→308 MB) |
| `idx_payment_contract_due_date` | 27 MB | +23% (`payment_history` 119→146 MB) |

`_upsert_feature_snapshot` — DELETE+INSERT digabung jadi satu transaksi
(dulu 2 `engine.begin()` terpisah, cacat atomicity).

### 3d. Item 1 (chunked read) — SELESAI di sesi lanjutan

**Update:** item ini AWALNYA ditunda (alasan tertulis di bawah, dipertahankan
sebagai riwayat keputusan) karena dianggap "pekerjaan multi-hari, bukan yang
aman diselesaikan tergesa". Di sesi lanjutan, user eksplisit meminta
menyelesaikan temuan yang memakan waktu — item ini dikerjakan. Hasil lengkap
di §3f. Ringkasan alasan penundaan asli (untuk konteks keputusan):

> `compute_contract_features`/`compute_customer_features` adalah pure
> function yang diuji 27+30 test di `test_features.py` dengan memanggilnya
> langsung memakai dataframe mentah — mendorong agregasi ke SQL berarti
> mengubah kontrak input fungsi ini. Solusi yang akhirnya dipakai (§3f)
> **tidak mengubah kontrak fungsi itu sama sekali** — partisi per-batch
> `cust_id` di lapisan orkestrasi baru (`chunked_features.py`), bukan di
> `feature_engineering.py`.

- **Column pruning** (`SELECT *` → daftar kolom) — TETAP tidak dikerjakan.
  Tabel terbesar sudah relatif sempit (payment_history 10 kolom,
  lkp_interaction 12 kolom), manfaat marginal dibanding risiko audit
  `_pick_col()` dinamis di 6 file.

### 3e. Efek gabungan pada ladder — 100rb customer (sebelum vs sesudah P5 CPU-fix)

| | Sebelum P5 | Sesudah P5 (CPU-fix, sebelum chunking) |
|---|---|---|
| `daily_scoring` @ 100rb | **TIMEOUT (>1200s / 20 menit)** | **209,1s** |

100.000 customer BUKAN LAGI ceiling waktu setelah fix CPU (§3a/3b). Ceiling
berpindah ke RAM di N lebih besar — lihat §3f/§4 untuk efek chunked read.

### 3f. Chunked read (item 1, sesi lanjutan) — hasil, bug ditemukan, parity

**Desain.** `src/chunked_features.py` (baru) — `compute_contract_features()`/
`compute_customer_features()` **TIDAK diubah kontraknya sama sekali** (57
test lama tetap hijau + 10 test parity baru,
`tests/test_features_chunked.py`). Data dipecah per batch `cust_id` (default
5.000, `FEATURE_CHUNK_BATCH_SIZE`), fungsi ASLI dipanggil pada tiap batch,
hasil digabung. Benar secara matematis karena SETIAP agregasi di kedua
fungsi itu (mode `recovery_source`, `delay_trend` OLS, PTP-kept windowed
join, `channel_effectiveness`, lineage restrukturisasi) murni dalam lingkup
SATU `cust_id` — tidak ada yang menyilang customer. Diwire ke
`daily_scoring.py`, ke-4 `train_*.py`, dan `cbs_builder.py::update_cbs()`.

**3 bug nyata ditemukan LEWAT parity gate (git stash + diff byte-level pada
data nyata), bukan lewat pembacaan kode:**

1. **Train/serve skew pre-existing** (bukan diperkenalkan sesi ini):
   `train_*.py` mengirim `df_customer` ke `compute_contract_features`
   (`installment_to_income_ratio` pakai income level ASLI), tapi
   `daily_scoring.py`/`update_cbs()` TIDAK PERNAH mengirimnya (selalu
   fallback flat 5.000.000) — sudah begitu SEBELUM ada chunking. Dicatat
   sebagai temuan, **TIDAK diperbaiki** (butuh evaluasi retraining, di luar
   scope RAM ini). `chunked_features.py` mereplikasi kedua perilaku lewat
   parameter `pass_customer_to_contract_features` (WAJIB disamakan per
   caller, bukan ditebak).
2. **Cabang global-vs-per-kontrak `recovery_source_encoded`**: kalau
   dataframe payment yang diberikan kosong TOTAL, fungsi asli mengisi `0`
   eksplisit; kalau tabel tidak kosong tapi satu kontrak tertentu memang
   tidak punya payment, hasilnya `NaN` (merge leftover). Chunking bisa
   membuat satu batch kebetulan kosong padahal tabel keseluruhan tidak —
   dikoreksi di layer orkestrasi (cek `EXISTS` murah di level tabel).
3. **Tie-break tidak stabil di `last_result_code`**: `sort_values(
   "action_date")` tanpa kunci sekunder memakai quicksort (TIDAK stabil) —
   hasilnya bergantung pada isi/ukuran array yang disortir, bukan cuma
   urutan relatif baris yang tie. Bug determinisme PRE-EXISTING di
   `feature_engineering.py` sendiri — **diperbaiki di sumbernya**
   (`sort_values(["action_date", "lkp_id"])`) karena tidak mungkin
   direplikasi dari luar tanpa akses ke seluruh array yang disortir.

**Paritas diverifikasi byte-level** (metodologi P5a/b: `git stash` + diff)
pada 1.500 customer/2.127 kontrak aktif nyata: `daily_scoring.py`
(`ai_intelligence_output`, `scoring_feature_snapshot`,
`customer_behavioral_standing` — identik), ke-4 `train_*.py` (n, paid_rate,
AUC, seluruh feature importance — identik sampai 6 desimal), `update_cbs()`
(13 kolom × 1.500 baris — identik).

**Hasil RAM nyata — 100.000 customer, dataset IDENTIK (bulk_clone), diukur
via `perf/benchmark_scale.py` yang sama:**

| Metrik | Sebelum chunking | Sesudah chunking | Perubahan |
|---|---|---|---|
| Peak RSS training (4 model) | 3.322,9 MB | **1.013,4 MB** | **−69%** |
| Peak RSS `daily_scoring` | 3.219,8 MB | **1.506,1 MB** | **−53%** |
| Waktu training (total 4) | 377,3 s | 378,9 s | ~sama |
| Waktu `daily_scoring` | 209,1 s | 185,5 s | −12% (bonus, bukan tujuan utama) |

**Ini bukti langsung "chunking bekerja"**: RAM berkurang drastis TANPA
memperlambat (malah sedikit lebih cepat, kemungkinan overhead SQL kecil per
batch tertutup oleh working-set yang lebih kecil/cache-friendly). Titik
silang RAM 16GB yang diproyeksikan P6 di N≈533rb (§4c lama) perlu dihitung
ulang — lihat §4 (diperbarui).

---

## 4. Sweep ladder TERUKUR + PROYEKSI ke 5 juta

> **⚠️ Dokumen ini punya DUA generasi angka** — dibedakan eksplisit supaya
> tidak tertukar: **§4a "sebelum chunking"** (5rb-100rb, dari P4/P6 —
> sebelum TASK-P5 item 1 dikerjakan) dan **§4a-lanjutan "sesudah chunking"**
> (100rb/250rb, sesi lanjutan). Proyeksi §4c LAMA (titik silang RAM di
> N≈533rb) **SUDAH DIGANTIKAN** oleh §4c-lanjutan di bawah — jangan
> mengutip 533rb lagi setelah membaca bagian ini.

### 4a. TERUKUR — sebelum chunking (P4/P6, baseline historis)

| N customer | generate | train (total 4) | daily_scoring | peak RSS train | DB size |
|---|---|---|---|---|---|
| 5.000 | 17,6s | 34,5s | 11,3s | 458,7 MB | 96,8 MB |
| 10.000 | 34,2s | 52,9s | 19,9s | 704,9 MB | 144,2 MB |
| 25.000 | 83,0s | 88,0s | 49,6s | 1.289,1 MB | 275,4 MB |
| 50.000 | 88,5s | 171,1s | 97,0s | 2.167,4 MB | 615,5 MB |
| 100.000 | 125,0s | 377,3s | 209,1s | 3.322,9 MB | 1.232,7 MB |
| 250.000 | ✅ (bulk-clone selesai) | ⛔ **TIMEOUT** (900s, di `train_initial_model.py`) | — | — | — |

Titik patah lama: 250.000 customer, oleh WAKTU — `train_initial:load`
sendirian makan **192,4s** (360.944 baris `payment_history`+`lkp_interaction`
termuat penuh ke pandas). Ini persis dinding yang TASK-P5 item 1 (chunked
read) dirancang untuk menghilangkan — lihat §3f dan §4a-lanjutan di bawah:
rung yang SAMA (250rb) kini selesai dalam hitungan menit, bukan timeout.

### 4a-lanjutan. TERUKUR — SESUDAH chunking (sesi lanjutan, TASK-P5 item 1)

Dataset IDENTIK (bulk_clone, seed berbeda per rung tapi metodologi sama),
diukur dengan `perf/benchmark_scale.py` yang SAMA, kode SESUDAH chunking:

| N customer | generate | train (total 4) | daily_scoring | peak RSS train | peak RSS score | DB size |
|---|---|---|---|---|---|---|
| 100.000 | 129,9s | 378,9s | 185,5s | **1.013,4 MB** | **1.506,1 MB** | 1.200,3 MB |
| 250.000 | 240,7s | 910,9s | 645,5s | **1.783,8 MB** | **2.927,0 MB** | 3.021,0 MB |
| 500.000 | ✅ (bulk-clone selesai) | ⛔ **TIMEOUT** (900s, di `train_initial_model.py`, sebelum sempat menulis stage `feature`/`train`) | — | — | — | 6.994.650 baris `payment_history` + 15.222.100 baris `lkp_interaction` termuat di DB (bulk-clone), tidak terpakai jauh sebelum timeout |

**250.000 customer — TIDAK LAGI timeout.** Rung yang SEBELUMNYA mati di
`train_initial:load` (192,4s sendirian, lalu >900s total) sekarang selesai
seluruh 4 training + scoring hanya dalam ~910,9s (train) + 645,5s (score),
kedua-duanya JAUH di bawah budget 900s PER STAGE (bukan per rung). Detail
per-stage `train_initial_model.py` @ 250rb: `load`=4,1s (vs 192,4s dulu —
**47× lebih cepat**, karena hanya `contract_snapshot`+`customer_master`
yang dimuat penuh, bukan `payment_history`/`lkp_interaction`), `feature`
(chunked, 50 batch × 5.000)=148,8s, `train` (XGBoost fit)=108,2s.

**Titik patah BARU di rung ini: TIDAK ADA** — 250.000 selesai bersih tanpa
menyentuh stop rule apa pun. `daily_scoring_s` naik ke 645,5s, tapi **55%
dari itu (357,9s) adalah `restructuring_assessment`** (perbandingan
97.420→243.616 kontrak aktif: 134,4s→357,9s, rasio 2,66× untuk 2,50× kontrak
— mendekati linier, TIDAK regresi O(n²) yang sama seperti P2/P5a; itu sudah
terverifikasi tetap terperbaiki). Bagian chunked (`feature_contract_chunked`
+ `cbs_bootstrap`) hanya 118,1s+133,8s=251,9s dari total 645,5s.

**500.000 customer — TIMEOUT baru, oleh SEBAB BERBEDA dari 250rb lama.**
`train_initial:load` tetap cepat (9,0s — hanya `contract_snapshot`+
`customer_master`, tabel kecil, tidak terpengaruh skala baris
`payment_history`/`lkp_interaction`). Tapi stage `feature` (chunked, 100
batch × 5.000) + `train` (XGBoost fit) di 500rb **bersama-sama melebihi
891s** (900s dikurangi 9s load) — tidak ada baris `train_initial:feature`
tercatat di `logs/perf_runs.csv`, artinya proses di-SIGKILL oleh
`subprocess.run(timeout=900)` di TENGAH stage tersebut, sebelum
context-manager `stage_timer`-nya sempat menulis baris. Dibandingkan 250rb
(feature=148,8s + train=108,2s = 257,0s total), ini kenaikan **>3,5×** untuk
kenaikan N hanya 2× — indikasi scaling super-linier mulai muncul di rentang
ini (kandidat penyebab: overhead per-batch `pd.concat` menumpuk pada 100
batch vs 50 batch, atau XGBoost fit time yang tidak linier terhadap baris
training). **Ini bukan lagi dinding RAM** (peak RSS di titik ini jauh di
bawah 16GB per model §4c-lanjutan) — 900s adalah budget ARBITRER yang
dipilih harness `benchmark_scale.py` untuk keperluan sweep, bukan limit
sistem yang keras. Produksi nyata tidak dibatasi 900s per stage; angka ini
memberi tahu kita bahwa training di skala 500rb makan waktu ORDE PULUHAN
MENIT (>15 menit), bukan bahwa ia MUSTAHIL — tapi ini tetap sinyal jujur
yang wajib dilaporkan: 3 titik (100rb, 250rb, dan kegagalan di 500rb)
konsisten menunjuk pola scaling waktu yang mulai memburuk, terlepas dari
cerita RAM di §4c-lanjutan.

**Catatan operasional — proses "yatim" (orphan).** Setelah harness
melaporkan STOPPED_TIMEOUT untuk rung 500rb dan proses orkestrator
`benchmark_scale.py` keluar, satu subprocess `train_self_cure.py` masih
DITEMUKAN HIDUP beberapa menit kemudian (RSS terus bertambah, PID
independen). Ini kemungkinan sisa dari insiden concurrent-access lebih
awal dalam rangkaian sesi ini (verifikasi ad-hoc yang tumpang-tindih dengan
sweep), bukan perilaku `benchmark_scale.py` yang terverifikasi disengaja —
`subprocess.run(..., timeout=...)` Python SEHARUSNYA mem-SIGKILL child
langsung saat timeout. Proses yatim ini di-`kill` manual begitu ditemukan;
tidak ada dampak pada angka 100rb/250rb yang sudah dicatat (rung itu sudah
selesai dan datanya sudah ditulis ke `scale_sweep.csv` sebelum insiden ini).
Dicatat di sini untuk transparansi, bukan diklaim sebagai bug
`benchmark_scale.py` yang terbukti — akar sebabnya tidak ditelusuri lebih
jauh karena di luar prioritas sesi ini.

### 4b. Efek chunking terhadap RAM — perbandingan langsung, N sama

| Metrik | Sebelum chunking (100rb) | Sesudah chunking (100rb) | Perubahan |
|---|---|---|---|
| Peak RSS training | 3.322,9 MB | 1.013,4 MB | **−69%** |
| Peak RSS `daily_scoring` | 3.219,8 MB* | 1.506,1 MB | **−53%** |

\*peak RSS score 100rb "sebelum" diambil dari kolom `peak_rss_score_mb` P6
lama (§4a) — stage yang sama, sebelum item 1 dikerjakan.

### 4c-lanjutan. Model RAM baru (fit 2 titik TERUKUR: 100rb, 250rb) + titik silang 16GB

**⚠️ Kejujuran statistik — HANYA 2 titik RAM lengkap.** Dua titik SELALU pas
sempurna membentuk satu garis (R² tidak bermakna, tidak dilaporkan). Ini
basis yang LEBIH LEMAH dari fit 5-titik §4a lama — rung ke-3 (500rb) SUDAH
DICOBA dalam sesi ini tapi TIMEOUT sebelum stage `feature`/`train`
menuliskan angka RSS-nya (lihat §4a-lanjutan) — jadi tidak ada titik RAM
ke-3 untuk memperkuat model di bawah. Angka RAM di bawah adalah estimasi
arah yang KUAT (perbedaannya besar, bukan noise), bukan model yang final.
**Model WAKTU (bukan RAM) justru punya sinyal ke-3**: kegagalan 500rb pada
stage yang sama menunjukkan waktu training mulai membengkak super-linier
di rentang 250rb-500rb — lihat catatan di §4a-lanjutan. Kedua model ini
(RAM vs waktu) bisa membentuk dinding yang BERBEDA; laporan ini melacak
keduanya secara terpisah, bukan mencampurnya jadi satu angka proyeksi.

| Metrik | Model (linear, 2 titik) | Slope lama (5 titik, sebelum chunking) | Rasio |
|---|---|---|---|
| Peak RSS training | 499,8 + 0,00514·N MB | 0,0299 MB/customer | **5,8× lebih lambat naik** |
| Peak RSS `daily_scoring` | 558,8 + 0,00947·N MB | *(tidak dipisah di model lama)* | — |

**Titik silang RAM 16 GB (16.384 MB) — REVISI dari perkiraan lama:**

| | Sebelum chunking | Sesudah chunking |
|---|---|---|
| Training | N≈533.000 | **N≈3.093.000** |
| `daily_scoring` | *(mengikuti training, sama)* | **N≈1.671.000** |

**Constraint RAM pengikat SEKARANG: `daily_scoring` di N≈1,67 juta** (bukan
training) — turun dari training-bound 533rb SEBELUM chunking, TAPI naik 3,1×
lipat dibanding titik silang lama. **5.000.000 customer MASIH melintasi
batas regime RAM** (5 juta ada 2,99× lebih jauh dari titik silang 1,67 juta)
— proyeksi ke 5 juta TETAP tidak sah secara fisik, TAPI jarak ekstrapolasi
mengecil drastis (dari "9,4× lebih jauh dari titik silang" jadi "3,0× lebih
jauh") — chunking TIDAK menghilangkan dinding RAM, tapi memindahkannya jauh
lebih dekat ke target 5 juta.

**Kenapa `daily_scoring` (bukan training) yang jadi constraint sekarang:**
`restructuring_assessment` (dalam `daily_scoring`) TIDAK di-chunk sesi ini
(di luar scope TASK-P5 item 1, yang menyasar `compute_contract_features`/
`compute_customer_features`) — ia tetap memuat `contract_snapshot`+
`customer_behavioral_standing`+`asset_appraisal` penuh (tabel kecil per-baris,
tapi ikut menyumbang RSS 2.927 MB peak di 250rb). Ini kandidat pekerjaan
LANJUTAN kalau target RAM ingin didorong lebih jauh lagi — di luar scope
sesi ini.

**Disk masih constraint KEDUA** (setelah RAM di kedua rezim) — bytes/row
stabil (255,9→259,8 di 100rb→250rb), model disk lama (§4a, sebelum
chunking) tetap valid karena COPY/schema tidak berubah oleh chunking.

**Kesimpulan yang bisa dipertanggungjawabkan:** TASK-P5 item 1 (chunked
read) berhasil memindahkan dinding RAM secara SUBSTANSIAL (533rb→1,67jt,
3,1×), TAPI TIDAK menghilangkannya — 5 juta customer TETAP tidak bisa diukur
ATAU diproyeksikan bermakna di mesin 16GB RAM ini. Constraint RAM berpindah
dari training ke `daily_scoring`/`restructuring_assessment`, yang belum
disentuh optimasi RAM sesi ini. **Selain itu, ada dinding KEDUA yang baru
muncul di rentang 250rb-500rb: waktu.** Rung 500rb DICOBA dan gagal karena
melebihi budget 900s per stage (bukan RAM) — chunking menyelesaikan masalah
RAM tapi memori bukan satu-satunya sumbu; waktu proses linear-ish tapi
dengan konstanta yang cukup besar (dan indikasi awal super-linier) di skala
ini juga jadi kandidat pembatas praktis, terlepas dari RAM. Rung 1jt tidak
dicoba (500rb sudah gagal lebih dulu). Kedua dinding ini (RAM di ~1,67jt,
waktu entah di mana tepatnya antara 250rb-500rb) sama-sama relevan untuk
percakapan "berapa customer yang realistis diproses per hari di mesin
ini" — jawaban jujurnya: **di bawah 500rb**, dengan RAM baru jadi masalah
jauh di atas itu.

---

## 4d. Load test API (k6) — TASK-P7

**Mesin sama** (Apple M2, 8 core, 16GB RAM). `perf/k6/read_endpoints.js`
(baru) — ramping-VU (0→10→50→50→0 selama 4 menit) pada 5 endpoint baca
panas: `dashboard/summary`, `customers` (list+paginasi), `customers/{id}`,
`contracts` (list), `contracts/{no}`. Threshold: `p(95)<500ms`,
`http_req_failed<0.01`. Tidak satu pun dari 5 endpoint ini butuh
autentikasi (diverifikasi lewat pembacaan kode — tidak ada yang memakai
`Depends(get_current_user)`), jadi skrip tidak melakukan login.

**Dua sumbu diuji terpisah** (sesuai metodologi wajib TASK-P7): jumlah
worker `uvicorn`, dan volume data — supaya efek concurrency tidak
tercampur dengan efek volume.

### Sumbu 1 — jumlah worker (dataset KECIL tetap, 2.000 customer, 2.766 kontrak, TERSKOR penuh)

| Metrik | 1 worker | 4 worker |
|---|---|---|
| p95 keseluruhan | 261,2 ms ✅ | 372,7 ms ✅ |
| p95 `dashboard_summary` | 388,3 ms ✅ | 685,2 ms ❌ (>500ms) |
| p95 `customer_list` | 225,2 ms ✅ | 229,1 ms ✅ |
| Error rate | 0% | 0% |
| Throughput (req/s) | 132,1 | 95,3 |
| Outlier maksimum | 1,0s | **1m33s** (satu iterasi `customer_list`) |

**Temuan tak terduga: 4 worker LEBIH BURUK dari 1 worker pada dataset
kecil ini** — bukan lebih baik seperti asumsi umum "lebih banyak worker =
lebih cepat". Throughput turun (132→95 req/s) dan `dashboard_summary`
melewati threshold di 4 worker tapi lolos di 1 worker. Hipotesis paling
mungkin (belum diverifikasi lebih jauh — di luar scope sesi ini): setiap
worker `uvicorn` membuat `Engine` SQLAlchemy sendiri
(`core/dependencies.py` — `create_engine()` di-cache per proses lewat
`@lru_cache`, BUKAN dibagi antar worker), dengan pool default SQLAlchemy
(`pool_size=5, max_overflow=10`). 4 worker × pool berarti hingga 60 koneksi
bersaing ke SATU Postgres yang tidak ikut di-scale — kemungkinan
kontensi koneksi/lock, bukan CPU. **Jangan menyimpulkan "tambah worker
selalu membantu" dari angka lain di laporan ini tanpa menguji ulang.**

### Sumbu 2 — volume data (worker tetap 4, dataset BESAR: 100.000 customer, 138.220 kontrak, TERSKOR penuh via `bulk_clone.py`)

| Endpoint | p95 @ 2rb customer (4 worker) | p95 @ 100rb customer (4 worker) | Kenaikan |
|---|---|---|---|
| `dashboard_summary` | 685,2 ms | **1m32s** (92.000 ms) | **134×** |
| `customer_list` | 229,1 ms | **19,06s** | **83×** |
| `contract_list` | (tidak diukur terpisah di sumbu 1) | **52,81s** | — |
| `customer_detail` | ~96-148ms (sumbu 1, sampel gabungan) | **17,5s** | — |
| `contract_detail` | ~45-111ms (sumbu 1, sampel gabungan) | **16,83s** | — |
| Throughput total | 95,3 req/s | **3,0 req/s** | **−97%** |

**⚠️ Ini bukan "sedikit lebih lambat" — ini KATASTROFIK, dan ROOT CAUSE-nya
ditemukan, bukan spekulasi.** `list_customers_page()`
(`app/backend/repositories/customer_repository.py:231-254`) menjalankan
**seluruh `_CUSTOMER_LIST_BASE_CTE`nya DUA KALI per request** — sekali untuk
`SELECT count(*) FROM (filtered_sql) t` (total untuk paginasi), sekali lagi
untuk baris halaman yang sebenarnya (`... ORDER BY ... LIMIT ... OFFSET`).
CTE itu sendiri (`:56-101`) menghitung **DISTINCT ON di seluruh
`contract_snapshot`** (dua kali — `primary_contract` dan `contract_priority`),
**DISTINCT ON di seluruh `ai_intelligence_output`** (`latest_score`), dan
`GROUP BY` per customer (`customer_priority`) — **untuk SEMUA baris di
tabel, bukan hanya 20 baris yang akan ditampilkan** — LIMIT/OFFSET baru
diterapkan di paling akhir, setelah semua agregasi berat selesai. Filter
`high_ambc` (dipakai filter chip UI) menambah lagi satu `percentile_cont`
atas SELURUH `contract_snapshot` per request (`_AMBC_THRESHOLD_SQL`,
`:110-112`). Pola ini SAMA untuk endpoint `contracts` (list). Index yang
ditambahkan di TASK-P5c tidak menyentuh masalah ini — index membantu SEEK,
bukan menghilangkan kebutuhan menghitung ulang agregat penuh setiap request.

Ini BUKAN temuan baru sepenuhnya — TASK-P2 sudah menandai CTE ini sebagai
hotspot di 50.000 customer (226,9ms, lihat §2) dan itu terdengar "cukup
cepat" sehingga tidak diprioritaskan. **Load test di 100.000 customer
membuktikan pola ini TIDAK degradasi linier — ia menjadi katastrofik jauh
lebih cepat dari yang tersirat di angka 50rb.** Ini murni ditemukan lewat
load test (TASK-P7), bukan lewat profiling `cProfile` (TASK-P2) yang hanya
membungkus `run_daily_scoring()`, tidak pernah menyentuh jalur API baca.

**Sengaja TIDAK diperbaiki di sesi ini** — ini perubahan arsitektur query
(memindahkan agregasi ke tabel materialized/pre-computed, atau menghitung
`count(*)` secara approksimasi, atau caching), bukan sesuatu yang aman
diubah tergesa di tengah sesi yang sedang fokus ke area lain. **Ditulis di
sini secara eksplisit sebagai temuan kritis yang wajib ditindaklanjuti**
sebelum sistem ini dianggap siap menangani volume customer besar dari sisi
API — terlepas dari cerita RAM/waktu pipeline batch di §4 yang sudah lebih
baik.

**Selesai kalau (verifikasi TASK-P7).** p95 + error rate + RPS terlaporkan
pada 2 konfigurasi worker (✅, sumbu 1) dan pada dataset kecil vs besar
(✅, sumbu 2); threshold pass/fail dilaporkan apa adanya, termasuk yang
GAGAL (✅ — `dashboard_summary` di 4 worker/kecil, dan SEMUA endpoint di
100rb, dilaporkan gagal, tidak disembunyikan).

---

## 5. Catatan disk sesi ini

Disk bebas turun dari ~14 GB (awal sesi review) ke ~8,5 GB (akhir sesi
review pertama) akibat data uji (bulk-clone berulang, model artifact, log)
yang dibuat SELAMA pengujian ini sendiri — bukan properti tetap mesin.
Proyeksi §4c (lama, sebelum chunking) memakai baseline 14GB untuk
perbandingan yang adil.

**Sesi lanjutan (chunked read):** rung 100K dan 250K menambah data lagi
(≈1,2 GB dan ≈3,0 GB DB masing-masing, lihat kolom `db_size_bytes` §4a-lanjutan)
sebelum rung 500K/1M dimulai. Constraint disk **tidak berubah** oleh chunking
(chunking mengubah RAM-path, bukan write-path/schema) — model disk §4a lama
tetap dipakai untuk proyeksi ke 5 juta di §4c-lanjutan.

---

## 6. Yang TIDAK dikerjakan di sesi ini (transparansi)

- **TASK-P7 SELESAI** (lihat §4d) — dan menemukan bottleneck API paling
  parah di seluruh laporan ini (`_CUSTOMER_LIST_BASE_CTE`, 134× lebih lambat
  di 100rb vs 2rb customer). **Perbaikannya SENGAJA TIDAK dikerjakan** —
  perubahan arsitektur query (materialized view / pre-agregasi / caching),
  bukan sesuatu yang aman diubah tergesa. Ini rekomendasi paling mendesak
  dari seluruh Area 1 untuk pekerjaan lanjutan.
- **`restructuring_assessment` (di dalam `daily_scoring`) belum di-chunk** —
  ini SEKARANG jadi constraint RAM pengikat (§4c-lanjutan, titik silang
  N≈1,67jt), setelah `compute_contract_features`/`compute_customer_features`
  berhasil di-chunk. Kandidat pekerjaan lanjutan berikutnya kalau target RAM
  ingin didorong lebih jauh dari 1,67jt.
- **Column pruning** (`SELECT *` → daftar kolom terpakai, TASK-P5 item 2) —
  masih belum dikerjakan; risiko rendah tapi tidak krusial/memakan waktu,
  jadi tidak masuk prioritas sesi lanjutan ini.
- **Train/serve skew di `installment_to_income_ratio`** (ditemukan lewat
  parity gate sesi lanjutan, §3f) — didokumentasikan, SENGAJA TIDAK diperbaiki
  karena memperbaikinya akan mengubah nilai fitur yang dipakai model produksi
  saat ini, butuh validasi ulang model sebelum aman diubah — di luar scope
  sesi ini.
- Rung 500rb — **DICOBA, gagal karena TIMEOUT** (900s, stage `feature`/`train`
  `train_initial_model.py`, lihat §4a-lanjutan) — bukan karena RAM/disk, jadi
  TIDAK menambah titik ke-3 untuk model RAM §4c-lanjutan (tidak ada angka RSS
  yang tercatat dari rung ini). 1jt/2,5jt/5jt tidak dicoba (500rb sudah gagal
  lebih dulu di stage yang lebih awal dalam ladder). §4c-lanjutan TETAP
  proyeksi RAM 2-titik saja — untuk memperkuatnya butuh rung 500rb yang
  BERHASIL, yang berarti menaikkan `--max-stage-seconds` di atas 900s dulu
  (di luar scope sesi ini, murni keterbatasan waktu menjalankan sweep lebih
  lama, bukan hardware).

## Deliverable

| File | Isi |
|---|---|
| `app/machine-learning/src/perf.py`, `src/db_write.py` | Instrumentasi timing + COPY write path (TASK-P1/P3) |
| `faker/bulk_clone.py` | Jalur data cepat khusus performa, terkarantina (TASK-P3) |
| `perf/profile_scoring.py`, `perf/explain_queries.sql` | Profiling (TASK-P2) |
| `perf/benchmark_scale.py`, `perf/results/scale_sweep.csv` | Harness sweep + data mentah (TASK-P4/P6) |
| `perf/k6/read_endpoints.js`, `perf/results/k6_*.json` | Load test 5 endpoint baca, 2 sumbu (worker × volume data) (TASK-P7) |
| `perf/results/daily_scoring_20260812031341.pstats`, `explain_50k_2026-08-12.txt` | Hasil profiling mentah |
| `app/machine-learning/pipelines/restructuring_runner.py`, `src/feature_engineering.py` | Fix performa (TASK-P5) |
| `app/machine-learning/src/chunked_features.py` | Chunked read + agregasi (TASK-P5 item 1, sesi lanjutan) |
| `app/machine-learning/tests/test_features_chunked.py` | Parity test chunking (10 test) |
| `schema.sql` | 2 index baru (TASK-P5c) |
| `performance-report.md` | Dokumen ini |

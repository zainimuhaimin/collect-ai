# Bahan Presentasi — Area 1, 2, 3

> Kondisi sistem CollectAI **saat ini**. Detail teknis: `performance-report.md`
> (Area 1), `post-presentation-review-tasks.md`, `ai-reasoning-evaluation.md`
> (Area 3).
>
> **Mesin uji:** MacBook Apple M2, 8 core, RAM 16 GB.

---

# AREA 1 — Performance & Scalability

> **Intinya:** scoring harian 100.000 customer selesai **3 menit** dengan
> **1,5 GB RAM**. Volume terbukti jalan penuh: **250.000 customer**. Batasnya
> adalah **waktu proses**, bukan memori. Satu masalah kecepatan di halaman web
> sudah ditemukan dan belum diperbaiki.

## 1. Kapasitas pipeline (hasil ukur nyata)

| Customer | Total baris data | Training (4 model) | Scoring harian | Memori puncak | Database |
|---|---|---|---|---|---|
| **2.000** | 94.520 | 20 detik | 6 detik | 277 MB | 30 MB |
| **100.000** | 4,7 juta | 6 menit | 3 menit | 1,5 GB | 1,2 GB |
| **250.000** | 11,6 juta | 15 menit | 11 menit | 2,9 GB | 3,0 GB |
| **500.000** | 23,4 juta | ⛔ tidak selesai | belum diuji | — | ~6 GB |

Satu customer rata-rata jadi **±47 baris**: 1,5 kontrak + 14 pembayaran +
30 log interaksi penagihan. (Rincian per tabel ada di
`perf/results/scale_sweep.csv`.)

**Catatan:**
- **Training** dijalankan sesekali saat model perlu diperbarui, **bukan**
  harian. Yang harian adalah scoring.
- **500.000 customer**: datanya berhasil dimuat semua (23,4 juta baris), tapi
  training model pertama belum selesai dalam 15 menit (batas waktu pengujian)
  → dihentikan. Ini batas **waktu**, bukan memori.
- **Resource:** satu proses Python per pipeline, dijalankan berurutan (tidak
  paralel). XGBoost memakai beberapa core saat melatih. Postgres terpisah.

## 2. Batas kapasitas

| | Batas |
|---|---|
| Terbukti jalan penuh | **250.000 customer** (11,6 juta baris) |
| Batas waktu | Antara 250.000–500.000 customer |
| Batas memori (proyeksi) | ±1,7 juta customer sebelum RAM 16 GB penuh |

Untuk 5 juta customer perlu server dengan RAM lebih besar **dan** optimasi
waktu. Script pengujian sudah *hardware-agnostic* — langsung jalan di server
lebih besar tanpa diubah.

## 3. Uji beban halaman web (k6)

Ini pengujian **terpisah** dari pipeline: mengukur kecepatan halaman web saat
banyak orang membuka bersamaan. Konfigurasi: 50 pengguna bersamaan, 4 menit,
backend 4 worker.

| Yang dibuka pengguna | 2.000 customer | 100.000 customer |
|---|---|---|
| Halaman Dashboard | 0,7 detik | **92 detik** |
| Daftar customer | 0,2 detik | **19 detik** |
| Daftar kontrak | 0,1 detik | **53 detik** |
| Detail customer | 0,1 detik | **18 detik** |
| Detail kontrak | 0,06 detik | **17 detik** |
| Request per detik | 95 | 3 |
| Error | 0% | 0% |

*(angka = p95: 95% permintaan selesai lebih cepat dari itu)*

**Yang perlu disampaikan:**
1. Di 2.000 customer semua halaman cepat, **0 error**.
2. Di 100.000 customer semua halaman melambat drastis — tapi tetap **0 error**.
   Sistem tidak tumbang, hanya lambat.
3. **Penyebabnya sudah ditemukan:** query halaman daftar menghitung ulang
   seluruh data setiap kali dibuka, bukan hanya 20 baris yang ditampilkan.
4. **Belum diperbaiki** — ini prioritas perbaikan berikutnya, karena inilah
   yang pertama dirasakan pengguna kalau volume bertambah.
5. Menambah worker backend 1 → 4 **tidak menolong** (132 → 95 request/detik),
   karena hambatannya di query database, bukan kapasitas proses Python.

## 4. Cara demo langsung

```bash
# Sweep skala kecil (~5 menit)
cd perf && python benchmark_scale.py --rungs 5000,10000,25000 \
  --max-stage-seconds 300 --max-rss-gb 14 --min-free-disk-gb 3
cat results/scale_sweep.csv
```

Kolom yang ditunjukkan: `daily_scoring_s` (waktu), `peak_rss_*_mb` (memori),
`rows_*` (jumlah baris), `db_size_bytes` (disk).

```bash
# Uji beban API (backend harus jalan)
k6 run -e SAMPLE_CUST_ID=CUST-00001 -e SAMPLE_CONTRACT_NO=CTR-00001-1 \
  perf/k6/read_endpoints.js
```

⚠️ `benchmark_scale.py` **menghapus dan mengisi ulang database**. Jalankan
sebelum menyiapkan demo Area 2/3, jangan sesudahnya.

---

# AREA 2 — Day-to-Day Sync

> **Intinya:** skor AI terbukti **bergerak mengikuti perilaku nasabah**, bukan
> angka mati. Dalam simulasi 30 hari, 53% kontrak skornya naik, 31% pindah
> kategori risiko. Modelnya **dibekukan** selama simulasi, jadi perubahan skor
> murni dari data nasabah. Perubahannya **bisa dilihat langsung di web**.

## 1. Cara kerjanya — versi cerita

**① Siapkan hari pertama (D0).** Buat data nasabah, latih 4 model, hitung skor
untuk tanggal D0.

**② Bekukan modelnya.** Model tidak dilatih ulang lagi. Ini penting: kalau
model ikut berubah tiap hari, kita tidak bisa tahu skor berubah karena
nasabahnya atau karena modelnya.

**③ Majukan tanggalnya, hitung ulang.** Masukkan transaksi baru → hitung ulang
status kontrak → hitung skor lagi dengan model yang sama.

## 2. Cara kerjanya — alur teknikal

### Kenapa perlu tabel staging

Saat data dibuat, generator sekaligus menyiapkan **jadwal cicilan penuh**
(setiap angsuran beserta tanggal jatuh temponya, termasuk yang belum dibayar)
dan **semua transaksi sampai tanggal akhir** ke tabel *staging* (`stg_*`) —
belum masuk tabel live yang dibaca aplikasi. Setiap kali tanggal dimajukan,
hanya transaksi sampai tanggal itu yang "dilepas" masuk. Inilah yang membuat
waktu terasa benar-benar berjalan, bukan data diacak ulang.

### 6 tahap saat tanggal dimajukan

Angka waktu di bawah dari run nyata (500 customer / 711 kontrak, D0 1 Sep →
30 Sep). Total ±4,7 detik.

**Tahap 1 — Suap transaksi baru (incremental, bukan ulang dari nol)**

```sql
SELECT * FROM stg_payment_history
WHERE actual_pay_date > '<tanggal-sebelumnya>' AND actual_pay_date <= '<tanggal-ini>'
```

Query yang sama untuk `stg_lkp_interaction` (pakai `action_date`). Baris hasil
di-`COPY` (bukan INSERT satu-satu) ke `payment_history` dan `lkp_interaction`.
Hanya **selisih** antar tanggal yang masuk — jadi tabel live tumbuh bertahap
seperti data produksi yang datang harian. Run nyata: +435 pembayaran,
+484 log interaksi.

**Tahap 2 — Hitung ulang status kontrak** (`recompute_contract_state()`)

Ini inti "kenapa DPD berubah". Nilainya **tidak** diambil dari generator, tapi
dihitung ulang dari nol hanya dari dua bahan: jadwal cicilan vs pembayaran yang
sudah masuk.

| Field | Cara hitungnya |
|---|---|
| angsuran lunas (`k_paid`) | Jumlah jadwal jatuh tempo ≤ tanggal ini yang punya pembayaran `Full`/`Overpaid` |
| `overdue_installment_count` | Jumlah jadwal jatuh tempo ≤ tanggal ini yang **belum** lunas |
| `dpd_current` | **Selisih hari** antara tanggal ini dan jatuh tempo angsuran **tertua yang belum lunas** |
| `cycle` | Diturunkan dari jumlah tunggakan: 0→C0, 1→C1, 2→C2, ≥3→C3+ |
| `prnc_ots` (sisa pokok) | Formula anuitas: `principal × ((1+r)^tenor − (1+r)^k_paid) / ((1+r)^tenor − 1)` |
| `intr_ots` (sisa bunga) | `(tenor − k_paid) × cicilan − sisa pokok` |

Hasilnya ditulis ke `contract_snapshot` lewat **temp table + COPY + satu
`UPDATE ... FROM`** (bukan update baris per baris — 739 kontrak diperbarui
dalam satu perintah). Waktu: ±0,2 detik.

⚠️ Fungsi ini **sengaja tidak menyentuh sifat tersembunyi nasabah** (`w`/`c`)
— input satu-satunya adalah riwayat transaksi, persis seperti kondisi
produksi. Jadi perubahan DPD di sini bukan "dibocorkan" dari generator.

**Tahap 3 — Perbarui profil perilaku** (`update_cbs()`)

Hitung ulang fitur level nasabah (per batch 5.000 customer supaya hemat
memori), lalu perbarui `customer_behavioral_standing`: behavioral grade (A–D),
keandalan janji bayar, sensitivitas channel. Run nyata: 500 profil diperbarui.

**Tahap 4 — Kosongkan skor lama** — `TRUNCATE ai_intelligence_output`. Wajib
karena tabel ini hanya bisa menyimpan **satu tanggal aktif** (kunci utamanya
`contract_no`, bukan kontrak+tanggal).

**Tahap 5 — Scoring ulang** — `daily_scoring.py --date <tanggal>`

Ini pipeline produksi asli yang **tidak dimodifikasi** untuk simulasi. Di
dalamnya ada 9 langkah:

| # | Langkah | Yang terjadi | Waktu |
|---|---|---|---|
| 1 | `load_contract` / `load_customer` / `load_cbs` | Muat kontrak aktif, data nasabah, profil perilaku | 0,08 s |
| 2 | `feature_contract_chunked` | Hitung 36 fitur per kontrak, per batch 5.000 customer | 0,23 s |
| 3 | `enrich_and_fill` | Gabungkan fitur kontrak + profil perilaku nasabah | 0,01 s |
| 4 | `score_contracts` | **Inferensi ke-4 model XGBoost** pakai champion D0 yang dibekukan | 0,92 s |
| 5 | `confidence_level` | Hitung tingkat keyakinan tiap skor | 0,005 s |
| 6 | `business_rules` | Terapkan aturan bisnis: kategori risiko, rekomendasi NBA, prioritas | 0,01 s |
| 7 | `restructuring_assessment` | Susun tawaran restrukturisasi untuk yang memenuhi syarat | 0,79 s |
| 8 | `quality_check` | Validasi hasil (skor 0–1, kolom wajib terisi, tidak ada duplikat) | 0,003 s |
| 9 | `persist_output` | Tulis skor + snapshot fitur ke database | 0,04 s |

Langkah 4 inilah yang membuat skor berubah: fiturnya sudah berbeda (karena
tahap 1–3), tapi **modelnya sama persis** — jadi perubahan skor murni dari
perubahan data nasabah.

**Tahap 6 — Arsipkan ke riwayat**

```sql
INSERT INTO scoring_history (snapshot_date, contract_no, ...)
SELECT ai.scoring_date, ai.contract_no, ... FROM ai_intelligence_output ai
LEFT JOIN contract_snapshot cs ON cs.contract_no = ai.contract_no
ON CONFLICT (contract_no, snapshot_date) DO NOTHING
```

Skor hari ini disalin ke arsip yang **menumpuk** (tidak menimpa), digabung
dengan DPD & total OTS saat itu. Run nyata: 711 baris diarsipkan per tanggal.

### Kenapa ada dua tabel skor

| Tabel | Isi | Dipakai untuk |
|---|---|---|
| `ai_intelligence_output` | **Kondisi terkini saja** — 1 baris per kontrak | Dibaca aplikasi web |
| `scoring_history` | **Arsip semua tanggal** — 1 baris per kontrak per tanggal | Sumber laporan pergerakan |

## 3. Hasilnya bisa dilihat di web?

**Ya — sudah diuji lewat API sungguhan** (bukan query database), jadi ini
persis yang tampil di browser. Contoh kontrak `CTR-00004-1`:

| | D0 (1 Sep) | Setelah maju ke 30 Sep |
|---|---|---|
| recovery_score | 0,4037 | **0,5526** |
| Kategori risiko | Cannot Pay | **Can Pay** |
| Rekomendasi | Visit | **Deskcoll** |
| DPD | 66 | 95 |

Perhatikan: DPD-nya justru **naik** (66→95) tapi skornya ikut naik dan
kategorinya membaik. Ini contoh asli, bukan dipilih supaya rapi. Penyebabnya:
ada pembayaran baru masuk yang menaikkan sinyal "kemungkinan bayar", meski
tunggakan lama belum lunas. Bagus untuk didemokan karena menunjukkan model
tidak sekadar mengikuti DPD.

## 4. Hasil simulasi 30 hari (426 kontrak)

| Dalam 30 hari | Jumlah |
|---|---|
| Skor naik | 227 kontrak (53%) |
| Skor turun | 197 kontrak (46%) |
| Skor tidak berubah | 2 kontrak |
| Pindah kategori risiko | 130 kontrak (31%) |
| Rekomendasi penagihan berubah | 120 kontrak (28%) |

**Perpindahan kategori risiko (dari → ke):**

| dari \ ke | Can Pay | Cannot Pay | Won't Pay |
|---|---|---|---|
| **Can Pay** | 74 | 16 | 3 |
| **Cannot Pay** | 32 | 43 | 25 |
| **Won't Pay** | 24 | 30 | 179 |

Angka di luar diagonal = nasabah yang benar-benar berpindah kategori. Kalau
semua menumpuk di diagonal, artinya tidak ada pergerakan sama sekali.

**Kasus paling dramatis** — `CTR-00151-1`: skor **0,118 → 0,864**, kategori
**Won't Pay → Can Pay**, rekomendasi **Somasi → Deskcoll** (dari ancaman hukum
jadi telepon biasa).

## 5. Cara demo — versi tampil di web (paling meyakinkan)

**① Bersihkan database, siapkan D0, lalu berhenti:**

```bash
cd /Users/mcdmobiledev11/Development/MCD/collect-ai
./scripts/reset-demo.sh --yes
python scripts/simulate_days.py --dates 2026-09-01 --bootstrap-only \
  --horizon 2026-09-30 --customers 500 --seed 20260101
```

**② Buka web**, pilih satu kontrak, **catat skornya**.

**③ Majukan tanggal:**

```bash
python scripts/simulate_days.py --dates 2026-09-30 --continue
```

**④ Refresh halaman kontrak yang sama** → skornya sudah berubah. Bisa diulang
dengan tanggal lain untuk menunjukkan pergerakan bertahap.

## 6. Cara demo — versi laporan agregat

```bash
./scripts/reset-demo.sh --yes
python scripts/simulate_days.py --dates 2026-09-01,2026-09-08,2026-09-30 \
  --customers 500 --seed 20260101
python scripts/movement_report.py --out reports/movement_demo.md --top-n 10
open reports/movement_demo.md
```

Yang ditunjukkan dari laporan: tabel ringkasan → matriks perpindahan (pastikan
**tidak semua di diagonal**) → daftar "top mover", pilih satu untuk diceritakan.

## 7. Kalau ditanya

**"Kenapa modelnya tidak dilatih ulang tiap hari?"**
> Supaya bisa dibuktikan skor berubah karena perilaku nasabah, bukan karena
> modelnya berubah. Di produksi, pelatihan ulang mingguan tetap jalan normal —
> pembekuan ini khusus untuk pembuktian.

**"Datanya buatan, apa relevan?"**
> Yang dibuktikan adalah **mekanismenya bekerja** — skor benar-benar bergerak
> mengikuti transaksi. Angka persentasenya akan berbeda di data produksi.

---

# AREA 3 — AI Reasoning (LLM)

> **Intinya:** AI membaca seluruh kontrak satu nasabah lalu menyusun satu
> strategi penanganan. Diuji 4 lapis: **0 nomor kontrak fiktif**, dinilai
> **5/4/5/5** oleh AI independen, dan terbukti **tidak membeo** rule engine.
> Model ML-nya mencapai **AUC 0,91** terhadap kunci jawaban tersembunyi.
> Jumlah sampel masih kecil (4–8 nasabah) karena kuota API.

## 1. Apa yang dilakukan

Untuk satu nasabah dengan beberapa kontrak, AI membaca datanya (DPD, sisa
utang, riwayat bayar, dan 4 skor model) lalu menulis: ringkasan kondisi,
strategi penanganan, dan rekomendasi cara menagih.

## 2. Empat lapis pengujian

| Lapis | Mengukur | Hasil |
|---|---|---|
| **1. Cek fakta otomatis** | Apakah AI mengarang angka/nomor kontrak yang tidak ada di data | **0 kontrak fiktif**, angka cocok dengan data |
| **2. Dinilai AI lain** | Kualitas tulisan — dinilai model keluarga berbeda (GLM) supaya tidak menilai dirinya sendiri | **5/4/5/5** dari maksimal 5 |
| **3. Konsistensi** | Ditanya hal sama 3×, jawabannya sama? | Konsisten |
| **4. Kunci jawaban** | Akurasi terhadap kebenaran tersembunyi | Model ML **AUC 0,91** |

⚠️ **Sampel masih kecil (4–8 nasabah per lapis)** karena kuota API. Arahnya
positif, tapi belum cukup untuk klaim statistik.

## 3. Kenapa lapis 2 hanya bisa menilai kualitas, bukan akurasi

Penilai (AI lain) hanya diberi dua hal: **data mentah nasabah** dan **tulisan
AI pertama**. Dengan bahan itu:

| Pertanyaan | Bisa dijawab penilai? |
|---|---|
| Apakah klaimnya didukung angka yang ada di data? | ✅ Bisa |
| Apakah rekomendasinya konkret dan konsisten? | ✅ Bisa |
| Apakah nasabah ini benar-benar akan bayar bulan depan? | ❌ **Tidak bisa** |

Yang terakhir bukan soal kepintaran modelnya — **penilai tidak punya
informasinya**. Menilai akurasi butuh tahu **apa yang benar-benar terjadi
setelahnya**, dan itu hanya ada di lapis 4.

Dan begitu kunci jawaban tersedia, membandingkannya cukup dengan **perhitungan
biasa** — lebih murah, lebih cepat, dan hasilnya selalu sama (tidak seperti LLM
yang jawabannya bisa berbeda tiap dipanggil).

**Ringkasnya:** lapis 2 menjawab *"apakah AI jujur pada data?"*, lapis 4
menjawab *"apakah tebakannya benar?"*

## 4. Lapis 4 — kunci jawaban dari mana, dan AUC itu apa

### Dari mana kunci jawabannya

Data demo ini kami yang membuat. Saat membuat setiap nasabah, generator
**mengundi dulu dua sifat tersembunyi**, baru mengarang riwayat transaksinya
dari sifat itu:

| Sifat tersembunyi | Arti |
|---|---|
| **w** (*willingness*) | Seberapa **mau** dia bayar — disiplin/niat |
| **c** (*capacity*) | Seberapa **mampu** dia bayar — kemampuan finansial |
| **y_pay** | Apakah dia **benar-benar membayar** dalam 30 hari berikutnya (diundi dari w & c) |

**Ketiga angka ini TIDAK PERNAH masuk ke database.** Hanya disimpan di file
terpisah (`faker/_audit_latents.parquet`) yang tidak pernah dibaca sistem.
Sistem hanya melihat riwayat transaksi — sama seperti di produksi.

### Dua pengukuran yang dilakukan

**(a) Akurasi rule engine** — pakai kunci jawaban `w` & `c`:

| Sifat tersembunyi | Kategori seharusnya |
|---|---|
| Mampu tapi tidak mau | **Won't Pay** |
| Mampu dan mau | **Can Pay** |
| Tidak mampu (apa pun kemauannya) | **Cannot Pay** |

Kategori yang **ditebak rule engine** vs kategori **seharusnya** → tepat
**32%**.

**(b) Kalibrasi model ML** — pakai kunci jawaban `y_pay`:

`recovery_score` (tebakan model, 0–1) dibandingkan dengan `y_pay` (kenyataan
dia bayar atau tidak) → **AUC 0,91**.

### AUC 0,91 artinya apa

Ambil satu nasabah yang ternyata **bayar** dan satu yang ternyata **tidak
bayar**, acak. Berapa persen kemungkinan model memberi skor lebih tinggi ke
yang bayar?

| AUC | Artinya |
|---|---|
| 0,50 | Setara menebak dengan koin — tidak berguna |
| **0,91** | **91% pasangan diurutkan benar — sangat baik** |
| 1,00 | Sempurna (biasanya tanda kebocoran data, bukan model hebat) |

Jadi: dari riwayat transaksi saja, model berhasil memisahkan siapa yang akan
bayar dan siapa yang tidak — padahal jawabannya tidak pernah diperlihatkan saat
pelatihan. Sebagai konteks, model collection di industri umumnya 0,70–0,80.

## 5. Apakah AI cuma membeo rule engine?

Kekhawatirannya: kalau AI diberi tahu rekomendasi rule engine, mungkin dia
hanya menyalin. Diuji dengan mengirim dua versi data:

| | Dengan rekomendasi rule engine | Tanpa rekomendasi rule engine |
|---|---|---|
| Tingkat kesamaan dengan rule engine | 87,5% | 87,5% |

**Selisihnya nol.** Bahkan pada **7 dari 8 nasabah, rekomendasi AI sama persis**
baik diberi tahu maupun tidak → AI menyimpulkan sendiri dari data mentah, bukan
menyalin. **Kesimpulan: rekomendasi rule engine aman tetap dikirim ke AI.**

## 6. Temuan yang perlu disampaikan terbuka

Rule engine hanya **32% tepat** — di bawah tebakan acak terbaik (49%). Jangan
disembunyikan kalau lapis 4 ditampilkan; audiens teknis akan menemukannya
sendiri. Cara menyampaikannya:

> "Pengujian ini justru menemukan hal berharga: pendekatan berbasis aturan saja
> punya keterbatasan nyata. Inilah alasan kami membangun lapisan model ML
> (terbukti AUC 0,91) dan AI Reasoning di atasnya."

## 7. Cara demo langsung

**Lewat web:** buka halaman detail nasabah → klik **Generate** pada kartu AI
Reasoning → hasil muncul beberapa detik.

Syarat di `.env`:
```
AI_REASONING_ENABLED=true
GOOGLE_AI_STUDIO_API_KEYS=["<api-key-gemini>"]
```

⚠️ Setiap klik untuk nasabah baru memanggil API berbayar. Nasabah yang sudah
pernah di-generate memakai cache.

**Lewat terminal:**

```bash
python scripts/run_ai_reasoning_eval.py --limit 20          # lapis 1-3
python scripts/evaluate_tier4_oracle.py                     # lapis 4 (tanpa AI)
python scripts/ablation_nba.py --n 10                       # uji "membeo"
```

⚠️ Lapis 4 wajib memakai data yang dibuat dengan `--dump-latents`, dan harus
dari generate yang **sama** dengan isi database. Kalau database sudah
di-generate ulang, kunci jawabannya tidak cocok lagi — script akan
memperingatkan.

## 8. Naskah untuk audiens non-teknis (lapis 4)

> **Jangan sebut** istilah internal seperti "latent oracle" atau "variabel laten".

> "Bagaimana kita tahu penilaian AI ini benar?
>
> Di data produksi kita tidak pernah benar-benar tahu — harus menunggu
> berbulan-bulan untuk melihat siapa yang akhirnya gagal bayar.
>
> Tapi data demo ini kami yang membuat. Saat membuatnya, setiap nasabah kami
> beri dua sifat: seberapa disiplin dia membayar, dan seberapa mampu dia
> membayar. Kedua angka itu tidak pernah kami masukkan ke database — sistem
> hanya melihat riwayat transaksi, sama seperti di produksi.
>
> Artinya kami punya kunci jawaban, dan bisa menguji: dari riwayat transaksi
> saja, apakah sistem berhasil menemukan sifat asli nasabahnya?"

**Analogi:** "Seperti menguji dokter dengan pasien simulasi. Kami yang
menentukan penyakitnya; dokter hanya diberi gejalanya. Kalau diagnosisnya
tepat, itu bukan kebetulan."

**Kalimat pengunci:** "Nilai absolutnya bisa diperdebatkan. Yang tidak bisa
diperdebatkan adalah perbandingannya — rule engine dan AI diuji dengan kunci
jawaban yang sama persis."

## 9. Kalau ditanya

**"Sampelnya cuma 4–8, apa cukup?"**
> Belum cukup untuk klaim statistik, dan kami sampaikan apa adanya. Yang sudah
> terbukti: seluruh alat ukurnya bekerja dan arahnya positif. Menambah sampel
> hanya soal kuota API, bukan pekerjaan pengembangan lagi.

**"Kalau AI dan rule engine sering setuju (87,5%), bukankah itu bukti AI cuma
ikut-ikutan?"**
> Justru sebaliknya. Yang membuktikan kemandirian bukan tingkat setujunya, tapi
> bahwa angkanya **sama** baik rekomendasi rule engine ditampilkan maupun
> disembunyikan. Kalau AI membeo, menyembunyikannya akan menurunkan angka itu
> drastis — kenyataannya tidak turun sama sekali.

**"Kenapa tidak pakai penilaian kolektor senior sebagai pembanding?"**
> Itu paling ideal dan tetap kami rekomendasikan. Tapi penilaian manusia juga
> sebuah opini — dua kolektor senior bisa berbeda pendapat pada kasus yang sama.
> Kunci jawaban ini tidak ambigu dan bisa diterapkan ke ribuan kasus sekaligus.

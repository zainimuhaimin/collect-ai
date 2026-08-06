# CollectAI — "AI Reasoning" sebagai Mesin Hyper-Personalization Level Debitur

**Status: BELUM diimplementasikan.**

Revisi 2026-07-30 — dua perubahan mendasar dari draft sebelumnya:

1. **Grain berubah dari kontrak ke DEBITUR.** Requirement baru
   (*Hyper-Personalization*) mengubah tujuan fitur ini: dari "menganalisa risiko
   satu kontrak" menjadi "menentukan treatment yang konsisten untuk satu orang
   yang mungkin punya beberapa kontrak". Ini bukan penyesuaian kosmetik — ia
   mengubah kunci tabel, aturan staleness, bentuk payload, dan bentuk output.
2. **Payload draft sebelumnya sebagian tidak ada datanya.** Audit terhadap kode
   menemukan beberapa field yang dicontohkan tidak eksis, tidak pernah terisi,
   atau tidak mungkin dibangun. Bagian [Koreksi hasil audit](#koreksi-hasil-audit-kode)
   mendaftarkannya. Kabar baiknya: payload level-debitur justru **lebih mudah**
   dibangun, karena CBS memang benar-benar level customer dan sudah terisi.

---

## Ringkasan keputusan

| # | Keputusan | Status |
|---|---|---|
| 1 | LLM eksternal — **Google AI Studio (Gemini API)**, bukan self-hosted | Final |
| 2 | **On-demand + cache**, dipicu tombol manual di Customer Detail | Final |
| 3 | **Grain = DEBITUR (`cust_id`)**, bukan kontrak | **Baru** |
| 4 | Cache basi ketika **set `(contract_no, scoring_date)` debitur berubah** | **Baru** (menggantikan "scoring_date kontrak") |
| 5 | `primaryNbaAction` dibatasi ke **5 nilai nyata** sistem: `WA` · `Deskcoll` · `Visit` · `Somasi` · `Pickup` | **Direvisi** — daftar lama fiktif |
| 6 | Kartu "Target NBA Action" yang terpisah **dihapus**; NBA level-debitur muncul sebagai badge **di dalam** hasil AI Reasoning | **Baru** |
| 7 | Channel `SMS` **dihapus sepenuhnya** dari sistem, dilebur ke `WA` | **Selesai** — lihat §9 P0-1 |
| 8 | Latensi: **override `timeout` per-request (~30s)** di pemanggilan ky, bukan `202`+poll | **Baru** |
| 9 | **SEMUA kontrak aktif** dikirim tanpa truncation; kontrak lunas hanya sebagai ringkasan 3 tahun terakhir | **Baru** |
| 10 | **Gate kecukupan data** sebelum memanggil Gemini — status baru `INSUFFICIENT_DATA` | **Baru** |

---

## Koreksi hasil audit kode

Semua sudah diverifikasi langsung di codebase. Yang dikoreksi dari draft lama:

| # | Temuan | Dampak |
|---|---|---|
| 1 | **Enum `targetNbaAction` lama fiktif.** Domain `nba_recommendation` nyata hanya 5 nilai (`business_rules.py:27`, `:93-133`): `WA`/`Deskcoll`/`Visit`/`Somasi`/`Pickup`. Nilai seperti `"Personalized SMS Hook"` **nol tumpang tindih** dan tidak bisa dieksekusi sistem apa pun | Output LLM tidak bisa ditindaklanjuti. Sudah dikoreksi di keputusan #5 |
| 2 | **"Target NBA Action" di halaman customer bukan NBA level customer.** `customer_repository.py:242-249` mengambilnya dari kontrak dengan **OTS aktif terbesar** lewat `LEFT JOIN LATERAL ... ORDER BY total_ots DESC LIMIT 1`, lalu dilabeli sebagai atribut customer | Salah label untuk debitur multi-kontrak — inilah masalah yang memicu revisi ini. Sudah dikoreksi di keputusan #6 |
| 3 | **`payment_pattern_last_6_months` tidak ada.** Semua agregat pembayaran di `feature_engineering.py:166-222` bersifat *lifetime*, tanpa window | Dihapus dari payload |
| 4 | **`late_or_missed` tidak mungkin dibangun**, bukan sekadar belum dibangun. `payment_history` hanya berisi pembayaran yang **benar-benar terjadi**; `pay_status` hanya `Full`/`Partial`. Angsuran yang tidak dibayar **tidak punya baris** | Celah model data. Gunakan `dpd_current` + `overdue_installment_count` sebagai penggantinya |
| 5 | **`contact_summary_last_90_days` tidak ada window-nya.** Semua agregat LKP juga lifetime | Dihapus dari payload |
| 6 | **`most_responsive_channel` tidak ada per-customer.** Yang mirip, `channel_effectiveness` (`feature_engineering.py:440-457`), menjawab pertanyaan **berbeda**: channel yang paling sering *diikuti pembayaran* | Diganti `collection_sensitivity` dari CBS — yang memang level debitur |
| 7 | **`restructure_count` selalu 0.** `cbs_builder.update_cbs()` yang menghitungnya tidak punya pemanggil produksi; semua pipeline memakai `build_cbs()` polos yang jatuh ke fallback 0 (`cbs_builder.py:121-125`) | Jangan dikirim sebagai fakta — LLM akan menyimpulkan "belum pernah direstrukturisasi" |
| 8 | **`roll_forward_risk` tersimpan TERBALIK** — nilainya P(*tidak* bayar) (`scoring_engine.py:82-87`) | Key di payload wajib self-describing, kalau tidak arah interpretasinya jadi lotere |
| 9 | **3 probabilitas sub-model nullable**, dan `customer_repository.py:258-268` meng-coalesce NULL → `0.0` | "Tidak diketahui" terkirim sebagai "0%" ⇒ halusinasi yang terdengar yakin. Wajib pakai jalur repository terpisah |
| 10 | **CBS bisa jauh lebih basi dari skornya.** `daily_scoring.py:115-133` menulis CBS **hanya kalau tabelnya kosong** (`if df_cbs.empty:`) — bootstrap sekali, bukan refresh harian | Payload wajib menyertakan `cbs_as_of` |
| 11 | **`extra="ignore"` di `core/config.py:16`** — menaruh `GOOGLE_AI_STUDIO_API_KEY` di `.env` saja **tidak berefek**; wajib ada field di class `Settings` | Klaim "dotenv sama seperti PGPASSWORD" di draft lama salah mekanisme |
| 12 | **Timeout klien 10 detik** (`app/frontend/src/api/client.ts:8`, global, tanpa override per-route) | UX "loading beberapa detik" akan di-abort browser sementara backend tetap membayar. Wajib diputuskan, lihat [§7](#7-bentuk-rest--latensi) |
| 13 | **TASK-F Prompting Rules belum ada kodenya.** `model_governance_config` hanya punya satu `config_key` terpakai: `"cbs_weights"` (`governance_repository.py:21`) | Jangan blokir ke TASK-F, lihat [§9](#9-prasyarat) |
| 14 | **`SMS` hilang dari dua peta ranking channel** (`business_rules.py:27`, `feature_engineering.py:450`) padahal SMS channel nyata (~35% interaksi bucket C0) | Override `collection_sensitivity` **mati diam-diam** untuk nasabah SMS-preferring — jangkar hyper-personalization bocor. Diselesaikan dengan keputusan #7 |
| 15 | **Seluruh endpoint `/customers` tanpa autentikasi**, tidak ada dependency auth global di `main.py`/`api/v1/api.py` | Endpoint generate memicu panggilan **berbayar**. Dicatat sebagai risiko terbuka, lihat [§10](#10-risiko-terbuka) |
| 16 | **Debitur tanpa baris CBS di-grade `"D"` secara diam-diam.** `customer_repository.py:273` melakukan `behavioral_grade=row.behavioral_grade or "D"`. Karena CBS hanya ditulis saat tabelnya kosong (temuan #10), debitur baru **tidak punya baris CBS sama sekali** — dan `"D"` adalah grade TERBURUK. Terverifikasi: **38 dari 2.000 debitur (1,9%) tidak punya CBS** hari ini | LLM akan menyimpulkan "perilaku buruk, grade D" padahal kenyataannya **tidak ada data**. Halusinasi yang terdengar sangat yakin, dan menyasar justru debitur baru yang salah penanganan paling merugikan. Diselesaikan di [§8](#8-kecukupan-data--data-sufficiency) |
| 17 | **`historical_default_count` dan `income_debt_ratio` dipaksa `0` di jalur scoring.** `compute_customer_features()` menghitung keduanya dengan benar (`feature_engineering.py:431-438`, `:483`), tapi `daily_scoring.py:136` memperkaya fitur lewat `enrich_with_cbs()` — sementara `out_cols` di `cbs_builder.py:127-133` **tidak membawa keduanya**. Lalu `daily_scoring.py:141-147` memaksa `df_features[c] = 0`. Hasil perhitungan aslinya **dibuang** | Kelas bug yang sama dengan temuan #7. **Jangan kirim ke payload** — lihat [§1.1](#11-analisa-kelayakan-nba-level-kontrak-sebagai-input) |
| 18 | **`Pickup` tidak pernah bisa dihasilkan rule engine.** Cabangnya (`business_rules.py:101-104`) mensyaratkan `hist_default >= 2`, yang selalu `0` (temuan #17). Terverifikasi: **0 dari 2.817 kontrak** ber-NBA `Pickup`, padahal **63 kontrak memenuhi syaratnya** kalau `historical_default_count` benar-benar terisi (123 debitur punya 2 kontrak C3+, 9 punya 3) | `nba_spread` tidak akan pernah memuat `Pickup`, jadi `nbaAgreement` **selalu** `DIFFER` kalau LLM memilih `Pickup`. Harus disadari supaya metrik ketidaksepakatan tidak tercemar |

---

## 1. Konsep inti: Hyper-Personalization level debitur

### Masalah yang diselesaikan

Satu debitur bisa punya beberapa kontrak, dan `business_rules.py` menghitung
`nba_recommendation` **per baris kontrak** — dari `risk_segment` + `cycle` +
`total_ots` + `historical_default_count`. Konsekuensinya satu orang bisa punya
tiga rekomendasi berbeda sekaligus:

```
CUST-00029
├── CTR-00029-1  Rp 28 jt  DPD  12  Can Pay      → NBA: WA
├── CTR-00029-2  Rp 15 jt  DPD  95  Won't Pay    → NBA: Somasi
└── CTR-00029-3  Rp  2 jt  DPD  45  Cannot Pay   → NBA: Visit
```

Kalau ketiganya dieksekusi apa adanya, debitur ini menerima pesan WA yang ramah,
kunjungan lapangan, **dan** somasi — kemungkinan di hari yang sama. Selain
membuat debitur merasa dikejar tanpa koordinasi, itu memberi sinyal bahwa
sistemnya tidak terkoordinasi, dan debitur yang menyadarinya bisa
memanfaatkannya.

### Prinsip: channel satu per debitur, intensitas boleh beda per kontrak

Manusianya satu. Yang harus konsisten adalah **cara menghubunginya**; yang boleh
berbeda adalah **urgensi dan isi pesan** per kontrak.

| Dimensi | Grain | Sumber |
|---|---|---|
| Channel kontak | **Debitur — satu saja** | `collection_sensitivity` (CBS) sebagai jangkar + rekonsiliasi oleh LLM |
| Urgensi / prioritas | **Debitur — worst-case** | `MAX()` lintas kontrak aktif |
| Isi pesan / fokus | Per kontrak (boleh menyebut kontrak spesifik) | array `contracts` di payload |

Aturan **worst-case, bukan rata-rata**, untuk risiko: kalau satu kontrak sudah
C3+/Somasi, memperlakukan debitur dengan rata-rata "C1" akan menunda tindakan
yang seharusnya. Ada **preseden di codebase ini sendiri**: `priority`
level-customer di `dashboard_repository.py` dihitung `MAX()` di antara SEMUA
kontrak aktif, bukan dari satu kontrak arbitrer. Keputusan ini konsisten dengan
pola itu.

Sebaliknya untuk **skor agregat**, pakai **rata-rata berbobot OTS**: kontrak
Rp 28 juta dan Rp 2 juta tidak setara, dan rata-rata sederhana membuat kontrak
kecil ikut menarik keputusan.

### Fondasinya sudah ada separuh

`business_rules.py:109-115` sudah punya override level-debitur:

```python
sens = out["collection_sensitivity"]      # ← dari CBS, grain-nya CUSTOMER
nba_rank  = out["nba_recommendation"].map(CHANNEL_RANK).fillna(0)
sens_rank = sens.map(CHANNEL_RANK).fillna(0)
do_override = sens_rank > nba_rank        # upgrade-only
out.loc[do_override, "nba_recommendation"] = sens[do_override]
```

Jadi personalisasi level-debitur sudah dipraktikkan, hanya belum diangkat jadi
konsep eksplisit — ia cuma jadi *override* per-kontrak. Fitur ini
memformalkannya.

⚠️ **Tapi override ini rusak untuk nasabah SMS-preferring** (temuan audit #14):
`SMS` tidak ada di `CHANNEL_RANK`, sehingga `sens_rank` jatuh ke `0` dan
`do_override` **tidak pernah** true. Selama ini belum diperbaiki, jangkar
hyper-personalization bocor tanpa suara. Karena itu penghapusan SMS
([§9](#9-prasyarat)) adalah **prasyarat**, bukan pekerjaan sampingan.

### Pembagian tugas dengan NBA per kontrak

NBA per kontrak **tetap ada dan tetap rule-based** — ia masih dipakai di
Contract Detail dan tetap ditulis ke `ai_intelligence_output`. Yang baru adalah
lapisan di atasnya:

| | Grain | Mesin | Dipakai di |
|---|---|---|---|
| `nba_recommendation` | Kontrak | Rule-based (`business_rules.py`), deterministik, gratis | Contract Detail |
| `primaryNbaAction` | **Debitur** | LLM (fitur ini), merekonsiliasi konflik lintas kontrak | Customer Detail |

### 1.1 Analisa kelayakan NBA level kontrak sebagai input

**Verdict: layak dikirim, tapi 2 field harus dibuang dan 3 keterbatasan wajib
diketahui.** Alasannya: `nba_recommendation` adalah *pendapat sistem saat ini*, dan
untuk keperluan rekonsiliasi itu sudah cukup — kualitas turunannya tidak perlu
sempurna supaya `nba_spread` berguna. Yang tidak boleh terjadi adalah LLM
memperlakukan input yang **selalu nol** sebagai fakta.

#### Rantai aturan yang sesungguhnya berjalan

`apply_risk_segment()` (`business_rules.py:30-67`) → `apply_nba()` (`:69-135`):

```
risk_segment:
  Won't Pay   ← score < 0.30  AND (rejection_count >= N  OR  last_result <= 1)
  Cannot Pay  ← 0.30 <= score < 0.50  AND (broken_ptp > 0  OR  income_debt_ratio > 2.0)
                                                              └── SELALU 0 (temuan #17)
  Self-cure   ← score >= 0.70 AND dpd <= 7 AND payment_rate >= 0.80
                AND self_cure_probability >= 0.70
                    └── NULL kalau model self_cure belum dilatih
  Can Pay     ← default

nba_recommendation (base):
  Self-cure                      → WA
  Can Pay    + cycle <= 1        → WA
  Can Pay    + cycle >= 2        → Deskcoll
  Cannot Pay + cycle <= 1        → Deskcoll
  Cannot Pay + cycle >= 2        → Visit
  Won't Pay  + OTS < 5jt         → Visit
  Won't Pay  + OTS >= 5jt        → Somasi
  Won't Pay  + OTS >= 20jt + hist_default >= 2  → Pickup
                                  └── SELALU 0 ⇒ CABANG MATI (temuan #18)

lalu 4 override berurutan:
  1. collection_sensitivity (CBS)  → upgrade-only; mati utk SMS (temuan #14)
  2. self_cure_probability >= 0.70 → WA   (unconditional; mati kalau NULL)
  3. rpc_rate < 0.30               → Visit (hanya kalau rank saat ini < 3)
  4. days_to_maturity < 60 AND ambc < 2x cicilan → WA  (unconditional downgrade)
```

#### Yang benar-benar keluar — terverifikasi di 2.817 kontrak

| NBA | Jumlah | % |
|---|---|---|
| Somasi | 929 | 33,0% |
| Visit | 703 | 25,0% |
| WA | 601 | 21,3% |
| Deskcoll | 584 | 20,7% |
| **Pickup** | **0** | **0%** |

Silang dengan segmen:

| risk_segment | NBA yang muncul |
|---|---|
| Can Pay | WA 601 · Deskcoll 429 · Visit 386 |
| Cannot Pay | Visit 261 · Deskcoll 155 |
| Won't Pay | Somasi 929 · Visit 56 |
| **Self-cure** | **0 kontrak** |

#### Tiga keterbatasan yang wajib diketahui

**(a) `Pickup` mati, dan itu bukan karena tidak ada kandidat.** 63 kontrak
sebenarnya memenuhi syarat (Won't Pay + OTS ≥20jt + ≥2 kontrak C3+), tapi
`historical_default_count` dipaksa `0` sebelum aturannya dievaluasi. Jadi eskalasi
tertinggi **tidak pernah direkomendasikan sistem** — sebuah lubang kebijakan, bukan
sekadar bug teknis.

Konsekuensi untuk fitur ini: `nba_spread` tidak akan pernah memuat `Pickup`. Kalau
LLM memilih `Pickup`, `nbaAgreement` **selalu** `DIFFER`. Itu **tidak selalu salah**
— LLM justru bisa mengisi celah yang rule engine tidak sanggup jangkau. Tapi harus
disadari, kalau tidak metrik ketidaksepakatan jadi tidak bermakna.

**(b) Komposisi segmen bergeser drastis tergantung model mana yang terlatih.**
`Self-cure` mensyaratkan `self_cure_probability >= 0.70`; saat ini
**2.817/2.817 baris bernilai NULL** karena model `self_cure` belum dilatih. Efeknya
berantai: segmen `Self-cure` kosong **dan** override #2 mati. Artinya `nba_spread`
yang sama bisa berarti hal berbeda antara instalasi yang 4 model-nya lengkap versus
yang hanya `recovery`.

Ini yang membuat `cbs_as_of` saja tidak cukup — payload perlu memberi tahu LLM
**model apa yang tersedia**.

**(c) `Cannot Pay` berdiri di atas satu kaki.** Kondisinya
`broken_ptp > 0 OR income_debt_ratio > 2.0`, dan bagian kedua selalu `false`. Jadi
`Cannot Pay` efektif berarti *"pernah ada PTP yang gagal"* — bukan *"tidak mampu
bayar"* seperti namanya. `broken_ptp_count` sendiri **memang terisi** di jalur
scoring, karena dihitung ulang di `daily_scoring.py:158-161` (bukan dari CBS) — jadi
segmen ini valid, hanya lebih sempit dari yang tersirat namanya.

#### Keputusan untuk payload

**Dibuang — jangan dikirim sama sekali:**

| Field | Alasan |
|---|---|
| `historical_default_count` | Selalu `0` (temuan #17). Kalau dikirim, LLM menyimpulkan *"belum pernah gagal bayar berat"* — **salah sebagai fakta**, dan justru untuk 132 debitur yang sebenarnya punya ≥2 kontrak C3+ |
| `income_debt_ratio` | Selalu `0` (temuan #17). LLM akan membaca *"rasio utang terhadap penghasilan sangat sehat"* |

Ini kelas kesalahan yang sama dengan `restructure_count` (temuan #7): **field yang
selalu nol lebih berbahaya daripada field yang hilang**, karena nol terbaca sebagai
informasi.

**Ditambahkan — memperbaiki kualitas reasoning secara nyata:**

| Field | Kenapa |
|---|---|
| `nba_trigger` per kontrak (mis. `"Won't Pay + OTS >= 5jt"`) | Sekarang LLM menerima `nba_recommendation: "Somasi"` **tanpa tahu kenapa**. Dengan alasan pemicunya, LLM bisa menilai apakah alasan itu masih berlaku di level debitur — inilah bedanya merekonsiliasi versus menebak |
| `rejection_count`, `last_result_code` per kontrak | Dua input utama yang menentukan `Won't Pay`. Tanpa ini LLM tahu label segmennya tapi tidak tahu dasarnya, sehingga `keyFactors` jadi mendaftar ulang label bukan bukti |
| `available_models` di level atas (mis. `["recovery"]`) | Menjawab keterbatasan (b): LLM perlu tahu kalau `self_cure`/`roll_forward`/`ptp_success` belum tersedia, supaya tidak menyimpulkan dari ketidakhadiran mereka |

**Ditambahkan ke prompt** — satu baris yang menjaga LLM tidak memperlakukan output
rule engine sebagai kebenaran mutlak:

> `nba_recommendation` per kontrak adalah hasil rule engine deterministik dengan
> cakupan terbatas — ia tidak pernah menghasilkan `Pickup`, dan tidak mempertimbangkan
> portofolio debitur secara keseluruhan. Perlakukan sebagai *rekomendasi sistem saat
> ini* yang perlu Anda rekonsiliasi, bukan sebagai batas atas tindakan yang boleh
> Anda usulkan.

Kalimat terakhir itu penting: tanpa itu, LLM cenderung memilih salah satu nilai yang
sudah ada di `nba_spread` dan tidak akan pernah mengusulkan eskalasi yang justru
paling tepat untuk debitur dengan beberapa kontrak bermasalah.

---

## 2. LLM: Google AI Studio (Gemini API)

Eksternal API (bukan self-hosted) — konsekuensinya:

- Data customer **teragregasi** (bukan raw PII) terkirim ke server Google.
  Diterima sebagai keputusan sadar; dicatat di sini supaya ada jejaknya kalau
  ditanya audit/compliance. Lihat [§10](#10-risiko-terbuka) untuk penegakannya
  (niat saja tidak cukup).
- Karena bukan self-hosted, penyebutan **"Local LLM System Prompt"** di halaman
  AI Intelligence tidak akurat — sudah diantisipasi lewat rename ke "Prompting
  Rules" (`frontend-layout-upgrade-tasks.md` TASK-F).
- **API key**: `GOOGLE_AI_STUDIO_API_KEY` di `.env` root **plus field
  snake_case di class `Settings`** (`core/config.py`). Menaruhnya di `.env` saja
  tidak cukup — `extra="ignore"` membuatnya diabaikan (temuan #11). Preseden yang
  diikuti: `ml_python_interpreter`. Tambahkan placeholder ke `.env.example`.
- **Model Gemini**: varian "flash" sebagai default (murah, cepat), dengan opsi
  ganti ke "pro" lewat config. Nama model taruh di **satu** tempat saja.
- **Structured output**: pakai `responseSchema`/JSON mode — memaksa bentuk output,
  bukan "diminta baik-baik" lewat teks prompt. Tetap divalidasi ulang ke model
  Pydantic di backend; pelanggaran enum ⇒ `FALLBACK`, bukan `500`.
- **Feature flag `ai_reasoning_enabled` default `False`** supaya key yang belum
  ada menghasilkan respons "disabled" yang bersih, bukan error 500.

---

## 3. Timing & UI: on-demand + cache

**Desain kartu** di Customer Detail — background biru gelap, awalnya kosong
dengan satu tombol:

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│            [ Generate AI Reasoning & Analysis ]                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Perilaku:**

- Kosong secara default kalau belum ada reasoning ter-cache yang masih valid.
- Klik → loading state → isi kartu diganti hasil reasoning.
- Kunjungan berikutnya (selama cache masih valid): kartu **langsung menampilkan
  hasil ter-cache**, tanpa klik ulang.
- Pemanggilan generate **hanya saat tombol diklik** — tidak otomatis saat
  halaman dibuka.

**Kartu "Target NBA Action" yang terpisah dihapus** (keputusan #6). NBA
level-debitur muncul sebagai **badge di dalam** hasil AI Reasoning. Alasannya:
kartu itu sekarang menampilkan NBA kontrak terbesar yang **salah label** sebagai
atribut customer (temuan #2); dan karena NBA level-debitur hanya ada setelah
digenerate, mempertahankan kartu terpisah hanya akan menyisakan kartu kosong
menggantung. Satu tempat, satu sumber.

> **Konsekuensi yang perlu disadari:** sebelum ada yang klik Generate, halaman
> Customer Detail **tidak menampilkan next-best-action level debitur sama
> sekali**, dan angka itu jadi bergantung pada panggilan API berbayar. Ini
> trade-off yang dipilih secara sadar. Komponen yang dihapus/diubah:
> `app/frontend/src/components/AiBehavioralInsights.tsx:67-74`.
> `nba_recommendation` boleh tetap ada di response `GET /customers/{cust_id}`
> untuk keperluan lain, tapi **jangan** dirender sebagai NBA level customer.

---

## 4. Grain, cache & staleness

### Grain = `cust_id`

Tabel **`ai_reasoning_output`**:

| Kolom | Catatan |
|---|---|
| `id` | SERIAL PK |
| `cust_id` | **Grain-nya di sini**, bukan `contract_no` |
| `generated_at` · `source_signature` · `prompt_version` · `model_used` | — |
| `status` | `OK` · `FALLBACK` · `FAILED` · `RUNNING` · `INSUFFICIENT_DATA` |
| `insufficient_reason` | Alasan spesifik kalau `INSUFFICIENT_DATA` (mis. `NO_CBS`, `TOO_FEW_PAYMENTS`, `TOO_MANY_CONTRACTS`) — supaya bisa diagregasi jadi metrik cakupan |
| `summary` · `customer_treatment_strategy` | teks |
| `key_factors` · `recommended_actions` · `per_contract_focus` | JSONB |
| `primary_nba_action` · `nba_agreement` | — |
| `analyzed_contract_nos` | JSONB — kontrak apa saja yang ikut dianalisa |
| `latency_ms` · `prompt_tokens` · `completion_tokens` · `total_tokens` · `error_code` · `payload_bytes` | observabilitas & biaya |

`UNIQUE (cust_id, source_signature, prompt_version)` — bukan PK `cust_id` polos,
karena Model Health butuh rasio `OK`/`FALLBACK`/`FAILED` lintas waktu dan rate
limiting butuh menghitung regenerasi.

Ditambahkan ke `app/backend/db/schema_governance.sql` (backend-owned, alasan sama
dengan `model_governance_config`), pola `CREATE TABLE IF NOT EXISTS`. **Tidak ada
migration framework** — penambahan kolom nanti mengikuti pola
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` seperti `schema_v2.sql:38-42`.

### Staleness: signature lintas kontrak

Draft lama memakai "`scoring_date` kontrak berubah". Itu tidak cukup untuk grain
debitur — kontrak baru muncul atau kontrak lunas **tidak** mengubah `scoring_date`
kontrak lain, padahal komposisi portofolio debitur berubah dan reasoning-nya jadi
salah.

```
source_signature = hash( sorted( (contract_no, scoring_date) untuk SEMUA
                                  kontrak aktif milik cust_id ) )
```

Cache dianggap valid hanya kalau signature-nya identik. Ini otomatis membatalkan
cache ketika: skor diperbarui, kontrak baru ditambahkan, atau kontrak ditutup —
ketiganya memang harus mengubah rekomendasi treatment.

---

## 5. Payload input

Tiga lapis. **Setiap field di bawah sudah diverifikasi ada dan terisi.**

```json
{
  "cust_id": "CUST-00029",
  "as_of": "2026-07-30",
  "available_models": ["recovery", "self_cure", "roll_forward", "ptp_success"],

  "customer_profile": {
    "behavioral_grade": "C",
    "recovery_effort_level": "HIGH",
    "ptp_reliability_index": 0.40,
    "collection_sensitivity": "WA",
    "b_list_status": "N",
    "active_contract_count": 3,
    "total_active_ots": 45000000,
    "cbs_as_of": "2026-07-28T09:12:00"
  },

  "portfolio_rollup": {
    "worst_risk_segment": "Won't Pay",
    "worst_dpd": 95,
    "worst_cycle": "C3+",
    "ots_weighted_recovery_score": 0.38,
    "max_roll_forward_risk_prob_not_paying": 0.71,
    "nba_spread": ["WA", "Somasi", "Visit"],
    "contracts_in_arrears": 2,
    "arrears_ots_share": 0.82
  },

  "contracts": [
    {
      "contract_no": "CTR-00029-1",
      "product_type": "Multiguna",
      "dpd_current": 12,
      "cycle": "C0",
      "overdue_installment_count": 1,
      "installment_amount": 820000,
      "total_ots": 28000000,
      "late_fee_amount": 42000,
      "risk_segment": "Can Pay",
      "recovery_score": 0.66,
      "nba_recommendation": "WA",
      "nba_trigger": "Can Pay + cycle <= 1",
      "rejection_count": 1,
      "last_result_code": "PTP",
      "recent_payments": [
        {"due_date": "2026-06-05", "actual_pay_date": "2026-06-09",
         "pay_status": "Full", "delay_days": 4}
      ]
    }
  ]
}
```

### Kenapa bentuknya begitu

**`nba_spread` adalah field terpenting di seluruh payload.** Tanpa ini, LLM tidak
tahu ada konflik untuk direkonsiliasi — ia hanya akan mendeskripsikan ulang satu
angka. Dengan ini, tugasnya menjadi eksplisit: *"ada 3 rekomendasi berbeda,
tentukan satu yang konsisten dan jelaskan kenapa."*

**`collection_sensitivity` adalah jangkar personalisasi**, menggantikan
`most_responsive_channel` yang tidak ada (temuan #6). Ini memang preferensi
channel level debitur dari CBS.

**`cbs_as_of` wajib ada** karena CBS bisa jauh lebih basi dari skornya (temuan
#10) — LLM perlu tahu kalau profil perilakunya berumur beberapa minggu.

**`arrears_ots_share`** (porsi OTS yang menunggak) membedakan dua situasi yang
sangat berbeda: debitur yang kontrak kecilnya menunggak, versus yang kontrak
besarnya menunggak. Rata-rata biasa mengaburkan ini.

### Aturan NULL dan penamaan

- **3 probabilitas sub-model hanya disertakan kalau non-NULL** — lewat method
  repository khusus yang mengembalikan `Optional[float]`, **bukan** jalur
  `customer_repository.py:258-268` yang meng-coalesce ke `0.0` (temuan #9). Key
  dihilangkan sama sekali kalau NULL.
- `roll_forward_risk` **diganti nama** jadi
  `max_roll_forward_risk_prob_not_paying` karena tersimpan terbalik (temuan #8).
- **Tiga field TIDAK dikirim selama masih selalu 0** — `restructure_count`
  (temuan #7), `historical_default_count` dan `income_debt_ratio` (temuan #17).
  Lihat [§1.1](#11-analisa-kelayakan-nba-level-kontrak-sebagai-input): field yang
  selalu nol lebih berbahaya daripada field yang hilang, karena nol terbaca sebagai
  informasi.
- **`available_models`** memberi tahu LLM model apa yang tersedia. Tanpa ini, LLM
  tidak bisa membedakan "kemungkinan self-cure rendah" dari "model self-cure belum
  ada" — dan saat ini `self_cure_probability` NULL di **seluruh** 2.817 baris.

### Instruksi ke model

> Anda analis kredit yang membantu petugas collection di perusahaan multifinance
> Indonesia. Data JSON berikut adalah profil **satu debitur** yang mungkin
> memiliki beberapa kontrak.
>
> Tugas Anda: tentukan **satu strategi penanganan yang konsisten untuk debitur
> ini sebagai satu orang**, bukan rekomendasi terpisah per kontrak.
>
> Aturan wajib:
> - `primaryNbaAction` **HARUS** salah satu dari: `WA`, `Deskcoll`, `Visit`,
>   `Somasi`, `Pickup`. Hanya **satu** — debitur ini satu orang, tidak masuk akal
>   menghubunginya lewat beberapa channel bertentangan di waktu yang sama.
> - Kalau `nba_spread` berisi lebih dari satu nilai, itu berarti kontrak-kontraknya
>   punya rekomendasi berbeda. **Rekonsiliasi**, dan jelaskan alasannya di
>   `consistencyNote`.
> - Urgensi mengikuti kontrak **terburuk** (`worst_*`), bukan rata-rata.
> - Pertimbangkan `collection_sensitivity` sebagai preferensi channel debitur;
>   boleh menyimpang kalau tingkat keparahan menuntut, tapi sebutkan alasannya.
> - `payment_history` hanya mencatat pembayaran yang **terjadi**; angsuran yang
>   tidak dibayar TIDAK muncul sebagai baris. Nilai tunggakan dari `dpd_current`
>   dan `overdue_installment_count`, **jangan** disimpulkan dari jumlah baris
>   pembayaran.
> - Field yang tidak ada di JSON berarti **tidak tersedia** — jangan diasumsikan
>   nol, dan jangan mengarang angka yang tidak ada di input. `available_models`
>   memberi tahu model skor apa yang tersedia; skor dari model yang tidak terdaftar
>   memang tidak ada, bukan bernilai rendah.
> - `nba_recommendation` per kontrak adalah hasil **rule engine deterministik dengan
>   cakupan terbatas** — ia tidak pernah menghasilkan `Pickup`, dan tidak
>   mempertimbangkan portofolio debitur secara keseluruhan. Perlakukan sebagai
>   *rekomendasi sistem saat ini yang perlu Anda rekonsiliasi*, **bukan** sebagai
>   batas atas tindakan yang boleh Anda usulkan. `nba_trigger` menjelaskan kondisi
>   apa yang memicu rekomendasi itu — nilai apakah alasannya masih berlaku ketika
>   seluruh kontrak debitur dilihat bersamaan.
>
> Jawab dalam Bahasa Indonesia, ringkas, berbasis data yang diberikan.

---

## 6. Bentuk output

```json
{
  "summary": "Debitur memiliki 3 kontrak aktif dengan total OTS Rp 45 juta, dan 82% dari eksposur itu sedang menunggak. Kontrak CTR-00029-2 sudah mencapai DPD 95 (C3+) dengan segmen Won't Pay, sementara kontrak terbesarnya (CTR-00029-1, Rp 28 juta) masih relatif terkendali di DPD 12. Reliabilitas janji bayar tergolong rendah (0.40), dan grade perilaku C menunjukkan pola pembayaran yang tidak konsisten. Karena satu kontrak sudah masuk tahap yang menuntut tindakan formal, penanganan debitur ini tidak bisa lagi bertumpu pada pengingat lunak.",

  "customerTreatmentStrategy": "Tangani sebagai satu debitur dengan pendekatan kunjungan langsung, memakai kesempatan itu untuk membahas SELURUH tiga kontraknya sekaligus — bukan tiga upaya terpisah. Prioritaskan penyelamatan CTR-00029-1 yang nilainya terbesar dan kondisinya masih terkendali, sekaligus menegosiasikan CTR-00029-2 yang sudah kritis.",

  "keyFactors": [
    "82% dari total OTS Rp 45 juta sedang menunggak",
    "CTR-00029-2 sudah DPD 95 (C3+) — segmen Won't Pay",
    "Reliabilitas PTP rendah (0.40) — janji bayar sering tidak ditepati",
    "3 kontrak dengan rekomendasi berbeda (WA / Somasi / Visit) — perlu satu pendekatan"
  ],

  "primaryNbaAction": "Visit",
  "primaryNbaRationale": "Kontrak terburuk sudah C3+ sehingga pengingat WA tidak lagi memadai, tapi kontrak terbesarnya masih bisa diselamatkan — kunjungan memungkinkan negosiasi seluruh portofolio sekaligus, sebelum eskalasi ke somasi.",
  "nbaAgreement": "DIFFER",

  "perContractFocus": [
    {"contractNo": "CTR-00029-1", "urgency": "HIGH",
     "note": "Nilai terbesar dan masih terkendali — fokus utama penyelamatan, tawarkan penjadwalan ulang sebelum ikut memburuk."},
    {"contractNo": "CTR-00029-2", "urgency": "CRITICAL",
     "note": "Sudah C3+. Bahas dalam kunjungan yang sama; siapkan opsi restrukturisasi, eskalasi somasi kalau negosiasi gagal."},
    {"contractNo": "CTR-00029-3", "urgency": "MEDIUM",
     "note": "Nilai kecil (Rp 2 juta) — jangan jadi alasan kunjungan terpisah, cukup dibereskan bersama yang lain."}
  ],

  "consistencyNote": "Ketiga kontrak ditangani dengan satu kunjungan, bukan tiga channel berbeda. Mengirim WA yang ramah untuk satu kontrak sementara somasi berjalan untuk kontrak lain ke orang yang sama akan melemahkan posisi negosiasi dan merusak kredibilitas penawaran berikutnya."
}
```

### Field yang berubah dari draft lama

| Field | Perubahan |
|---|---|
| `targetNbaAction` → **`primaryNbaAction`** | Enum diganti ke 5 nilai nyata. Nama diubah supaya jelas ini **satu** channel untuk **satu** debitur |
| **`customerTreatmentStrategy`** | Baru — inti hyper-personalization: strategi level debitur, bukan analisa per kontrak |
| **`perContractFocus[]`** | Baru — urgensi + fokus per kontrak, tapi turunan dari satu strategi |
| **`consistencyNote`** | Baru — penjelasan kenapa kontrak berbeda ditangani dengan satu channel. Ini yang dibaca CS untuk menjelaskan ke debitur |
| **`nbaAgreement`** (`AGREE`/`DIFFER`) | Baru — apakah LLM sepakat dengan rule engine. Memberi metrik evaluasi gratis: tingkat ketidaksepakatan bisa dipantau di Model Health |
| `recommendedActions[]` | Tetap — langkah taktis bebas |
| `confidence_level` | Tetap tidak ditampilkan mentah ke user; dipakai internal untuk logging kualitas |

**Tampilan di kartu:** `summary` sebagai paragraf, badge `primaryNbaAction`,
`customerTreatmentStrategy` sebagai blok tersorot, bullet `keyFactors`, tabel
`perContractFocus` (kontrak + badge urgensi + catatan), `consistencyNote` sebagai
catatan kaki.

---

## 7. Bentuk REST & latensi

Draft lama punya kontradiksi: keputusan #2 menyatakan endpoint dipanggil "hanya
saat tombol diklik", tapi bagian `hasReasoning` menyuruh frontend mengambil cache
"lewat endpoint yang sama, dipanggil dengan **method yang sama**" — artinya POST
otomatis setiap halaman dibuka. Dipisah:

| Method | Endpoint | Perilaku |
|---|---|---|
| `GET` | `/api/v1/customers/{cust_id}/ai-reasoning` | Baca cache + `stale: boolean`. **Tidak pernah** memanggil Gemini, tidak pernah berbiaya. Aman dipanggil saat halaman dibuka. `404`/`204` kalau belum ada |
| `POST` | `/api/v1/customers/{cust_id}/ai-reasoning` | Generate. Hanya dari klik tombol. `201` hasil baru; `200` cache valid; `409`/`202` kalau generate lain sedang berjalan |

`hasReasoning`/`reasoningStale` di `GET /customers/{cust_id}` **dihapus** — GET di
atas sudah menjawab keduanya dalam round trip yang memang sudah dilakukan halaman.

### Latensi ✅ DIPUTUSKAN (keputusan #8)

**Override `timeout` per-request menjadi ~30 detik** di pemanggilan ky untuk route
ini saja. Timeout global 10 detik (`client.ts:8`) **tidak** diubah — mengubahnya
akan melonggarkan seluruh aplikasi demi satu endpoint.

Alasan memilih ini di atas pola `202` + poll:

- **Satu baris perubahan** di sisi frontend, tanpa state machine polling, tanpa
  endpoint status tambahan. Gemini Flash pada payload sebesar ini wajar selesai
  dalam hitungan detik, jadi kompleksitas polling belum terbayar.
- Guard konkurensi berbasis baris `RUNNING` (di bawah) sudah menangani kasus
  double-click, yang biasanya jadi alasan utama orang memilih polling.
- **Jalur eskalasi disiapkan, bukan diperdebatkan ulang nanti:** kalau p95 latensi
  ternyata melewati ~25 detik, pindah ke `202` + poll `GET` **memakai baris
  `RUNNING` yang sama** — jadi keputusan ini tidak mengunci apa pun. Tulis ambang
  itu sebagai kriteria pindah supaya tidak jadi debat baru.

Konsekuensi yang harus ditulis di kode: `httpx.Timeout` di backend wajib **lebih
kecil** dari 30 detik (mis. 25s) supaya backend menyerah lebih dulu daripada
browser — kalau terbalik, browser menutup koneksi sementara backend tetap
membayar panggilan sampai selesai.

**Eksekusi:** blocking di threadpool FastAPI (semua router sudah `def` sync,
`httpx` sudah ada di requirements). `httpx.Timeout` keras di bawah timeout klien;
retry **sekali** hanya untuk connect error/5xx/429, **tidak pernah** untuk read
timeout. Pola `threading.Thread` di `ai_intelligence_sync_service.py:178` **tidak**
cocok ditiru — itu job singleton multi-menit; reasoning per-debitur dan konkuren.

**Guard konkurensi:** insert baris `status='RUNNING'` sebelum memanggil Gemini;
baris `RUNNING` yang lebih muda dari timeout dianggap in-flight ⇒ `409`/`202`.
Tahan multi-worker uvicorn, yang lock in-process tidak.

---

## 8. Kecukupan data & data sufficiency

Dua hal yang dijawab di sini: **berapa banyak** kontrak yang dikirim (keputusan #9),
dan **apa yang terjadi kalau datanya terlalu sedikit** (keputusan #10).

### 8.1 Cakupan kontrak ✅ DIPUTUSKAN (keputusan #9)

**Semua kontrak AKTIF dikirim, tanpa truncation.**

Alasannya bukan soal biaya — ini soal kebenaran fitur. Janji inti
hyper-personalization adalah *"treatment konsisten berdasarkan profil keseluruhan
customer"*. Kalau kontrak aktif dipotong secara diam-diam, klaim itu jadi bohong:
LLM akan menyatakan strategi menyeluruh sambil buta terhadap sebagian eksposur.
Lebih buruk lagi, kontrak yang terpotong bisa justru yang paling parah.

Ternyata kekhawatiran payload membengkak **tidak nyata di data ini**. Terverifikasi
hari ini:

| Kontrak aktif per debitur | Jumlah debitur |
|---|---|
| 1 | 1.283 |
| 2 | 516 |
| 3 | 201 |
| **Maksimum** | **3** |

Jadi payload terbesar hanya berisi 3 kontrak. Tidak ada alasan teknis untuk
memotongnya.

**Instinct Anda soal "3 tahun ke belakang" tetap dipakai — tapi untuk kontrak
LUNAS, bukan kontrak aktif.** Pembagiannya:

| Kelompok kontrak | Yang dikirim | Alasan |
|---|---|---|
| **Aktif** (`closed_via_restructure=FALSE`, masih ada OTS) | **Seluruh detail, semuanya** | Ini himpunan yang menentukan keputusan treatment |
| **Lunas / ditutup**, 3 tahun terakhir | Hanya **ringkasan agregat**: `settled_contract_count`, `settled_total_amount`, `avg_settlement_delay_days` | Konteks perilaku, bukan objek keputusan. Detailnya sudah terwakili di `behavioral_grade` dan `ptp_reliability_index` yang bersifat lifetime |
| Lunas, >3 tahun | Tidak dikirim | Perilaku pembayaran 3+ tahun lalu tidak informatif untuk keputusan penagihan hari ini |

Ringkasan kontrak lunas ini penting untuk membedakan dua debitur yang skornya
identik hari ini: yang satu pernah melunasi 3 kontrak dengan bersih, yang satu
baru pertama kali. Keduanya layak diperlakukan berbeda.

**Safety valve — bukan batas normal, tapi penjaga anomali.** Kalau suatu debitur
punya lebih dari **15 kontrak aktif** (5x maksimum yang pernah ada), itu bukan
nasabah ritel biasa — kemungkinan besar akun korporat/fleet, atau ada masalah
integritas data. Dalam kasus itu:

- **Jangan truncate diam-diam.** Kembalikan `status='INSUFFICIENT_DATA'` dengan
  alasan eksplisit `TOO_MANY_CONTRACTS`, dan arahkan ke penanganan manual.
- Alasannya sama dengan di atas: analisa yang buta terhadap sebagian portofolio
  lebih berbahaya daripada tidak ada analisa, karena ia tampil dengan keyakinan
  yang sama.

`analyzed_contract_nos` di tabel output **wajib** mencatat kontrak apa saja yang
ikut dianalisa, supaya audit bisa membuktikan tidak ada yang tertinggal.

**Baris pembayaran per kontrak dibatasi 6 terakhir** (bukan 12), karena angka ini
dikali jumlah kontrak. Dengan maksimum 3 kontrak, itu 18 baris — cukup untuk
melihat pola, jauh dari batas ukuran apa pun.

### 8.2 Gate kecukupan data ✅ DIPUTUSKAN (keputusan #10)

**Ya, sangat mungkin datanya tidak cukup — dan itu sudah terjadi sekarang.**
Terverifikasi hari ini di 2.000 debitur:

| Kondisi | Jumlah | Akibat kalau tidak ditangani |
|---|---|---|
| **Tanpa baris CBS sama sekali** | **38** (1,9%) | Di-grade `"D"` (terburuk) secara diam-diam oleh `customer_repository.py:273` — lihat temuan #16 |
| `ptp_reliability_index` NULL (belum pernah janji bayar) | 189 (9,5%) | Kalau di-coalesce jadi 0, terbaca "janji bayar selalu gagal" |
| 0 baris pembayaran | 3 | Tidak ada pola pembayaran untuk dianalisa |
| ≤4 baris pembayaran | 173 (8,7%) | Pola terlalu tipis untuk kesimpulan perilaku |
| Tanpa interaksi LKP sama sekali | 1 | Tidak ada riwayat kontak/responsivitas |

**Kegagalan terburuk bukan "output kosong" — tapi narasi yang terdengar yakin di
atas nilai default.** Contoh nyata dari temuan #16: debitur baru tanpa CBS akan
membuat LLM menulis *"grade perilaku D menunjukkan pola pembayaran yang buruk"*,
padahal kenyataannya sistem belum tahu apa pun tentang orang itu. Dan ini menyasar
justru **debitur baru**, di mana salah penanganan paling merugikan — mereka bisa
diperlakukan sebagai kredit macet sejak hari pertama.

**Solusinya dua lapis.**

**Lapis 1 — jangan pernah kirim nilai default sebagai fakta.** Payload builder
**wajib memakai jalur repository sendiri**, bukan `get_customer_profile()`:

| Field | Perilaku yang benar |
|---|---|
| `behavioral_grade` | Hilangkan key kalau tidak ada baris CBS. **Jangan** `or "D"` |
| `ptp_reliability_index` | Hilangkan kalau NULL. **Jangan** jadikan 0 |
| `risk_segment` | Hilangkan kalau belum pernah discoring. **Jangan** `or "Can Pay"` |
| 3 probabilitas sub-model | Hilangkan kalau NULL (temuan #9) |

Plus satu baris di prompt (sudah ada di [§5](#5-payload-input)): *"field yang tidak
ada di JSON berarti tidak tersedia, jangan diasumsikan nol."*

**Lapis 2 — gate SEBELUM memanggil Gemini.** Hitung kecukupan data dulu; kalau
kurang, **jangan panggil sama sekali**:

```
data_sufficiency (dievaluasi sebelum call):
  ✓ ada baris CBS untuk cust_id ini
  ✓ total baris payment_history lintas kontrak aktif  >= 3
  ✓ ada minimal 1 baris ai_intelligence_output
  ✓ jumlah kontrak aktif <= 15
  ✓ months_on_book kontrak tertua >= 3

gagal salah satu ⇒ status='INSUFFICIENT_DATA', TIDAK memanggil Gemini
```

Dua manfaat sekaligus: **tidak membayar** panggilan yang hanya bisa menghasilkan
narasi kabur, dan **tidak menghasilkan halusinasi** yang terdengar meyakinkan.

Yang ditampilkan di kartu untuk `INSUFFICIENT_DATA` — jujur dan spesifik,
bukan error:

> **Data belum cukup untuk analisa AI**
> Debitur ini baru memiliki 2 riwayat pembayaran dan belum memiliki profil
> perilaku (CBS). Analisa AI membutuhkan minimal 3 riwayat pembayaran agar
> kesimpulannya dapat dipertanggungjawabkan.
> *Gunakan skor dan rekomendasi per kontrak di halaman Contract Detail sebagai
> acuan sementara.*

Perhatikan kalimat terakhir: **selalu arahkan ke alternatif yang tersedia.**
NBA per kontrak tetap rule-based dan tetap ada, jadi petugas tidak dibiarkan tanpa
pegangan. Kartu ini menampilkan tombol Generate lagi (bukan dinonaktifkan
permanen) supaya bisa dicoba lagi setelah data bertambah.

**Bedakan tiga status kosong** — ini yang sering dicampur dan membuat debugging
sulit:

| Status | Arti | Tindakan user |
|---|---|---|
| *(belum ada baris)* | Belum pernah digenerate | Klik Generate |
| `INSUFFICIENT_DATA` | Data debitur belum memadai | Tunggu data bertambah; pakai Contract Detail |
| `FALLBACK` | Data cukup, tapi Gemini gagal/timeout | Coba lagi |
| `FAILED` | Error teknis (key salah, quota habis) | Perlu tindakan admin |

`INSUFFICIENT_DATA` **tidak** dihitung sebagai kegagalan model di Model Health —
mencampurnya akan membuat metrik kesehatan terlihat buruk padahal sistemnya
bekerja benar. Tapi **jumlahnya tetap dilaporkan** sebagai indikator cakupan
(*coverage*): kalau 30% debitur tidak bisa dianalisa, itu temuan produk yang
penting, bukan sesuatu yang boleh disembunyikan.

> **Catatan yang lebih besar dari fitur ini:** akar masalah 38 debitur tanpa CBS
> adalah `daily_scoring.py:115-133` yang hanya menulis CBS kalau tabelnya **kosong**
> (`if df_cbs.empty:`) — bootstrap sekali, bukan refresh. Selama itu tidak
> diperbaiki, setiap debitur baru akan terus jatuh ke kategori ini dan jumlahnya
> **bertambah terus**. Perbaikannya di luar scope dokumen ini, tapi ini task yang
> layak diprioritaskan tersendiri karena juga memengaruhi kualitas fitur lain.

---

## 9. Prasyarat

### P0-1 — Hapus channel `SMS`, lebur ke `WA` (keputusan #7) — ✅ SELESAI (2026-08-06)

Dieksekusi penuh: migrasi `schema_v6.sql` (data lama + CHECK constraint),
`faker/generate-faker-realistic.py` (bobot direalokasi ke WA), `feature_engineering.py`
`RECOVERY_SOURCE_MAP` (diselaraskan dengan `CHANNEL_RANK`), backend
(`contract_service.py` icon map, `schemas/contract.py` contoh), frontend
(`contract.fixtures.ts`, `docs/api/07-contract.md`). Dataset diregenerasi penuh
(`--reset`, 2000 customer/2918 kontrak) dan ke-4 model dilatih ulang lalu
dipromosikan langsung ke champion (bukan lewat siklus shadow-scoring
`weekly_mlops.py` — regenerasi total dataset, bukan drift bertahap, jadi
perbandingan champion-lama-vs-data-baru tidak relevan).

Verifikasi: `payment_history.recovery_source` dan `lkp_interaction.treatment_type`
nol baris `SMS` (3.529 dan 12.244 baris lama berhasil dimigrasi/diregenerasi);
`override:collection_sensitivity` di `nba_trigger` sekarang 349 hit (sebelumnya
mati untuk nasabah SMS-preferring, temuan #14); NBA `Pickup` tetap hidup (56
kontrak); ML pytest 155/155, backend pytest 56/56.

Prasyarat, bukan pekerjaan sampingan: selama `SMS` hilang dari `CHANNEL_RANK`,
jangkar `collection_sensitivity` mati untuk nasabah SMS-preferring (temuan #14),
sehingga hyper-personalization bocor tanpa suara.

> **Trade-off yang diterima:** menghapus SMS dari data berarti informasi channel
> yang sebenarnya dipakai **hilang permanen** — tidak akan bisa lagi mengevaluasi
> apakah SMS berbeda performa dari WA. Ini dipilih secara sadar demi kesederhanaan;
> dicatat di sini supaya ada jejaknya.

**Urutan pengerjaan penting** — migrasi baris dulu, baru perketat constraint,
kalau tidak `ALTER` akan gagal:

1. `UPDATE payment_history SET recovery_source='WA' WHERE recovery_source='SMS'`
   dan hal yang sama untuk `lkp_interaction.treatment_type`.
2. Perketat CHECK: `schema_combined.sql:64` dan `schema_v2.sql:36` — buang `'SMS'`
   dari `recovery_source IN (...)`. Tambahkan sebagai `schema_v5.sql` mengikuti
   pola inkremental yang sudah ada.
3. `faker/generate-faker-realistic.py` — buang SMS dari `CHANNEL_MIX` (`:705-706`),
   `CHANNEL_CONTACT_EFFECT` (`:712`), hapus cabang forced-no-reply SMS (`:750`),
   dan `TREATMENT_TO_SOURCE` (`:877`). **Bobotnya harus direalokasi ke `WA`**,
   bukan sekadar dihapus — kalau tidak, total interaksi bucket C0 turun ~35% dan
   distribusi datanya berubah.
4. `app/machine-learning/src/feature_engineering.py:194` `RECOVERY_SOURCE_MAP` —
   buang `sms`, dan **selaraskan ordinalnya** dengan `CHANNEL_RANK`. Sekarang
   ketiga peta itu saling tidak konsisten.
5. `app/backend/services/contract_service.py:14` — hapus mapping `"SMS": "sms"`.
   `app/backend/schemas/contract.py:225-227` — perbarui contoh.
6. Frontend: `contract.fixtures.ts:97` (`recoverySources`), `:128`
   (`'Automated SMS Sent'`), dan **4 baris fixture yang memakai
   `nbaRecommendation: 'SMS Reminder'`** (`:54`, `:72`, `:84`, `:88`) — nilai itu
   fiktif, bukan bagian dari 5 nilai nyata.
7. Setelah selesai: jalankan ulang generator + `faker/validate_leakage.py`, lalu
   latih ulang model. Langkah 3 mengubah distribusi data, jadi model lama tidak
   lagi merepresentasikan datanya.

### P0-2 — Schema `ai_reasoning_output`

Lihat [§4](#4-grain-cache--staleness). Ke `app/backend/db/schema_governance.sql`.

### P0-3 — Field `Settings`

`google_ai_studio_api_key`, `gemini_model`, `gemini_timeout_seconds`,
`ai_reasoning_enabled: bool = False`, `ai_reasoning_daily_call_limit`. Wajib —
tanpa ini API key diabaikan (temuan #11).

### P0-4 — Prompt config tanpa menunggu TASK-F

Jangan blokir ke TASK-F yang belum ada kodenya (temuan #13). Buat
`services/ai_reasoning_prompt.py` dengan `PROMPT_VERSION = "v1"` dan set grup
aktif sebagai konstanta, plus override opsional dari `config_key` kedua
(mis. `"ai_reasoning_prompt"`) memakai pola JSONB get/put yang sudah ada di
`GovernanceConfigRepository`. Payload builder menerima `enabled_groups: set[str]`
sebagai parameter. TASK-F lalu tinggal "menampilkan key yang sudah ada di UI".

### P1 — Model Health placeholder

Mengganti placeholder adalah konsekuensi **dalam scope**, bukan follow-up.
`available: false` di-hardcode di 4 tempat: `app/backend/schemas/governance.py:46-57`,
wiring `api/v1/routers/ai_intelligence.py:39-41`, assertion
`tests/test_smoke.py:521-524`, dan
`app/frontend/src/domains/ai-intelligence/aiIntelligence.schema.ts:29-36` +
fixture-nya.

---

## 10. Risiko terbuka

1. **Endpoint berbayar di API tanpa autentikasi** (temuan #15). Seluruh route
   `/customers` terbuka tanpa token, tidak ada dependency auth global.
   **Ditunda secara sadar** — bukan prioritas pada iterasi ini karena keterbatasan
   waktu; dicatat di sini supaya ada jejak keputusannya dan tidak "hilang" begitu
   fitur dianggap selesai. Yang perlu diketahui saat memutuskan nanti: menambahkan
   `Depends(get_current_user)` **hanya pada POST** biayanya nyaris nol di sisi
   frontend, karena `client.ts:15-20` sudah mengirim bearer token di setiap request
   dan sudah menangani `401` secara global.

   Pengaman biaya di bawah ini **tetap dipasang sekarang** karena tidak menyentuh
   pola auth sama sekali — dan justru pengaman inilah yang menahan kerugian
   terbesar selama auth belum ada:
   - Tolak POST kalau sudah ada baris `OK` untuk `(cust_id, source_signature)`
     kecuali `force=true`; batasi jumlah `force` per debitur per signature.
   - Cap harian global lewat `ai_reasoning_daily_call_limit` ⇒ `429`. Catat
     interaksinya dengan `client.ts:11` yang me-retry **GET** pada 429 — limiter
     hanya untuk POST.
   - Simpan `prompt_tokens`/`completion_tokens`/`total_tokens` dari
     `usageMetadata` Gemini + `latency_ms`. Tanpa ini tidak ada cara menjawab
     "berapa biayanya".
   - Batasi ukuran payload: potong jumlah kontrak/baris pembayaran, assert ukuran
     maksimum, simpan `payload_bytes`. **Debitur dengan banyak kontrak membuat
     payload tumbuh linear** — ini spesifik untuk grain debitur.
   - Audit tiap generate ke `model_governance_audit_log` yang sudah ada
     (`action='AI_REASONING_GENERATE'`).
2. **PII ditegakkan, bukan diniatkan.** Builder hanya boleh mengeluarkan
   **whitelist** key, plus unit test yang memastikan `cust_name`/alamat/telepon
   tidak pernah muncul. `cust_id` dan `contract_no` dinyatakan sebagai identifier
   pseudonim yang diterima sebagai batasnya.
3. **Fallback harus terlihat sebagai fallback.** Template rule-based dari
   `risk_segment` + `nba_recommendation` boleh dipakai, tapi kembalikan `status`
   di response body dan render state "bukan hasil AI". Kalau tampil identik
   dengan output model, user akan membaca template sebagai penalaran model.

---

## Rancangan alur

```
User klik "Generate AI Reasoning & Analysis" di Customer Detail
        │
        ▼
POST /api/v1/customers/{cust_id}/ai-reasoning
        │
        ▼
services/ai_reasoning_service.py
        │
        ├─ hitung source_signature = hash(set (contract_no, scoring_date) aktif)
        │
        ├─ ada baris OK dengan signature + prompt_version sama? ──► kembalikan cache
        ├─ ada baris RUNNING yang masih muda?                  ──► 409 / 202
        │
        └─ tidak ada / basi:
                ├─ CEK data_sufficiency  ──gagal──► status='INSUFFICIENT_DATA'
                │  (ada CBS? >=3 pembayaran?         + insufficient_reason
                │   ada skor? <=15 kontrak?          TIDAK memanggil Gemini,
                │   months_on_book >=3?)             TIDAK ada biaya
                │
                ├─ insert baris status='RUNNING'  (guard konkurensi)
                ├─ kumpulkan payload 3 lapis:
                │     customer_profile   ← customer_behavioral_standing
                │     portfolio_rollup   ← agregat worst-case + bobot OTS
                │     contracts[]        ← contract_snapshot + ai_intelligence_output
                │                          + 12 pembayaran terakhir
                ├─ panggil Gemini (responseSchema) dengan httpx.Timeout keras
                ├─ validasi hasil ke model Pydantic
                ├─ update baris → status='OK' + token/latency
                └─ gagal → status='FALLBACK' (template rule-based) atau 'FAILED'
```

---

## Di luar scope dokumen ini

- Field `aiReasoning`/`aiRecommendations` terpisah di Collector Workbench —
  Workbench sudah dihapus total (`frontend-layout-upgrade-tasks.md` TASK-A),
  fungsinya melebur ke kartu ini.
- Isi system prompt final — diedit lewat Prompting Rules (TASK-F).
- Integrasi WhatsApp/Email template otomatis — fitur terpisah (outbound messaging).
- **Menghitung NBA level-debitur secara rule-based.** Sengaja tidak dilakukan:
  NBA level-debitur hanya berasal dari output AI (keputusan #6). Konsekuensinya
  sudah dicatat di [§3](#3-timing--ui-on-demand--cache).
- **Memperbaiki `restructure_count` yang selalu 0** dan 4 fitur ML lain yang
  selalu 0 (`delay_trend`, `historical_default_count`, `income_debt_ratio`,
  `broken_ptp_count`) — task tersendiri.

---

## Status pertanyaan terbuka

Ketiga pertanyaan dari revisi sebelumnya sudah dijawab:

| Pertanyaan | Status | Keputusan |
|---|---|---|
| Latensi: timeout atau `202`+poll? | ✅ Diputuskan | Override `timeout` per-request ~30s. Jalur eskalasi ke `202`+poll disiapkan dengan kriteria pindah p95 >25s ([§7](#7-bentuk-rest--latensi)) |
| Batas jumlah kontrak per payload | ✅ Diputuskan | Semua kontrak aktif, tanpa truncation — maksimum nyata di data hanya 3. Kontrak lunas cukup ringkasan 3 tahun. Safety valve 15 kontrak ⇒ manual ([§8.1](#81-cakupan-kontrak--diputuskan-keputusan-9)) |
| Postur auth endpoint berbayar | ⏸️ **Ditunda secara sadar** | Bukan prioritas saat ini karena keterbatasan waktu. Tetap dicatat sebagai risiko terbuka di [§10](#10-risiko-terbuka), dan pengaman biaya berbasis DB **tetap dipasang** karena tidak menyentuh pola auth |

### Yang tersisa sebagai keputusan implementasi (bukan blocker)

1. **Ambang `data_sufficiency`** di [§8.2](#82-gate-kecukupan-data--diputuskan-keputusan-10)
   (minimal 3 pembayaran, `months_on_book` ≥3) adalah angka awal yang wajar, bukan
   hasil kalibrasi. Setelah fitur jalan, lihat distribusi `INSUFFICIENT_DATA`: kalau
   terlalu banyak debitur terblokir, longgarkan; kalau ada output yang terasa kabur
   padahal lolos gate, perketat.
2. **Nama model Gemini** persisnya dicek saat implementasi, taruh di satu tempat.

### Hal di luar dokumen ini yang layak jadi task tersendiri

**`daily_scoring.py:115-133` hanya menulis CBS kalau tabelnya kosong.** Ini akar
dari 38 debitur tanpa CBS, dan jumlahnya **akan terus bertambah** selama tidak
diperbaiki — setiap debitur baru masuk ke kategori itu, lalu di-grade `"D"` secara
diam-diam oleh `customer_repository.py:273` (temuan #16). Dampaknya melampaui fitur
ini: `behavioral_grade` dipakai di daftar customer, dashboard, dan sebagai input
`business_rules`. Gate di [§8.2](#82-gate-kecukupan-data--diputuskan-keputusan-10)
mencegah AI Reasoning menghasilkan halusinasi karenanya, **tapi tidak memperbaiki
akarnya**.

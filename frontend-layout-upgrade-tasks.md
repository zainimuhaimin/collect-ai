# CollectAI Frontend — Layout & Menu Upgrade (Task List untuk Review)

**Status: BELUM diimplementasikan.** Revisi final — semua pertanyaan sudah terjawab. Tidak ada
kode yang diubah.

**Catatan soal RBAC:** sebelumnya sempat direncanakan jadi 2 dokumen terpisah
(`rbac-backend-tasks.md`, `rbac-frontend-tasks.md`, masih ada di repo). Arahan terakhir: **untuk
sekarang cukup tampilkan ke semua user login saja, belum perlu dikerjakan** — jadi kedua dokumen
itu **ditunda/on-hold**, tidak jadi bagian rencana implementasi saat ini. Detail di TASK-A.

Scope: **5 menu** — Dashboard, Customer, Contract, Restructuring Approval, AI Intelligence.
Performance dan Collector Workbench dihapus total.

---

## TASK-A: Sidebar — 5 menu ✅ **DIPUTUSKAN**

```
navItems = [
  { label: 'Dashboard',               icon: 'grid_view',    path: '/dashboard' },
  { label: 'Customer',                icon: 'people',       path: '/customers' },
  { label: 'Contract',                icon: 'description',  path: '/contracts' },
  { label: 'Restructuring Approval',  icon: 'fact_check',   path: '/restructuring-approval' },
  { label: 'AI Intelligence',         icon: 'psychology',    path: '/ai-intelligence' },
]
```

`PerformancePage.tsx`, `CollectorWorkbenchPage.tsx`, `domains/performance/`, `domains/workbench/`
— dihapus total.

**Restructuring Approval & AI Intelligence: tampil ke semua user login, tanpa pembatasan role.**
Ini final untuk sekarang (bukan sementara-menunggu-RBAC) — RBAC tidak dikerjakan di fase ini.

---

## TASK-B: Dashboard ✅ **DIPUTUSKAN**

- Contactability Funnel tetap, dibangun dengan data asli (agregasi `lkp_interaction`).
- Tabel "Broken PTP - High AMBC Priorities" dihapus dari Dashboard, pindah jadi filter di
  Customer (TASK-C) & Contract (TASK-D).
- Slot kosong diisi 2 card baru: **Restructuring Pipeline Snapshot** (jumlah offer per status
  GENERATED/OFFERED/ACCEPTED/REJECTED/EXPIRED) dan **Risk Segment Distribution** (proporsi
  Cannot Pay/Self Cure/Won't Pay).

Layout: 4 KPI tiles → DPD Buckets + Contactability Funnel → Restructuring Pipeline Snapshot +
Risk Segment Distribution (baris baru) → sync note.

---

## TASK-C: Customer — list (dengan paginasi) + kartu Restrukturisasi + list kontrak

### List Customer ✅ **DIPUTUSKAN**

Kolom: `name`, `dpdDays`, `amount`, `priority`, tombol Detail → `/customers/:id`.

Filter chip, single-select:

| Filter | Kondisi |
|---|---|
| `all` | tanpa filter |
| `dpd_30_plus` | `dpd_current >= 30` |
| `high_amount` | `priority` High/Critical |
| `broken_ptp` | customer punya ≥1 kontrak dengan `lkp_interaction.ptp_status = 'BROKEN'` terakhir |
| `high_ambc` | customer punya ≥1 kontrak dengan `contract_snapshot.ambc` di atas ambang tertentu |

(Di level Customer, `broken_ptp`/`high_ambc` berarti "punya kontrak yang..." karena atributnya
sebenarnya per-kontrak — konsekuensi wajar, bukan bug.)

**Paginasi ditambahkan:** query param `page` (1-indexed) + `pageSize`, response menyertakan
`pageInfo` (`showingFrom`, `showingTo`, `totalCustomers`, `totalPages`) — pola yang sama seperti
yang sebelumnya sudah dirancang di modul Performance lama (`GET /performance/collectors`).

### Customer Detail — kartu Opsi Restrukturisasi ✅ **DIPUTUSKAN**

Kartu baru menampilkan `eligibility_tier` + offer(s) dari `GET /customers/{cust_id}/restructuring-options`,
tombol **Terima**/**Tolak** memanggil `POST .../customer-response`. Aksi accept/reject **hanya ada
di sini** (Customer Detail), tidak diduplikasi di Contract Detail.

Tombol ini baru berfungsi penuh untuk tier `MANUAL_REVIEW` setelah **TASK-E (Restructuring
Approval)** dibangun — sebelum itu, offer tier `MANUAL_REVIEW` macet di status `GENERATED` dan
tombol akan selalu gagal `409`. UI perlu menampilkan state "Menunggu approval supervisor"
(disabled) selama `offer_status = GENERATED`.

Domain frontend baru (belum ada sama sekali): `src/domains/restructuring/*`.

### Customer Detail — GANTI Collection Activity Timeline jadi list Kontrak (expandable) ✅ **DIPUTUSKAN**

```
Kontrak Milik Customer Ini
┌──────────────────────────────────────────────────────────────────────────┐
│ ▸ CTR-00029-1   Personal Loan   DPD 45   Rp 12.500.000   [Cannot Pay]     │
│                                            [Lihat Detail Kontrak →]       │
│ ▾ CTR-00029-2   Multiguna       DPD 12   Rp 8.200.000    [Self Cure]      │
│                                            [Lihat Detail Kontrak →]       │
│   └─ Log Aktivitas Kontrak Ini (di-fetch saat expand diklik):             │
│      • 12 Oct 2023 — SMS terkirim ...                                     │
│      • 05 Oct 2023 — Broken Promise (PTP) ...                            │
└──────────────────────────────────────────────────────────────────────────┘
```

- Tiap baris: `contract_no`, `product_type`, `dpd_current`, outstanding, `risk_segment` (nilai
  **apa adanya** dari DB — `Cannot Pay`/`Self Cure`/`Won't Pay`, tidak diterjemahkan).
- Expand **lazy-load** (fetch log kontrak cuma saat baris pertama kali di-expand).
- Tombol "Lihat Detail Kontrak" → `/contracts/:contractNo`.

**Endpoint baru:** `GET /customers/{cust_id}/contracts` (list ringan kontrak milik customer),
`GET /contracts/{contractNo}/activity-log` (dipakai di sini DAN di Contract Detail penuh — 1
endpoint, 2 pemakai, supaya datanya selalu konsisten).

---

## TASK-D: Contract — list (dengan paginasi) + detail ✅ **DIPUTUSKAN**

List: kolom `contractNo`, `custId` (link ke Customer), `productType`, `dpdCurrent`, `outstanding`,
`riskSegment` (apa adanya dari DB), tombol Detail. Filter sama seperti Customer, single-select:
`all` / `dpd_30_plus` / `high_amount` / `broken_ptp` / `high_ambc` — di sini murni per-baris
(bukan agregat, karena `ambc`/`ptp_status` memang atribut kontrak).

**Paginasi ditambahkan**, pola sama seperti List Customer.

Detail — 7 bagian:
1. **Header** — `contract_no`, `product_type`, `cycle`, link ke Customer, badge kalau
   `closed_via_restructure = true`.
2. **Card Ringkasan Kontrak** — `loan_amount`, `installment_amount`, `interest_rate`,
   `maturity_date`, sisa tenor, `dpd_current`, `overdue_installment_count`, `late_fee_amount`,
   `ambc`, `prev_cycle`.
3. **Card Rincian Outstanding** — `prnc_ots`, `intr_ots`, total.
4. **Card AI Scoring** — `recovery_score`, `risk_segment`, `self_cure_probability`,
   `roll_forward_risk`, `ptp_success_probability`, `nba_recommendation`, `confidence_level`,
   `scoring_date` — langsung dari `ai_intelligence_output` (PK `contract_no`, tidak perlu agregasi).
5. **Tabel Riwayat Pembayaran** — dari `payment_history` filter `contract_no`.
6. **Collection Activity Timeline** — via `GET /contracts/{contractNo}/activity-log`.
7. **Card Status Restrukturisasi** — read-only, tanpa tombol aksi (aksinya cuma di Customer Detail,
   karena `restructuring_group_map` bisa mencakup >1 kontrak sekaligus untuk CONSOLIDATE).

---

## TASK-E: Restructuring Approval ✅ **DIPUTUSKAN**

Daftar grup restrukturisasi `offer_status = GENERATED` (+ tab histori OFFERED/REJECTED). Aksi:

- **Approve** → `GENERATED → OFFERED`
- **Reject** → `GENERATED → REJECTED`, **tanpa catatan/alasan wajib**.

**Audit log dikerjakan bersamaan** dengan endpoint approve/reject — mencatat siapa approve/reject
dan kapan (mengisi gap TASK-59 lama), bukan pekerjaan terpisah belakangan.

Endpoint: `GET /restructuring-groups?status=`, `POST /restructuring-groups/{group_id}/approve`,
`POST /restructuring-groups/{group_id}/reject`.

Role & Access: tampil ke semua user login (final untuk fase ini, lihat TASK-A).

---

## TASK-F: AI Intelligence — fase pertama: Bobot CBS

### Risk & Sub-model Threshold — DIHAPUS dari scope ✅ **DIPUTUSKAN**

Anda ragu dan condong menghapus section itu — saya sependapat, dengan alasan:

- Constant ini (`SCORE_THRESHOLD_WONT_PAY`/`CANNOT_PAY`/`SELF_CURE`, dst) menentukan `risk_segment`
  yang tampil di hampir semua halaman yang baru dirancang (list Customer, list Contract, Contract
  Detail, Dashboard Risk Segment Distribution). Mengubahnya bukan "geser 1 angka" tapi
  **mereklasifikasi seluruh portfolio secara instan** — dampaknya jauh lebih luas dan lebih sulit
  di-undo dibanding Bobot CBS (cuma 1 angka behavioral_grade per customer).
- QC (`QC_WONT_PAY_MAX_PCT` dkk) sudah ada khusus mendeteksi distribusi segmen yang janggal — kalau
  threshold ini bebas diubah lewat UI, ada risiko orang "memperbaiki" hasil QC yang gagal dengan
  menggeser cutoff-nya, bukan menyelidiki penyebabnya. Antipattern governance.
- Tidak ada RBAC (lihat TASK-A) — mengekspos sesuatu berdampak seluas ini tanpa kontrol akses lebih
  berisiko dibanding Bobot CBS.

**Kesimpulan: section ini dihapus dari scope.** Kalau nanti dibutuhkan, sebaiknya lewat proses yang
melibatkan sign-off data science, bukan slider UI biasa.

**Roadmap AI Intelligence yang tersisa:**
- **Fase 1 (sekarang):** Bobot CBS.
- **Fase 2 (menyusul, belum sekarang):** Restructuring Policy — tetap rekomendasi kuat saya karena
  `settings.py` sendiri eksplisit minta ini di-govern, dan dampaknya lebih terkontrol (per-offer,
  bukan re-label harian).

### Fase 1: Bobot CBS ✅ **DIPUTUSKAN**

| Konstanta | Untuk apa |
|---|---|
| `WEIGHT_PAYMENT_RATE` (0.30) | Pengaruh "rajin bayar tepat waktu" ke `behavioral_grade`. |
| `WEIGHT_PTP_RELIABILITY` (0.25) | Pengaruh "bisa dipegang janji bayarnya". |
| `WEIGHT_INTERACTION` (0.20) | Pengaruh "responsif saat dihubungi". |
| `WEIGHT_DELAY_SCORE` (0.25) | Pengaruh tren keterlambatan. |

### Prompting Rules — grouping "Data Fields Included" ✅ **DIPUTUSKAN (rekomendasi saya dipakai)**

Grouping per sumber data (bukan checklist per-field satuan), konsisten dengan tabel di
`ai-reasoning-api-upgrade-tasks.md`:

| Grup | Isi (contoh) | Default |
|---|---|---|
| ☑ Skor & Segmentasi Risiko | `recovery_score`, `risk_segment`, `self_cure_probability`, `roll_forward_risk`, `ptp_success_probability`, `nba_recommendation` | ON |
| ☑ Status Perilaku (CBS) | `behavioral_grade`, `ptp_reliability_index`, `b_list_status`, `restructure_count` | ON |
| ☑ Riwayat Pembayaran | pola bayar N bulan terakhir, `self_cure_flag`, `recovery_source` | ON |
| ☐ Riwayat Kontak/Interaksi | jumlah kontak, tingkat keberhasilan kontak, channel paling responsif, kept/broken PTP | OFF |
| ☐ Riwayat Restrukturisasi | pernah direstrukturisasi berapa kali, hasilnya | OFF |

2 grup terakhir default OFF supaya biaya token per panggilan LLM mulai dari yang paling relevan
dulu — bisa dinyalakan kalau hasil reasoning dirasa kurang kaya.

Sisanya (teks bebas system prompt, versioning terhubung ke `ai_reasoning_output.prompt_version`,
"Test Prompt Performance" jadi live-preview) tidak berubah dari revisi sebelumnya.

### Model Health ✅ **DIPUTUSKAN**

Gabungan health model scoring (`model_monitoring_log`: AUC, status drift) + health AI Reasoning
(`ai_reasoning_output.status` rasio OK/FALLBACK/FAILED).

### Implikasi arsitektur ✅ **DIPUTUSKAN: sekaligus**

Tabel `model_governance_config` (Postgres) **dibangun sekaligus** dengan fase 1 (Bobot CBS) —
bukan UI-di-atas-mock dulu. Slider Bobot CBS dari awal implementasi sudah baca/tulis ke tabel asli;
`settings.py` tetap jadi nilai default/seed saja.

### Role & Access

Tampil ke semua user login (final untuk fase ini, lihat TASK-A).

---

## Lampiran: Daftar Lengkap API Baru yang Dibutuhkan (untuk mulai kerja Backend)

### Sudah ada & berfungsi (beberapa perlu RESHAPE)

| Endpoint | Status |
|---|---|
| `POST /auth/login`, `GET /auth/me` | ✅ ada, sesuai kontrak, tidak berubah |
| `GET /customers` | ⚠️ perlu reshape: tambah `filter`/`search`/`page`/`pageSize` (TASK-C) |
| `GET /customers/{cust_id}` | ⚠️ perlu reshape total jadi 360° view (lihat `frontend-backend-api-gap-analysis.md`) |
| `GET /customers/{cust_id}/restructuring-options` | ✅ ada, sesuai kontrak |
| `POST /customers/{cust_id}/restructuring-options/{group_id}/customer-response` | ✅ ada, sesuai kontrak |

### Baru — Dashboard (TASK-B)

| Method & Path | Isi |
|---|---|
| `GET /dashboard/summary` | kpis, dpdBuckets, contactabilityFunnel + channelEfficiency, **restructuringPipelineSnapshot** (baru), **riskSegmentDistribution** (baru), syncNote. `brokenPtpPriorities` **dihapus** dari payload. |

### Baru — Customer (TASK-C)

| Method & Path | Isi |
|---|---|
| `GET /customers/{cust_id}/contracts` | list ringan kontrak milik 1 customer |

### Baru — Contract (TASK-D)

| Method & Path | Isi |
|---|---|
| `GET /contracts?filter=&search=&page=&pageSize=` | list kontrak, filter sama seperti Customer |
| `GET /contracts/{contractNo}` | detail penuh: ringkasan kontrak, outstanding breakdown, AI scoring, riwayat pembayaran, status restrukturisasi (read-only) |
| `GET /contracts/{contractNo}/activity-log` | dipakai 2 tempat: Contract Detail & expand di Customer Detail |

### Baru — Restructuring Approval (TASK-E)

| Method & Path | Isi |
|---|---|
| `GET /restructuring-groups?status=` | queue GENERATED (default) + histori OFFERED/REJECTED |
| `POST /restructuring-groups/{group_id}/approve` | GENERATED → OFFERED |
| `POST /restructuring-groups/{group_id}/reject` | GENERATED → REJECTED, tanpa body alasan |

### Baru — AI Intelligence (TASK-F, fase 1 saja)

| Method & Path | Isi |
|---|---|
| `GET /ai-intelligence/model-config` | Bobot CBS + Prompting Rules (teks + grup data field) + Model Health gabungan |
| `PUT /ai-intelligence/weighting-parameters` | simpan Bobot CBS (validasi total = 100%) ke `model_governance_config` |
| `PUT /ai-intelligence/prompting-rules` | simpan system prompt + toggle grup data field, naikkan `prompt_version` |
| `GET /ai-intelligence/operational-log` | audit log semua perubahan config di atas |

### Tabel/skema baru yang menopang semua di atas

- `model_governance_config` — key-value config Bobot CBS (dan nanti Restructuring Policy fase 2) + audit.
- Endpoint approve/reject di atas kemungkinan cukup pakai kolom `offer_status` yang sudah ada di
  `restructuring_recommendation_output`.
- `ai_reasoning_output` — dari `ai-reasoning-api-upgrade-tasks.md`, dibutuhkan Model Health.
- Audit log approve/reject (TASK-59 lama) — tabel baru, atau reuse audit log `model_governance_config`
  kalau strukturnya cocok.

Endpoint RBAC **tidak termasuk** daftar ini untuk sekarang — ditunda sesuai TASK-A.

---

## Catatan penutup

Tidak ada pertanyaan terbuka tersisa. Satu hal teknis kecil untuk fase implementasi nanti (bukan
keputusan produk): apakah `GET /contracts/{contractNo}` menyertakan riwayat pembayaran langsung di
payload yang sama, atau dipisah jadi endpoint sendiri seperti `activity-log`? Saya asumsikan
**digabung di payload yang sama** (riwayat pembayaran per kontrak biasanya jumlahnya kecil, tidak
butuh paginasi/endpoint terpisah) — beri tahu kalau mau dipisah juga.

# Frontend & Backend Refinement — Round 2 (DRAFT untuk direview)

> **Status: BELUM DIIMPLEMENTASI.** Dokumen ini murni hasil investigasi ground-truth
> (baca kode + DB schema langsung, tidak menebak) untuk 9 poin yang diminta. Tolong
> baca, koreksi asumsi yang salah, dan jawab pertanyaan terbuka di tiap task — baru
> setelah itu saya eksekusi.

---

## ⚠️ Temuan penting duluan (relevan untuk poin 3, 5, 6, 7)

**MSW mock masih AKTIF di frontend dev server Anda saat ini.**

Cek `app/frontend/.env.development`:
```
VITE_ENABLE_MSW=true
```
Dan `mocks/handlers/index.ts` meng-import `customerHandlers`, `dashboardHandlers`,
`contractHandlers`, `restructuringHandlers` — **semua module KECUALI Auth** masih
di-intercept oleh mock (`onUnhandledRequest: 'bypass'` di `main.tsx` cuma
membiarkan request `/auth/*` yang tidak match tembus ke backend asli).

Artinya: kalau Anda menjalankan `npm run dev` dengan `.env.development` default,
**Customer, Contract, Dashboard, Restructuring Approval, dan AI Intelligence yang
Anda lihat di browser saat ini adalah data mock/fixture buatan, BUKAN dari
Postgres Anda** — walaupun login (Auth) memang sudah ke backend asli. Ini
kemungkinan besar penyebab kecurigaan Anda di poin 6 (nama customer seperti "Budi
Pratama Sitorus" itu ADA di `mocks/fixtures/customer.fixtures.ts`, bukan hasil
karangan backend — backend asli tidak pernah mengirim nama seperti itu, lihat poin 6).

**Ini bukan salah satu dari 9 poin Anda, tapi saya rasa perlu jadi TASK-0** karena
semua perubahan UI di poin 3/5/6/7 tidak akan terlihat efeknya kalau frontend masih
baca dari mock. Saya usulkan **TASK-0: matikan MSW untuk module Customer/Contract/
Dashboard/Restructuring Approval** (set `VITE_ENABLE_MSW=false`, atau — lebih rapi —
kosongkan `handlers` array bertahap per-module sesuai pola yang sudah didokumentasikan
di `docs/api/README.md`), supaya UI benar-benar bicara ke backend asli sebelum kita
lanjutkan poin-poin di bawah. **Perlu konfirmasi Anda**: matikan MSW sepenuhnya
sekarang, atau tetap dipertahankan untuk sementara (misal AI Intelligence yang belum
lengkap)?

---

**✅ TASK-0 — Keputusan Anda: matikan MSW sekarang.** `VITE_ENABLE_MSW` di
`app/frontend/.env.development` diubah jadi `false`, supaya semua module
(Customer/Contract/Dashboard/Restructuring Approval/AI Intelligence) bicara ke
backend asli, bukan mock lagi.

---

## TASK-1 — Health check pindah ke `/`

**Kondisi saat ini:** `GET /api/v1/test` didefinisikan di
`app/backend/api/v1/routers/health.py`, di-mount lewat `api_router` dengan prefix
`/api/v1` (`main.py`). Dipakai oleh `tests/test_smoke.py::test_health` dan
didokumentasikan di `README.md`. Frontend tidak memanggilnya sama sekali (bukan
dependency siapa-siapa).

**Rencana:** Tambah route langsung di level `app` (bukan lewat `api_router`,
karena ini infra-level check, bukan bagian API v1 yang di-versioning):
```python
@app.get("/", tags=["health"], summary="Health check")
def root_health():
    return {"message": "Hello from backend"}
```
lalu **hapus** `GET /api/v1/test` dari `health.py` (sesuai kata "dipindah", bukan
ditambah endpoint baru), update `tests/test_smoke.py` dan `README.md` supaya
konsisten.

**✅ Keputusan Anda: diperkaya.** Response jadi:
```json
{"service": "CollectAI Backend", "status": "ok", "version": "<settings.app_version>"}
```

---

## TASK-2 — Sidebar fixed+collapsible, hapus profile duplikat, logout di top-right

**Kondisi saat ini (ground truth dari kode):**
- `components/Sidebar.tsx` — nav list biasa (`flex-1 px-4 space-y-1`), lalu di
  bagian bawah `<aside>` ada 3 hal berurutan: baris "System Status: Optimal",
  tombol "Support Hub", lalu blok Avatar+nama+role (ini yang Anda maksud
  "profile-me" di bawah).
- `components/TopBar.tsx` — blok Avatar+nama+role di kanan atas, tapi **statis**,
  tidak ada `onClick`, tidak ada dropdown/menu sama sekali hari ini.
- **Logout SUDAH ADA tapi tidak terpakai**: `auth/useAuthToken.ts` punya fungsi
  `logout()` yang meng-clear token, tapi tidak ada satupun komponen yang
  memanggilnya sekarang. Begitu dipanggil, `RequireAuth.tsx` otomatis redirect ke
  `/login` (mekanisme guard sudah jalan, tinggal dipicu).
- **Tidak ada** pattern collapse/expand sidebar yang sudah ada (bukan cuma belum
  dipakai — memang belum pernah dibuat), dan **tidak ada library dropdown/menu**
  apapun terpasang (`package.json` tidak ada Radix/Headless UI/dsb) — jadi
  dropdown profile perlu dibuat dari nol (state open/close + klik-di-luar-nutup).
- Sidebar saat ini **tidak fixed** — dia cuma `min-h-screen` di dalam parent
  `flex`, jadi ikut scroll bersama halaman (bukan scroll internal sendiri).

**Rencana implementasi:**
1. **Sidebar jadi fixed**: `sticky top-0 h-screen` pada `<aside>` (parent tetap
   `flex`, jadi tidak perlu geser konten pakai margin manual seperti kalau pakai
   `position: fixed`).
2. **Collapse/expand**: state boolean baru (`useState` + persist ke
   `localStorage`, pola yang sama dengan `auth/tokenStorage.ts`), lift ke
   `layouts/AppLayout.tsx` supaya bisa mempengaruhi lebar sidebar (`w-64` ↔
   `w-20`) dan konten sekaligus. Saat collapsed: label nav item disembunyikan,
   cuma ikon + tooltip nama saat hover.
3. **Hapus blok Avatar/nama/role di bawah Sidebar** (bagian "profile-me" yang
   redundan).
4. **TopBar jadi trigger dropdown**: bungkus Avatar+nama+role dengan
   `<button onClick={...}>`, render menu kecil (posisi absolute di bawahnya) berisi
   minimal 1 item: **Logout** → panggil `useAuthToken().logout()`.

**✅ Keputusan Anda (final, siap diimplementasi):**
1. **System Status + Support Hub — dipertahankan dulu**, cuma blok Avatar/nama/role
   yang dihapus dari Sidebar bawah.
2. **Logo "CollectAI" murni jadi toggle collapse/expand** — tidak lagi berfungsi
   sebagai link navigasi ke Dashboard (klik logo = cuma collapse/expand, bukan
   navigasi). Catatan: ini tidak menghilangkan akses ke Dashboard karena item nav
   "Dashboard" tetap ada di list menu seperti biasa.
3. **Dropdown profile berisi 2 item**: "Profil Saya" dan "Logout". Karena Anda
   tidak spesifikasikan detail "Profil Saya", saya usulkan default: klik item ini
   membuka **modal kecil read-only** (bukan halaman/rute baru) berisi data user
   yang sudah tersedia dari `/auth/me` — Name, Role, Username/initials — mirip
   info yang tadinya ada di blok profile Sidebar, cuma sekarang tampil on-demand
   lewat modal. Tidak ada form edit (tidak ada endpoint update-profile di backend
   hari ini). Kalau Anda maunya beda (misal halaman terpisah, atau field lain
   yang ditampilkan), tolong koreksi sebelum saya mulai.

---

## TASK-3 — Implementasi penuh Dashboard Summary di frontend

**Kondisi saat ini:** Frontend Dashboard dibangun berdasarkan dokumen kontrak API
lama (`docs/api/03-dashboard.md`) yang **berbeda struktur** dari response backend
asli sekarang. Ini bukan sekadar "kurang lengkap" — beberapa bagian betul-betul
tidak nyambung sama sekali kalau langsung disambungkan ke backend nyata. Rincian
per bagian:

| Bagian | Backend asli (`GET /dashboard/summary`) | Frontend sekarang | Status |
|---|---|---|---|
| KPI | `kpis`: 4 angka mentah — `total_outstanding`, `active_delinquent_accounts`, `self_cure_rate`, `manual_review_pending` | Array kartu dengan `value` (string sudah diformat), `change`, `trend` (naik/turun) — 2 di antaranya ("PTP Success Rate", "Avg AI Confidence") **tidak ada di backend sama sekali** | Perlu dirombak total |
| DPD buckets | `dpd_buckets[]`: `bucket, settled, active_ptp, broken, total` — selalu 4 baris (C0/C1/C2/C3+) | Field `total` diabaikan, dihitung ulang di client | Perlu pakai `total` asli dari backend |
| Contactability funnel | `contactability_funnel`: cuma 3 angka — `total_attempts`, `contacted`, `ptp_obtained` | UI sekarang render 4 tahap fiktif ("Attempts/Contacted/Engaged/Commitment") | Perlu dikurangi jadi 3 tahap real |
| Channel efficiency | `channel_efficiency[]`: **list** N channel (WA/SMS/CALL/dst), masing-masing ada `contact_success_rate`, diurutkan dari yang paling efektif | UI sekarang cuma render 1 objek "channel terbaik" | **Perlu widget baru** — list/ranking, bukan cuma 1 angka |
| Restructuring pipeline | `restructuring_pipeline_snapshot`: dict `{GENERATED, OFFERED, ACCEPTED, REJECTED, EXPIRED}` | Array `{status, count}[]` — isinya sudah cocok, cuma beda bentuk (dict vs array) | Perubahan kecil, tinggal adaptasi |
| Risk segment distribution | Nilai riil di DB: `Cannot Pay`, `Self-cure` (pakai strip), `Won't Pay`, `Can Pay` | Enum frontend cuma terima `Cannot Pay`/`Self Cure` (tanpa strip)/`Won't Pay` — **`Can Pay` tidak ada, dan ejaan `Self-cure` vs `Self Cure` beda** | Perlu perbaikan enum + tone warna utk segment ke-4 |
| Sync note | String siap-pakai, mis. "Data terakhir disinkronkan: 21 Jul 2026 17:07" | Field sudah cocok, cuma teks contoh beda bahasa/format | Cosmetic saja |
| Tombol "Export Report"/"Share Insight" | Tidak ada endpoint pendukung sama sekali | Ada di UI tapi tidak terhubung apapun | Perlu keputusan Anda (lihat pertanyaan) |

Selain itu, `dashboard.api.ts` saat ini memvalidasi JSON mentah langsung tanpa
mapper snake_case→camelCase — begitu backend asli dipanggil (setelah TASK-0),
request akan **gagal validasi Zod langsung**, bukan cuma tampil salah. Perlu
mapper (pola yang sama seperti `caseTransform.ts` yang sudah dipakai module lain).

**Rencana:** rombak `dashboard.schema.ts` mengikuti bentuk asli di atas, tambah
mapper di `dashboard.api.ts`, sesuaikan `DashboardPage.tsx` + komponen widget
(`StatCard`, `DpdBucketChart`, `ContactabilityFunnel`) mengikuti data asli, buat 1
widget baru untuk Channel Efficiency (list peringkat, bukan 1 angka), styling
tetap pakai card/style yang sudah ada (tidak redesign ulang).

**❓ Pertanyaan Anda: apa beda `self_cure_rate` (KPI) dengan segment "Self-cure"
(Risk Segment Distribution)? Kalau redundan, berikan opsi pengganti.**

Saya cek langsung kedua sumbernya — **ternyata TIDAK redundan, keduanya mengukur
hal yang beda secara fundamental**:

- **KPI `self_cure_rate`** (`dashboard_repository.py`) — ini angka **AKTUAL/histori**:
  ```sql
  SELECT count(*) FILTER (WHERE self_cure_flag) AS cured, count(*) AS total
  FROM payment_history
  WHERE due_date >= (MAX(due_date) - 30 hari)
  ```
  Artinya: dari seluruh **cicilan yang jatuh tempo 30 hari terakhir**, berapa
  persen yang **benar-benar sudah self-cure** (bayar sendiri tanpa perlu
  intervensi collector) — ini fakta yang sudah terjadi, dicatat di
  `payment_history.self_cure_flag`.

- **Segment "Self-cure"** (`risk_segment_distribution`) — ini **PREDIKSI/label
  model** per kontrak, dari `business_rules.py::apply_risk_segment`:
  ```python
  cond_self = (score >= SCORE_THRESHOLD_SELF_CURE) & (dpd <= MAX_DPD_FOR_SELFCURE)
            & (pay_rate >= MIN_PAYMENT_RATE_SELFCURE) & (prob_sc >= SELF_CURE_PROB_THRESHOLD)
  ```
  Artinya: dari seluruh **kontrak aktif saat ini**, berapa yang **diklasifikasikan
  model AI sebagai kemungkinan besar akan self-cure ke depan** (belum tentu
  terjadi, ini prediksi berdasarkan skor terbaru).

Ringkasnya: yang satu **"berapa % yang SUDAH self-cure bulan ini"** (fakta,
diukur per pembayaran), yang satu lagi **"berapa kontrak yang DIPREDIKSI akan
self-cure"** (prediksi, diukur per kontrak) — dua metrik yang saling melengkapi,
bukan duplikat. **Tidak perlu opsi pengganti** — tapi supaya tidak
membingungkan di UI, saya usulkan perjelas labelnya:
- KPI card: **"Self-Cure Rate (Aktual, 30 Hari Terakhir)"**
- Chip di Risk Segment Distribution: tetap "Self-cure" tapi dengan subtitle/tooltip
  kecil **"(Prediksi AI)"**

**✅ Keputusan Anda untuk pertanyaan lain di task ini:**
1. Tombol Export Report/Share Insight — **dibiarkan sebagai placeholder tidak
   aktif** (disabled, bukan dihapus).
2. Widget Channel Efficiency — **jalan dulu dengan UI rekomendasi saya**
   (ranked-list bar), nanti direview lagi dan direvisi kalau kurang cocok.

---

## TASK-4 — Beda `high_amount` vs `high_ambc`

Ini penjelasan lengkapnya (SQL asli, bukan tebakan):

- **`high_amount`** — ternyata **BUKAN** soal jumlah tagihan. Ini alias dari
  filter **priority** (`priority.py`):
  ```
  Critical = risk_segment='Cannot Pay' AND dpd_current>=90
  High     = risk_segment='Cannot Pay' OR dpd_current>=60
  ```
  `high_amount` = `priority IN ('High','Critical')`. **Nama filternya menyesatkan**
  — dia sama sekali tidak melihat kolom nominal/`ambc`.
- **`high_ambc`** — ini yang beneran soal nominal: kontrak yang `ambc`
  (Average Monthly Billing Cycle)-nya **di atas persentil-75 dari seluruh
  kontrak** (`percentile_cont(0.75) ... FROM contract_snapshot`) — angka batas
  ini dihitung dinamis dari data, bukan angka tetap.

**Rekomendasi saya:** ini bug penamaan, bukan cuma dokumentasi kurang jelas.
Saran: ganti label filter `high_amount` di UI (chip filter) jadi sesuatu yang
jujur soal isinya, misal **"Priority: High/Critical"** atau **"Critical Risk"**,
dan biarkan `high_ambc` diberi label yang jelas soal nominal, misal **"High
Billing Amount"**.

**✅ Keputusan Anda: ganti sekalian nama parameter API-nya juga** (bukan cuma
label UI). Usulan nama pengganti: **`high_amount` → `high_priority`** (paling
jujur mewakili isinya — priority Critical/High berdasarkan risk_segment+dpd),
label UI jadi **"Critical Risk"**. `high_ambc` dibiarkan seperti sekarang
(sudah jujur soal AMBC), label UI-nya diperjelas jadi **"High Billing Amount"**.

File yang perlu diubah konsisten (FE+BE bersamaan, karena ini breaking change
kecil di kontrak API):
- Backend: `_CUSTOMER_FILTER_SQL`/`_CONTRACT_FILTER_SQL` dict key di
  `customer_repository.py` & `contract_repository.py`, docstring router
  `customers.py`/`contracts.py`, `README.md` contoh curl, `tests/test_smoke.py`
  yang mereferensikan `filter=high_amount`.
- Frontend: enum filter di `customer.schema.ts`/`contract.schema.ts`, label chip
  filter di halaman list Customer & Contract, mock handlers/fixtures kalau ada
  yang mereferensikan `high_amount`.

**✅ Dikonfirmasi Anda — pakai nama `high_priority` seperti rekomendasi saya.**

---

## TASK-5 — Customer list: contract number & DPD

**Soal "contract number" di Customer list — dikonfirmasi Anda, memang sudah
tidak ada, diabaikan (selesai, tidak ada perubahan diperlukan).**

**Soal "DPD" di Customer list — ini konfirmasi kecurigaan Anda benar:**
`dpd_current` yang ditampilkan berasal dari **1 kontrak saja**: kontrak aktif
dengan **outstanding balance terbesar** milik customer itu (`DISTINCT ON (cust_id)
... ORDER BY total_ots DESC`) — bukan agregat, bukan kontrak paling telat. Kalau
customer punya 3 kontrak dan yang saldo-nya terbesar DPD-nya 10 tapi kontrak lain
DPD-nya 90, yang tampil di list ya 10. Kolom **"Amount" juga sama** — itu OTS satu
kontrak itu saja, bukan total gabungan (dokumentasi lama malah salah bilang ini
"total di semua kontrak" — kodenya tidak begitu).

**Rekomendasi saya:** setuju dihilangkan karena memang ambigu. Ganti dengan kolom
yang betul-betul level-customer (bukan bergantung ke 1 kontrak tertentu), yang
datanya sudah tersedia dari `customer_behavioral_standing`:
- **Active Contracts** (`active_contract_count`)
- **Behavioral Grade** (`behavioral_grade`)
- **B-List Status** (`b_list_status`)

Usulan kolom baru Customer list: **Name | Active Contracts | Behavioral Grade |
B-List Status | Priority | Detail**.

**Catatan penting yang perlu Anda putuskan:** kolom **Priority** yang saya usulkan
tetap dipertahankan itu **sebenarnya punya ambiguitas yang SAMA** — dia dihitung
dari `dpd_current` + `risk_segment` milik kontrak "terbesar" itu juga (lihat
`priority.py` + query di TASK-4). Jadi kalau alasan Anda menghapus DPD adalah
"jangan ambigu ke 1 kontrak", Priority secara teknis punya masalah yang sama,
cuma lebih tersamar karena sudah berbentuk label (Critical/High/Medium) bukan
angka mentah.

**✅ Keputusan Anda:**
1. **Setuju** — DPD dan Amount dihilangkan, kolom baru: **Name | Active
   Contracts | Behavioral Grade | B-List Status | Priority | Detail**.
2. **Priority diubah jadi level-customer** — "tampilkan priority TERBESAR dari
   seluruh kontrak yang dipunya customer" (bukan cuma dari kontrak
   bersaldo-terbesar seperti sekarang). Ini butuh query baru di
   `customer_repository.py`: untuk tiap customer, ambil MAX priority di antara
   semua kontrak aktifnya, dengan urutan **Critical > High > Medium** (pakai
   `CASE` ranking numerik lalu di-map balik ke label, karena `MAX()` biasa pada
   string tidak akan mengurutkan sesuai severity). Query filter `high_amount`/
   `high_priority` (TASK-4) juga perlu disesuaikan supaya konsisten pakai
   definisi Priority yang baru ini (EXISTS: customer masuk filter kalau **punya
   minimal 1 kontrak** dengan priority itu).

---

## TASK-6 — Konfirmasi data asli vs mock, dan soal nama customer

**Konfirmasi ground-truth:** saya cek schema `customer_master` langsung di
`app/machine-learning/config/schema_combined.sql` (file otoritatif untuk instalasi
baru) — kolomnya cuma: `cust_id, cust_age, cust_occupation, cust_income_level,
cust_region, cust_phone, cust_segment`. **Memang tidak ada kolom nama sama sekali**
— bukan hanya di tabel ini, saya cek semua tabel lain (`customer_behavioral_
standing`, `contract_snapshot`, dst) juga tidak ada field nama di manapun di
database. Backend asli **sudah jujur soal ini** — kodenya (`customer_repository.py`)
sengaja menaruh `cust_id` sebagai `name` dengan komentar eksplisit: *"customer_master
TIDAK punya kolom nama asli — pakai cust_id sebagai display label daripada
mengarang nama palsu."*

**Nama-nama seperti "Budi Pratama Sitorus" yang Anda lihat itu SUMBER-nya dari
`app/frontend/src/mocks/fixtures/customer.fixtures.ts`** (data hardcode untuk MSW
mock) dan dari `docs/api/02-customer.md` (dokumen contoh lama) — **bukan dari
backend/DB asli**. Ini menguatkan temuan MSW di atas (⚠️ di awal dokumen): kalau
`VITE_ENABLE_MSW=true`, Anda melihat data fiktif ini, bukan data Postgres Anda.

**✅ Keputusan Anda (mengubah rekomendasi awal saya): tambahkan kolom nama asli
ke `customer_master`, isi datanya pakai Faker (nama Indonesia).**

Rencana implementasi:
1. **Schema**: tambah kolom `cust_name VARCHAR(150)` ke `customer_master` di
   `app/machine-learning/config/schema_combined.sql` (definisi fresh-install),
   plus tambahkan statement `ALTER TABLE customer_master ADD COLUMN IF NOT
   EXISTS cust_name VARCHAR(150)` di `schema_v3.sql` (migrasi incremental) supaya
   DB yang sudah terlanjur jalan bisa di-upgrade tanpa drop tabel.
2. **Faker**: di `faker/generate-faker-realistic.py::generate_customer_master()`,
   tambah `'CUST_NAME': fake.name()` per baris (Faker locale `id_ID` sudah
   dipakai di file ini — `fake.name()` otomatis menghasilkan nama gaya
   Indonesia, tidak perlu locale baru).
3. **Backfill data yang SUDAH ada** — karena script faker saat ini jalan dengan
   `if_exists='append'` (nambah baris baru, bukan update baris lama), 500
   customer yang sudah ada di DB dev Anda sekarang tidak akan otomatis dapat
   nama hanya dengan menjalankan ulang script ini. Ada 2 opsi, **tolong pilih
   salah satu**:
   - **(a) Regenerate total** — kosongkan 4 tabel (`customer_master`,
     `contract_snapshot`, `payment_history`, `lkp_interaction`) lalu jalankan
     ulang `generate-faker-realistic.py` dari nol. Paling bersih, tapi
     menghapus seluruh data dev Anda saat ini (termasuk histori scoring yang
     sudah pernah dijalankan `daily_scoring.py`/`train_initial_model.py` —
     model & registry tidak perlu training ulang, tapi `ai_intelligence_output`
     akan kosong sampai scoring dijalankan ulang).
   - **(b) Backfill saja** — script kecil terpisah yang UPDATE `cust_name` untuk
     baris `customer_master` yang sudah ada (pakai `fake.name()` per baris),
     tanpa menyentuh tabel lain sama sekali. Lebih aman/tidak mengganggu data
     lain, tapi berarti ada 2 tempat kode yang menghasilkan nama (generator utama
     + script backfill terpisah).
   Karena ini DB **development lokal Anda** (bukan production — sudah
   dikonfirmasi sebelumnya), opsi (a) sebenarnya aman dieksekusi kalau Anda mau
   yang paling simpel. Saya tetap tanya dulu sebelum menjalankan salah satunya,
   sesuai kebiasaan kita untuk operasi yang mengubah/menghapus data.
4. **Backend**: update `customer_repository.py` — SELECT `cm.cust_name` di
   query list & detail, ganti `name=row.cust_id` jadi `name=row.cust_name`
   (dengan fallback ke `cust_id` kalau `cust_name` NULL, untuk baris lama yang
   belum ke-backfill kalau Anda pilih opsi (b) parsial), hapus komentar lama
   yang bilang "customer_master tidak punya kolom nama asli".
5. **Frontend/docs**: `customer.fixtures.ts` dan `02-customer.md` sudah pakai
   nama fiktif gaya Indonesia — begitu backend beneran mengembalikan nama asli
   dari DB (bukan `cust_id`), mock tidak perlu diubah lagi (sudah match secara
   bentuk, cuma beda nilai spesifik — itu wajar untuk data mock).

---

## TASK-7 — Restructuring Approval: ramping list, search, halaman detail

**Kondisi saat ini:**
- List sekarang render 8 kolom: Group ID, Customer, Kontrak, Offer Type,
  Eligibility (+ reasons ditampilkan inline), NPV Baseline→Restrukturisasi,
  Generated, Actions (Approve/Reject inline di baris) / Status.
- Search box **sudah ada secara visual** di TopBar tapi **tidak fungsional sama
  sekali** — tidak ada `onChange`/state, cuma dekorasi.
- **Belum ada halaman detail** (`/restructuring-approval/:id`) — dicek di
  `App.tsx`, rute ini belum ada. Pola serupa sudah ada di Customer & Contract
  (list+detail), jadi menambah 1 halaman detail baru untuk module ini mengikuti
  pola yang sudah dipakai, bukan pola baru.
- **Backend juga belum ada endpoint single-item** (`GET /restructuring-groups/{id}`)
  — hanya ada list dan approve/reject. Perlu ditambah kalau halaman detail mau
  bisa diakses langsung lewat URL/refresh (bukan cuma mengandalkan cache dari
  halaman list).
- **Ketemu 1 bug schema kecil** yang perlu ikut dibetulkan: field
  `eligibility_reasons` di backend itu `TEXT` tunggal (beberapa alasan digabung
  jadi satu string dengan pemisah `"; "` — lihat
  `restructuring_runner.py:307`), tapi frontend `restructuring.schema.ts`
  mendeklarasikannya sebagai `z.array(z.string())`. Backend sudah benar
  mengikuti DB — yang perlu diperbaiki adalah **schema frontend** (jadi
  `z.string()`, lalu di-split `"; "` di komponen kalau mau ditampilkan sebagai
  bullet list).

**✅ Rencana final (semua dikonfirmasi Anda):**
1. **List** — kolom disederhanakan jadi: **ID | Customer | Offered Type |
   Eligibility | Detail** (tombol/link ke halaman detail). Kolom yang di-drop:
   Kontrak, NPV Baseline/Restrukturisasi, Generated, Eligibility reasons (pindah
   ke detail), Actions inline (pindah ke detail).
2. **Search — server-side** (bukan client-side seperti usulan awal saya), sesuai
   arahan Anda: tambah param `?search=` ke `GET /restructuring-groups` (match ke
   `restructure_group_id` ATAU `cust_id`, pola sama seperti yang sudah dipakai
   Customer/Contract list). Ini juga sekalian menyamakan pola — Customer &
   Contract list **sebenarnya sudah punya** `search` param di backend hari ini;
   yang belum cuma Restructuring Groups, jadi ini melengkapi konsistensi 1-pola
   di semua API list, bukan menambah pola baru.
3. **Halaman detail baru** `/restructuring-approval/:id`, styling mengikuti pola
   Customer/Contract Detail yang sudah ada — menampilkan Group ID, Customer
   (link ke Customer Detail), daftar Contract, Offer Type, Eligibility tier +
   reasons lengkap, NPV Baseline vs Restrukturisasi (selisih ditonjolkan),
   Generated date, Status, dan tombol Approve/Reject (dipindah ke sini).
4. **Backend**: tambah `GET /restructuring-groups/{restructure_group_id}`.
5. **Fix schema**: `eligibilityReasons` di frontend jadi `z.string()`.

**❓ Pertanyaan Anda: "eligibility bukannya akan selalu manual review atau
generated aja ya?"**

Saya cek `pipelines/restructuring_runner.py` — **benar, ada nuansa penting di
sini**:
- Tier **BLOCKED tidak pernah disimpan ke database sama sekali** (baris
  komentar di kode: *"Batch tetap MENYIMPAN hasil untuk tier AUTO maupun
  MANUAL_REVIEW"* — BLOCKED sengaja dilewati karena tidak ada angka tawaran
  untuk disimpan). Jadi kolom `eligibility_tier` di tabel/endpoint ini **hanya
  akan pernah berisi `AUTO` atau `MANUAL_REVIEW`**, tidak pernah `BLOCKED`.
- Tier `AUTO` langsung ditulis dengan `offer_status='OFFERED'` (lompat, tidak
  pernah mampir ke status `GENERATED`). Tier `MANUAL_REVIEW` ditulis dengan
  `offer_status='GENERATED'`.
- **Konsekuensinya persis seperti dugaan Anda**: di antrean approval default
  (`status=GENERATED`, "menunggu approval"), kolom Eligibility **akan SELALU
  menunjukkan `MANUAL_REVIEW`** — karena `AUTO` sudah lompat ke `OFFERED` dan
  tidak pernah muncul di status `GENERATED`. Jadi di tampilan queue utama, kolom
  ini secara teknis konstan/tidak informatif. Kolom ini baru jadi variatif kalau
  Anda pindah ke tab History (yang menampilkan status lain seperti
  OFFERED/ACCEPTED/REJECTED, di mana baris ber-tier AUTO juga akan muncul).

**✅ Keputusan Anda: tetap tampilkan** kolom Eligibility di kedua tab (queue
utama maupun History), meski di tab utama nilainya akan selalu "MANUAL_REVIEW".

---

## TASK-8 — Contoh kasus restrukturisasi (input → output)

Saya jalankan langsung kalkulator asli (`app/shared/restructuring_offer_calculator.py`)
dengan input realistis untuk menunjukkan alurnya:

**Input** — 1 kontrak, tanpa kontrak lain (tidak eligible CONSOLIDATE), tanpa
appraisal aset (tidak eligible TAKEOVER):
```
Kontrak Motor, outstanding Rp12.000.000, bunga 24%/tahun, sisa tenor 12 bulan
Cicilan saat ini Rp1.150.000/bulan, DPD 10 hari, risk_segment = "Cannot Pay"
recovery_score = 0.30 (peluang tertagih rendah), self_cure_probability = 0.15
Belum pernah direstrukturisasi, tidak masuk blacklist, cuma 1 kontrak aktif
```

**Langkah 1 — Cek eligibility** (`classify_eligibility`):
- Tidak BLOCKED (data valid semua).
- Cek syarat MANUAL_REVIEW satu-satu: segmen Cannot Pay → oke (lolos), tidak
  blacklist → oke, self_cure_probability 0.15 < 0.70 → oke, restructure_count
  0 < 2 (limit) → oke, **TAPI** DPD harus di rentang 30–180 untuk masuk jalur
  otomatis — **DPD 10 di luar rentang itu**, jadi ini yang membuatnya masuk
  **MANUAL_REVIEW** dengan alasan: `"DPD 10 di luar window standar (30-180)"`.
- Kalau AUTO, tawaran akan langsung berstatus OFFERED (lewat approval). Karena
  MANUAL_REVIEW, statusnya jadi GENERATED — inilah yang muncul di antrean
  Restructuring Approval untuk direview supervisor.

**Langkah 2 — Hitung tawaran REFINANCE** (satu-satunya jenis yang mungkin di
sini, karena tidak ada kontrak lain/appraisal):
- Perpanjangan tenor: `min(24, 12 × 50%) = 6 bulan` → tenor baru **18 bulan**
- Potongan bunga: `24% × (1 − 40%) = 14,4%` (masih di atas batas minimum 9%)
- Cicilan baru dihitung ulang dengan formula anuitas atas pokok yang sama

**Langkah 3 — Guardrail** (satu-satunya syarat: NPV hasil restrukturisasi harus
lebih besar dari NPV kalau dibiarkan apa adanya):

**Output nyata (hasil jalan langsung, bukan simulasi manual):**
```
Eligibility: MANUAL_REVIEW — "DPD 10 di luar window standar (30-180)"

Tawaran REFINANCE:
  Tenor baru        : 18 bulan (dari 12 bulan)
  Bunga baru        : 14,4% (dari 24%)
  Cicilan baru      : ± Rp745.233/bulan (dari Rp1.150.000)
  NPV kalau dibiarkan (baseline)     : ± Rp3.883.002
  NPV kalau direstrukturisasi        : ± Rp12.220.536
  Lolos guardrail (NPV lebih baik)   : YA
```
**Kesimpulan dalam bahasa awam:** customer telat 10 hari di kontrak motor
Rp12 juta (24%/12 bulan sisa) → karena DPD-nya belum masuk rentang standar
restrukturisasi otomatis (30–180 hari), sistem tetap menghitungkan tawaran
(tenor jadi 18 bulan, bunga turun ke 14,4%, cicilan turun ke ±Rp745rb/bulan),
tapi **menunggu supervisor approve dulu** sebelum ditawarkan ke customer —
inilah baris yang muncul di Restructuring Approval queue (TASK-7), dan semua
angka ini (NPV baseline/restrukturisasi, reasons, tenor/rate baru) adalah data
yang seharusnya tampil lengkap di halaman detail yang diusulkan di TASK-7.

**❓ Pertanyaan Anda: kenapa jaraknya jauh sekali (Rp3,88 juta → Rp12,22 juta)?
Apakah sisa yang belum dibayar tidak dihitung? Bukankah customer dirugikan
(cicilan turun dari Rp1.150.000 ke Rp745.233)?**

Jawaban singkat dulu: **customer TIDAK dirugikan** — justru sedikit diuntungkan.
Kenapa cicilan turun tapi angka NPV perusahaan malah naik 3× lipat, itu 2 hal
yang beda sebabnya. Saya jelaskan satu-satu, sudah saya cek ulang persis ke kode
`calculate_installment`/`npv_of_installments`/`apply_guardrail`:

**1. Soal "sisa yang belum dibayar" — sudah dihitung penuh, tidak ada yang
hilang.** `calculate_installment()` pakai formula anuitas standar: cicilan baru
dihitung dari **seluruh pokok pinjaman (`total_ots`) yang sama**, cuma
tenornya diperpanjang (12→18 bulan) dan bunganya diturunkan (24%→14,4%). Total
nominal yang akan dibayar customer:
- **Skema lama**: Rp1.150.000 × 12 bulan = **Rp13.800.000**
- **Skema baru**: Rp745.233 × 18 bulan = **Rp13.414.200**

Selisihnya cuma ~Rp386 ribu (≈2,8%) lebih murah di skema baru — **secara
nominal total, customer membayar hampir sama, bahkan sedikit lebih murah**,
cuma dicicil lebih ringan per bulan karena tenornya lebih panjang dan
bunganya jauh lebih rendah. Jadi tidak ada "sisa yang hilang" — semuanya tetap
dihitung, cuma jadwalnya beda.

**2. Yang membuat NPV baseline vs restructured terlihat jauh — ini soal
ASUMSI PELUANG TERTAGIH, bukan soal nominal cicilan.** Lihat kodenya persis:
```python
npv_baseline = npv_of_installments(cicilan_lama, 12, discount_rate) * recovery_score  # ×0.30
npv_restructured = npv_of_installments(cicilan_baru, 18, discount_rate)               # TIDAK dikali apapun
```
`recovery_score=0.30` di sini artinya: model menilai kalau **kontrak dibiarkan
apa adanya (tidak direstrukturisasi)**, peluang riil perusahaan benar-benar
menagih penuh Rp13,8 juta itu **cuma 30%** (karena profil risikonya "Cannot
Pay"+telat) — jadi `npv_baseline` sengaja dipotong jadi ~30%-nya. Sedangkan
`npv_restructured` **tidak dipotong probabilitas apapun** — modelnya berasumsi
kalau sudah direstrukturisasi ke skema yang lebih ringan, customer akan bayar
penuh (100%) sesuai jadwal baru. **Gap besar itu murni dari perbandingan
"30% dari skema lama" vs "100% dari skema baru"**, bukan dari nominal
cicilannya yang beda jauh (yang mana memang tidak beda jauh, cuma ~2,8%).

**3. Ini temuan yang jujur perlu saya sampaikan (bukan bug di kode Anda, tapi
asumsi desain yang layak Anda tahu):** karena `npv_restructured` tidak pernah
dipotong probabilitas apapun (selalu dianggap 100% akan terbayar), sementara
`npv_baseline` HAMPIR SELALU dipotong signifikan oleh `recovery_score` (customer
yang masuk pertimbangan restrukturisasi kan memang customer berisiko, jadi
recovery_score-nya jarang tinggi) — guardrail `npv_restructured > npv_baseline`
ini secara struktur **hampir selalu lolos**, hampir apapun skema tawarannya,
selama cicilan barunya tidak dibuat konyol besar. Artinya guardrail ini lebih
tepat dibaca sebagai *"apakah menawarkan sesuatu lebih baik daripada diam
saja"*, bukan benar-benar *"apakah tawaran ini adil/optimal buat kedua pihak"*.
Ini **bukan salah satu dari 9 poin Anda** dan menyentuh logika inti kalkulator
di `app/shared/restructuring_offer_calculator.py` (dipakai bersama backend &
ML) — perubahan di situ berdampak lebih luas dari sekadar UI/API, jadi saya
tidak masukkan ke rencana implementasi sekarang. Saya cuma flag supaya Anda
sadar asumsi ini ada di baliknya — beri tahu saya kalau Anda mau ini dibahas
sebagai topik terpisah nanti.

## TASK-8 (lanjutan) — Contoh REFINANCE & CONSOLIDATE dengan angka dari Anda

Saya jalankan langsung fungsi aslinya (bukan hitung manual) dengan input persis
seperti yang Anda kasih.

### Kasus REFINANCE

**Input:** kontrak tenor 12 bulan, cicilan Rp1.150.000/bulan, sudah dibayar 3
bulan → sisa tenor 9 bulan, sisa belum dibayar Rp10.350.000 (9 × Rp1.150.000 —
persis seperti yang Anda hitung). Karena Anda tidak sebutkan detail lain (rate,
DPD, segment), saya asumsikan angka realistis yang konsisten (tolong koreksi
kalau beda dari kasus nyata yang Anda maksud): bunga 24%/tahun, DPD 45 hari,
`risk_segment="Cannot Pay"`, `recovery_score=0.55`, belum pernah restrukturisasi.

**Hasil (dijalankan langsung dari `restructuring_offer_calculator.py`):**
```
Eligibility: AUTO (semua syarat standar terpenuhi — DPD 45 ada di window 30-180)

Tawaran REFINANCE:
  Tenor baru      : 13 bulan (9 + perpanjangan 4 bulan, maks 50% dari sisa tenor)
  Bunga baru      : 14,4% (dari 24%, potongan 40%)
  Cicilan baru    : Rp864.626/bulan (dari Rp1.150.000)
  NPV baseline    : Rp5.418.006
  NPV restrukturisasi : Rp10.491.143
  Lolos guardrail : YA
```

**Poin penting yang beda dari contoh sebelumnya — di sini TOTAL NOMINAL justru
NAIK, bukan turun:**
- Sisa kewajiban lama: 9 × Rp1.150.000 = **Rp10.350.000**
- Total cicilan baru: 13 × Rp864.626 = **Rp11.240.133**
- Selisih: **+Rp890.133 (≈8,6% lebih mahal secara nominal)**

Kenapa bisa naik padahal cicilan bulanannya turun? Karena tenornya diperpanjang
4 bulan (9→13), dan 4 bulan tambahan itu tetap dikenai bunga 14,4% dari sisa
pokok yang belum lunas — jadi walau bunga per-tahun diturunkan, total bunga yang
terkumpul selama periode yang lebih panjang bisa lebih besar dari penghematan
rate-nya. **Ini bukan pola tetap** (di contoh TASK-8 yang pertama kemarin,
totalnya malah turun ~2,8%) — arahnya tergantung kombinasi seberapa besar
potongan rate vs seberapa panjang perpanjangan tenornya. Jadi jawaban jujurnya:
**restrukturisasi tidak selalu berarti total bayar lebih murah** — yang pasti
turun cuma beban cicilan BULANAN-nya (arus kas jangka pendek customer lebih
ringan), belum tentu total keseluruhannya.

Gap NPV baseline→restrukturisasi (Rp5,4jt→Rp10,5jt, ≈2×) sumbernya sama seperti
yang saya jelaskan di atas: `recovery_score=0.55` cuma memotong sisi baseline,
sisi restrukturisasi dianggap 100% akan terbayar.

### Kasus CONSOLIDATE

**Input:** "kasus yang sama" dua kali — 2 kontrak, masing-masing persis seperti
kasus REFINANCE di atas (tenor 12, cicilan Rp1.150.000, sudah bayar 3 bulan,
sisa 9 bulan @ Rp10.350.000, bunga 24%). Customer sekarang punya 2 kontrak aktif
dan mengajukan konsolidasi keduanya jadi 1.

**Hasil:**
```
Eligibility per-kontrak: AUTO (sama seperti di atas, keduanya identik)

Tawaran CONSOLIDATE:
  Total OTS gabungan  : Rp20.700.000 (Rp10.350.000 × 2)
  Rate blended        : 24% (sama, karena kedua kontrak rate-nya identik)
  Tenor baru           : 13 bulan (dari tenor terpanjang di antara keduanya = 9,
                          + perpanjangan 4 bulan sama seperti kasus tunggal)
  Cicilan baru gabungan: Rp1.729.251/bulan
  NPV baseline         : Rp10.836.012 (persis 2× versi 1 kontrak)
  NPV restrukturisasi  : Rp20.982.285 (persis 2× versi 1 kontrak)
  Lolos guardrail      : YA
```

**Temuan penting — konsolidasi 2 kontrak yang IDENTIK tidak memberi keuntungan
matematis dibanding refinance terpisah keduanya satu-satu:** saya bandingkan
langsung, hasilnya **persis sama** — 2× refinance terpisah (Rp864.626 × 2 =
Rp1.729.251/bulan) = 1× consolidate (Rp1.729.251/bulan). Ini masuk akal karena
rumus anuitas linear terhadap principal ketika rate & tenor sama persis, jadi
menggabungkan 2 kontrak yang identik secara matematis sama saja dengan
menjumlahkan 2 hasil refinance terpisah.

**Kapan CONSOLIDATE baru benar-benar memberi nilai tambah**: ketika kontrak-
kontraknya **berbeda** (misal 1 kontrak rate tinggi/tenor pendek, 1 lagi rate
rendah/tenor panjang) — proses blending rate (`weighted_rate`, tertimbang OTS)
dan pemakaian tenor-terpanjang bisa membuat kontrak yang lebih "buruk" ikut
menikmati sedikit keringanan dari yang lebih "baik". Untuk kasus 2 kontrak
identik yang Anda kasih, manfaat CONSOLIDATE murni administratif: **customer
cukup bayar 1 kali per bulan (1 rekening/1 due date) bukan 2 transaksi
terpisah** — bukan penghematan nominal. Kalau Anda mau lihat contoh dengan 2
kontrak yang benar-benar berbeda supaya manfaat blending-nya kelihatan, saya
bisa buatkan — tinggal bilang.

---

## TASK-9 — Tombol Sync (daily_scoring.py, + train_initial_model.py kalau model belum ada)

**Kondisi & risiko yang perlu Anda tahu sebelum saya desain ini:**

1. **Belum ada mekanisme apapun** di backend yang menjalankan script ML — saya
   grep `subprocess/Popen/os.system` di `app/backend/`, nihil. Backend hari ini
   cuma **membaca** tabel yang ML tulis, tidak pernah memicu proses ML. Jadi ini
   pola arsitektur baru, bukan perluasan yang sudah ada.
2. **Dependency terpisah** — `app/backend/requirements.txt` tidak ada
   pandas/xgboost/scikit-learn/joblib; itu semua cuma ada di
   `app/machine-learning/requirements.txt`. Kalau backend memicu script ML lewat
   subprocess, itu **harus pakai interpreter Python yang punya paket ML
   ter-install** (bukan otomatis pakai python milik proses FastAPI-nya sendiri).
   Karena Anda kemarin memutuskan backend & ML sekarang **berbagi 1 venv yang
   sama** (venv root Python 3.9), ini kebetulan sudah aman di lingkungan Anda
   sekarang — tapi saya akan tetap membuat path interpreter-nya configurable
   (env var), bukan hardcode, supaya tidak rapuh kalau nanti dipisah lagi.
3. **`daily_scoring.py` aman dijalankan berkali-kali** (idempotent — dia hapus
   baris `scoring_date` yang sama sebelum insert ulang). Perkiraan durasi: cepat
   (hitungan detik, skala data sekarang ~700 kontrak, hitungan vectorized bukan
   loop per-baris).
4. **`train_initial_model.py` TIDAK idempotent** — setiap dijalankan langsung
   menimpa champion model yang ada di `registry.json` **tanpa syarat minimum
   kualitas** (tidak ada gate AUC-floor seperti proses champion/challenger
   mingguan). Kalau training ulang menghasilkan model lebih buruk, itu tetap jadi
   champion baru. Durasi: lebih lama dari scoring (XGBoost + 5-fold
   cross-validation, kemungkinan belasan-puluhan detik, tergantung jumlah baris).
5. **Cek "belum ada model" bisa pakai fungsi yang sudah ada**:
   `src/model_registry.get_champion_path(model_type=...)` — akan raise
   `FileNotFoundError` kalau champion belum ada, sama seperti yang sudah dipakai
   `daily_scoring.py` sendiri. Tidak perlu bikin logic baca `registry.json` manual.
6. Endpoint model-health yang sudah ada (`/ai-intelligence/model-config`) sumber
   datanya `model_monitoring_log`, yang **hanya ditulis oleh `weekly_mlops.py`**
   (proses mingguan), BUKAN oleh `daily_scoring.py`. Jadi "terakhir sync" yang
   akurat untuk tombol ini butuh sumber data lain — saya usulkan endpoint kecil
   baru yang baca `MAX(updated_at) FROM ai_intelligence_output` untuk
   menunjukkan "terakhir di-scoring: ...".

**Rencana desain:**
- Endpoint baru, misal `POST /ai-intelligence/sync` — **berjalan sebagai
  background job**, BUKAN blocking di request HTTP (karena training bisa
  belasan detik, terlalu lama untuk 1 request-response biasa dan berisiko
  timeout). Response langsung `202 Accepted` + job-id, frontend polling status.
- Alurnya: cek `get_champion_path("recovery")` (dan submodel lain kalau relevan
  — lihat pertanyaan #1 di bawah) → kalau `FileNotFoundError`, jalankan
  `train_initial_model.py` dulu → lanjut jalankan `daily_scoring.py` → update
  status job jadi selesai/gagal.
- Tombol di UI: "Sync Now", nonaktif/spinner selama job berjalan, tampilkan
  "Terakhir sync: ..." dari endpoint status baru di atas.

**✅ Keputusan Anda:**
1. **Cover semua 4 model** (`recovery`, `self_cure`, `roll_forward`,
   `ptp_success`) — masing-masing dicek `get_champion_path(model_type=...)`
   sendiri-sendiri, training cuma jalan untuk model_type yang belum ada
   champion-nya (bukan retrain semuanya kalau salah satu belum ada).
2. **Tanpa gate kualitas** — dan setelah dicek ulang, **Anda benar, poin risiko
   yang saya angkat sebelumnya tidak relevan untuk desain Sync button ini**.
   Alasan: karena training di alur Sync ini **hanya dipicu kalau
   `get_champion_path()` gagal (belum ada champion sama sekali)**, begitu 1 kali
   berhasil training, Sync berikutnya otomatis SKIP training (langsung ke
   scoring) — jadi champion yang sudah ada **tidak akan pernah tertimpa** lewat
   tombol ini, berapa kalipun Anda menekannya. Risiko "tertimpa model lebih
   jelek" yang saya khawatirkan kemarin cuma relevan kalau suatu saat ada fitur
   terpisah "force retrain" yang sengaja melewati pengecekan
   `get_champion_path()` — untuk sekarang, **gate dihapus dari rencana**, sesuai
   koreksi Anda.
3. **Semua user login boleh menekan tombol ini** (tidak ada pembatasan akses,
   konsisten dengan fitur lain yang RBAC-nya masih di-hold).

---

## Ringkasan status pertanyaan (per revisi ini)

**Semua 9 poin + TASK-0 sudah terjawab/final.** Yang tersisa cuma 2 hal kecil
sebelum saya mulai implementasi:

| # | Yang masih perlu diputuskan |
|---|---|
| 2 | Modal "Profil Saya" — saya asumsikan read-only (Name/Role/Username dari `/auth/me`), tolong koreksi kalau Anda mau bentuk lain. |
| 6 | **Backfill nama customer yang sudah ada di DB dev**: (a) regenerate total 4 tabel faker dari nol (bersih tapi hapus data dev existing), atau (b) script backfill terpisah yang cuma UPDATE `cust_name` tanpa sentuh tabel lain? Perlu pilihan Anda sebelum saya jalankan salah satunya (operasi ubah/hapus data, saya tidak mau asumsi sepihak). |

Selebihnya (TASK-0, 1, 2 lainnya, 3, 4, 5, 6 skema+faker, 7, 8, 9) sudah final
dan siap dieksekusi. Setelah 2 poin di atas Anda jawab, saya mulai implementasi
semuanya — atau kalau Anda mau saya mulai sekarang dengan asumsi default untuk
poin 2 dan pilih opsi (b) untuk poin 6 (paling aman, tidak menyentuh data lain),
tinggal bilang saja.

# CollectAI — Restructuring Recommendation Engine: Task List

**Prasyarat**: TASK-01 s/d TASK-47 sudah selesai (arsitektur 4-model + CBS sudah berjalan).

## Catatan untuk Agent — baca dulu sebelum mulai

1. **Nilai konfigurasi di TASK-49 (haircut, tenor, dsb.) adalah starting point ilustratif**,
   bukan angka final. Jangan deploy ke production sebelum di-review ulang oleh tim
   finance/risk perusahaan.
2. **`product_conversion_mapping` di TASK-48 masih placeholder.** Daftar `PRODUCT_TYPE`
   aktual belum tersedia — konfirmasi ke tim produk sebelum TASK-54 (Takeover) dianggap selesai.
3. **Fase 2 (model ML acceptance probability) sengaja TIDAK ada di file ini.** Itu baru bisa
   dikerjakan setelah `restructuring_history` (TASK-55) terisi data nyata dalam jumlah cukup.
   Urutan ini disengaja — jangan loncat ke ML sebelum data historis ada.
4. Guardrail (`apply_guardrail`) bersifat **permanen** — jangan pernah dihapus/dilewati
   walau nanti model ML sudah ada di atasnya.
5. **Eligibility bertingkat (AUTO / MANUAL_REVIEW / BLOCKED), bukan gate biner.**
   Karena akan ada backend + frontend di mana setiap customer bisa di-query opsi
   restrukturisasinya, angka tawaran HARUS tetap dihitung untuk MANUAL_REVIEW
   (hanya butuh approval sebelum ditawarkan ke nasabah). Hanya BLOCKED (data tidak
   valid) yang tidak menghasilkan angka sama sekali. Lihat TASK-50/51 yang sudah direvisi.

**Urutan eksekusi:**
```
TASK-48 → TASK-49 → TASK-50 → TASK-51 → TASK-52 → TASK-53
        → TASK-54 → TASK-55 → TASK-56 → TASK-57
        → TASK-58 → TASK-59 → TASK-60   (backend integration)
```

---

## PHASE 10 — Schema & Config

### TASK-48: Update Database Schema untuk Restructuring Engine
**Status**: [ ] Pending
**Dependencies**: TASK-31 (schema_v2 sudah ada)
**Output file**: `config/schema_v3.sql`

**Instruksi untuk agent:**
Buat file `config/schema_v3.sql` berisi ALTER/CREATE TABLE. Jangan hapus kolom/tabel lama.

```sql
-- config/schema_v3.sql
-- Restructuring Recommendation Engine — jalankan SETELAH schema_v2

-- ── CONTRACT_SNAPSHOT: raw rate + lineage restrukturisasi ──────────
ALTER TABLE contract_snapshot
  ADD COLUMN IF NOT EXISTS interest_rate          NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS closed_via_restructure BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS new_contract_no        VARCHAR(30);

-- ── CUSTOMER_BEHAVIORAL_STANDING: input guardrail ───────────────────
ALTER TABLE customer_behavioral_standing
  ADD COLUMN IF NOT EXISTS restructure_count      INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_restructure_date  DATE;

-- ── GROUP MAP: 1 tawaran bisa mencakup 1 atau N kontrak ─────────────
CREATE TABLE IF NOT EXISTS restructuring_group_map (
  restructure_group_id  VARCHAR(40)  NOT NULL,
  contract_no           VARCHAR(30)  NOT NULL,
  cust_id               VARCHAR(30)  NOT NULL,
  inclusion_reason      VARCHAR(50),
  PRIMARY KEY (restructure_group_id, contract_no)
);

-- ── OUTPUT: tawaran yang direkomendasikan ───────────────────────────
CREATE TABLE IF NOT EXISTS restructuring_recommendation_output (
  restructure_group_id        VARCHAR(40) PRIMARY KEY,
  cust_id                      VARCHAR(30) NOT NULL,
  offer_type                   VARCHAR(20) NOT NULL,
  contract_count_included      INTEGER NOT NULL,
  total_ots_combined           NUMERIC(18,2),
  recommended_new_tenor        INTEGER,
  recommended_new_rate         NUMERIC(6,4),
  recommended_new_installment  NUMERIC(18,2),
  recovery_from_asset          NUMERIC(18,2) DEFAULT 0,
  npv_baseline                 NUMERIC(18,2),
  npv_restructured             NUMERIC(18,2),
  offer_status                 VARCHAR(20) DEFAULT 'GENERATED',
  generated_date                DATE NOT NULL,
  expiry_date                   DATE,
  CONSTRAINT chk_offer_type   CHECK (offer_type IN ('REFINANCE','CONSOLIDATE','TAKEOVER')),
  CONSTRAINT chk_offer_status CHECK (offer_status IN ('GENERATED','OFFERED','ACCEPTED','REJECTED','EXPIRED'))
);

-- ── HISTORY: hasil aktual — bahan training model acceptance Fase 2 ──
CREATE TABLE IF NOT EXISTS restructuring_history (
  restructure_group_id      VARCHAR(40) NOT NULL,
  offered_date               DATE NOT NULL,
  customer_response          VARCHAR(20),
  response_date               DATE,
  post_restructure_dpd_30d   INTEGER,
  post_restructure_dpd_90d   INTEGER,
  PRIMARY KEY (restructure_group_id, offered_date)
);

-- ── PRODUCT CONVERSION MAPPING (placeholder — lihat Catatan #2) ─────
CREATE TABLE IF NOT EXISTS product_conversion_mapping (
  source_product_type          VARCHAR(50) NOT NULL,
  allowed_target_product_type  VARCHAR(50) NOT NULL,
  conversion_type               VARCHAR(30),
  requires_appraisal            BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (source_product_type, allowed_target_product_type)
);

-- ── ASSET APPRAISAL (input eksternal — bukan hasil AI) ────────────────
CREATE TABLE IF NOT EXISTS asset_appraisal (
  contract_no       VARCHAR(30) NOT NULL,
  asset_id          VARCHAR(40) NOT NULL,
  appraised_value   NUMERIC(18,2) NOT NULL,
  appraisal_date    DATE NOT NULL,
  condition_grade   VARCHAR(10),
  PRIMARY KEY (contract_no, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_restructure_group_cust    ON restructuring_group_map (cust_id);
CREATE INDEX IF NOT EXISTS idx_restructure_output_status ON restructuring_recommendation_output (offer_status);
```

**Acceptance Criteria:**
- [ ] Semua statement idempotent (`IF NOT EXISTS`), aman dijalankan ulang
- [ ] Kolom/tabel lama tidak berubah
- [ ] CHECK constraints untuk `offer_type` dan `offer_status` berfungsi
- [ ] `product_conversion_mapping` kosong sampai TASK-54 (tim produk belum kasih data asli)

---

### TASK-49: Update `config/settings.py` — Restructuring Policy
**Status**: [ ] Pending
**Dependencies**: TASK-48
**Output file**: `config/settings.py` (update)

**Instruksi untuk agent:**
Tambahkan konstanta berikut. Jangan hapus konstanta lama dari TASK-32.

```python
# ── RESTRUCTURING POLICY — starting point, perlu approval finance/risk ──
MAX_HAIRCUT_PCT              = 0.40   # maks turun 40% relatif dari rate asal
MIN_RATE_FLOOR                = 0.09   # floor absolut ~cost of fund + margin
MAX_TENOR_EXTENSION_MONTHS    = 24
MAX_TENOR_EXTENSION_RATIO     = 0.50   # atau maks 50% dari sisa tenor asli — ambil yg lebih ketat

MIN_DPD_FOR_RESTRUCTURE       = 30
MAX_DPD_FOR_RESTRUCTURE       = 180
MAX_RESTRUCTURE_PER_CUSTOMER  = 2      # ke-3+ butuh approval komite manual

ASSET_VALUE_MIN_RATIO         = 0.50   # nilai appraisal min. tutup 50% OTS
APPRAISAL_MAX_AGE_MONTHS      = 3

CONSOLIDATION_MIN_ACTIVE_CONTRACTS   = 2
CONSOLIDATION_PROBLEM_CONTRACTS_ONLY = True  # kontrak lancar tidak ikut merge (default)

RESTRUCTURE_DISCOUNT_RATE_ANNUAL = 0.12  # dipakai utk NPV, bukan bunga kontrak
```

**Acceptance Criteria:**
- [ ] Semua konstanta di atas ada dan importable
- [ ] Tidak ada konstanta lama (TASK-32) yang hilang/berubah

---

## PHASE 11 — Offer Calculation

### TASK-50: Build Eligibility Classifier (Tiered)
**Status**: [ ] Pending
**Dependencies**: TASK-49
**Output file**: `business_rules/restructuring_eligibility.py`

**Instruksi untuk agent:**
Implementasikan `classify_eligibility()` yang mengembalikan salah satu dari 3 tier,
BUKAN gate biner. Ini penting karena backend nanti butuh menampilkan opsi
restrukturisasi untuk *setiap* customer, bukan hanya yang lolos filter otomatis.

```
AUTO           → lolos semua kriteria standar → daily batch boleh mendorong otomatis
MANUAL_REVIEW  → angka TETAP DIHITUNG (lihat TASK-51) → butuh approval supervisor
                 sebelum ditawarkan ke nasabah — dipakai saat backend query on-demand
BLOCKED        → SATU-SATUNYA tier yang tidak menghasilkan angka — hanya untuk
                 masalah data (interest_rate/total_ots tidak valid, kontrak sudah
                 closed_via_restructure), BUKAN untuk judgment bisnis
```

```python
def classify_eligibility(contract, customer, policy) -> EligibilityResult:
    # BLOCKED — murni data/status kontrak
    blocked_reasons = []
    if contract.closed_via_restructure:
        blocked_reasons.append("kontrak sudah ditutup lewat restrukturisasi sebelumnya")
    if contract.interest_rate is None or contract.interest_rate <= 0:
        blocked_reasons.append("interest_rate tidak valid")
    if contract.total_ots is None or contract.total_ots <= 0:
        blocked_reasons.append("total_ots tidak valid")
    if blocked_reasons:
        return EligibilityResult(tier=EligibilityTier.BLOCKED, reasons=blocked_reasons)

    # MANUAL_REVIEW — judgment bisnis, angka tetap dihitung di TASK-51
    review_reasons = []
    if contract.risk_segment != "Cannot Pay":
        review_reasons.append(f"risk_segment '{contract.risk_segment}' bukan target standar")
    if customer.b_list_status == "Y":
        review_reasons.append("nasabah B_LIST — butuh approval manual")
    if contract.self_cure_probability >= 0.70:
        review_reasons.append("self_cure_probability tinggi")
    if not (policy.min_dpd_for_restructure <= contract.dpd_current <= policy.max_dpd_for_restructure):
        review_reasons.append("DPD di luar window standar")
    if customer.restructure_count >= policy.max_restructure_per_customer:
        review_reasons.append("restructure_count sudah mencapai batas standar")
    if review_reasons:
        return EligibilityResult(tier=EligibilityTier.MANUAL_REVIEW, reasons=review_reasons)

    return EligibilityResult(tier=EligibilityTier.AUTO, reasons=[])
```

**Acceptance Criteria:**
- [ ] Semua 3 kondisi BLOCKED dan 5 kondisi MANUAL_REVIEW diuji di unit test (TASK-56)
- [ ] BLOCKED hanya dipicu oleh masalah data, tidak pernah oleh risk_segment/B_LIST/DPD/self_cure/restructure_count
- [ ] Return value selalu `EligibilityResult`, tidak pernah raise exception untuk input valid

---

### TASK-51: Build Offer Calculator (3 cabang)
**Status**: [ ] Pending
**Dependencies**: TASK-50
**Output file**: `business_rules/restructuring_offer_calculator.py`

**Instruksi untuk agent:**
Implementasikan modul lengkap — dataclasses (`ContractInput`, `CustomerContext`,
`AssetAppraisal`, `RestructureOffer`), fungsi amortisasi (`calculate_installment`,
`npv_of_installments`), 3 fungsi cabang (`calculate_refinance_offer`,
`calculate_consolidation_offer`, `calculate_takeover_offer`), `apply_guardrail`,
dan orchestrator `generate_offers`.

Referensi implementasi lengkap ada di file terlampir `restructuring_offer_calculator.py`
(sudah di-smoke-test dan menghasilkan output benar) — salin/adaptasi langsung dari file itu.

Orchestrator utamanya adalah `assess_restructuring_options()` (bukan lagi
`generate_offers()`), yang mengembalikan `RestructuringAssessment` berisi
`eligibility_tier`, `eligibility_reasons`, dan `offers` — dan **tetap mengisi
`offers` untuk tier MANUAL_REVIEW**, hanya mengembalikan `offers=[]` untuk BLOCKED.

**Poin yang WAJIB dijaga:**
- `apply_guardrail()` harus selalu dipanggil di akhir sebelum offer dianggap valid — jangan pernah di-skip
- Kalau produk pakai flat rate (bukan reducing-balance), `calculate_installment()` harus diganti — jangan campur dua metode amortisasi dalam satu engine
- Ranking kandidat diberi komentar eksplisit bahwa ini akan diganti `expected_value = P(accept) * npv_restructured` di Fase 2 — jangan hapus komentar ini
- **Jangan early-return offers kosong untuk tier MANUAL_REVIEW** — ini poin utama revisi task ini, salah satu regresi paling gampang terjadi kalau agent lain menyentuh file ini nanti

**Acceptance Criteria:**
- [ ] `python business_rules/restructuring_offer_calculator.py` jalan tanpa error (smoke test)
- [ ] Semua 3 cabang offer menghasilkan `is_guardrail_passed` yang benar sesuai NPV
- [ ] Takeover branch mengembalikan `None` jika appraisal kadaluarsa atau nilai aset < `ASSET_VALUE_MIN_RATIO`
- [ ] Kasus MANUAL_REVIEW (mis. DPD di luar window) tetap menghasilkan `offers` terisi, bukan list kosong
- [ ] Kasus BLOCKED (mis. `interest_rate` invalid) menghasilkan `offers=[]`

---

### TASK-52: Orchestrator + Integrasi Daily Batch Flow
**Status**: [ ] Pending
**Dependencies**: TASK-51
**Output file**: `pipeline/restructuring_runner.py` + update `pipeline/daily_runner.py`

**Instruksi untuk agent:**
Tambahkan Step 7.5 di `daily_runner.py`, dijalankan SETELAH business rules (Step 7)
dan SEBELUM QC (Step 8). Untuk **semua** `CONTRACT_NO` yang tidak `BLOCKED`
(termasuk yang tidak persis `RISK_SEGMENT = 'Cannot Pay'`), panggil
`assess_restructuring_options()` dan simpan hasilnya (berikut `eligibility_tier`)
ke `restructuring_group_map` dan `restructuring_recommendation_output`, dengan
`source = 'BATCH'`.

**Penting**: batch tetap MENYIMPAN hasil untuk tier AUTO maupun MANUAL_REVIEW —
tapi **hanya tier AUTO yang memicu notifikasi/push otomatis ke collector**.
Tier MANUAL_REVIEW disimpan sebagai cache supaya backend (TASK-58) bisa
menyajikannya cepat saat CS query on-demand, tanpa perlu hitung ulang live
kalau data hari itu masih fresh.

**Acceptance Criteria:**
- [ ] Step 7.5 tidak menghentikan pipeline jika satu kontrak gagal diproses (log & lanjut)
- [ ] `restructure_group_id` di-generate konsisten (mis. `RG-{cust_id}-{generated_date}-{seq}`)
- [ ] Notifikasi ke collector hanya terpicu untuk baris dengan `eligibility_tier = 'AUTO'`
- [ ] Baris `MANUAL_REVIEW` tetap tersimpan (untuk dipakai TASK-58), tidak memicu notifikasi

---

## PHASE 12 — Dampak ke Sistem Existing

### TASK-53: Update Feature Engineering — Lineage Flags
**Status**: [ ] Pending
**Dependencies**: TASK-52
**Output file**: `features/contract_features.py` (update)

**Instruksi untuk agent:**
Tambahkan fitur `IS_RESTRUCTURED` dan `MONTHS_SINCE_RESTRUCTURE`. Kontrak dengan
`closed_via_restructure = TRUE` HARUS dikeluarkan dari training set 4 model existing
sampai minimal 3 siklus penagihan berjalan pasca-restrukturisasi (cegah label contamination —
DPD yang "reset" karena restrukturisasi administratif jangan disalahartikan model sebagai
perbaikan perilaku genuine).

**Acceptance Criteria:**
- [ ] Training set 4 model existing mem-filter `closed_via_restructure = FALSE`
- [ ] `IS_RESTRUCTURED` tersedia sebagai fitur untuk kontrak yang levelnya adalah hasil restrukturisasi

---

### TASK-54: Update QC Checks
**Status**: [ ] Pending
**Dependencies**: TASK-52
**Output file**: `qc/qc_checks.py` (update)

**Instruksi untuk agent:**
Tambahkan validasi: (a) `npv_restructured > npv_baseline` untuk semua baris di
`restructuring_recommendation_output`, (b) haircut & tenor tidak melebihi cap kebijakan,
(c) `product_conversion_mapping` yang dipakai memang sudah dikonfirmasi tim produk
(bukan placeholder kosong) sebelum takeover offer di-generate ke production.

**Acceptance Criteria:**
- [ ] QC gagal (alert) jika ada baris melanggar guardrail yang lolos ke output (harusnya tidak mungkin, tapi ini safety net)

---

## PHASE 13 — Feedback Loop & Testing

### TASK-55: Update MLOps Outcome Labeler
**Status**: [ ] Pending
**Dependencies**: TASK-52
**Output file**: `mlops/outcome_labeler.py` (update)

**Instruksi untuk agent:**
Setelah tawaran berstatus `OFFERED`, capture `customer_response` dan
`post_restructure_dpd_30d`/`90d` ke `restructuring_history`. Data ini adalah bahan
baku SATU-SATUNYA untuk melatih model acceptance probability di Fase 2 —
tidak ada shortcut lain.

**Acceptance Criteria:**
- [ ] Setiap baris `restructuring_history` bisa di-join balik ke `restructuring_recommendation_output`
- [ ] Job ini idempotent — tidak duplikat kalau dijalankan ulang

---

### TASK-56: Test Cases
**Status**: [ ] Pending
**Dependencies**: TASK-51
**Output file**: `tests/test_restructuring_engine.py`

**Instruksi untuk agent:**
Unit test untuk: eligibility (5 kondisi di TASK-50), refinance calc, consolidation calc,
takeover calc (termasuk edge case: appraisal expired, asset value di bawah ratio),
guardrail (offer yang NPV-nya lebih buruk dari baseline harus `is_guardrail_passed=False`).

**Acceptance Criteria:**
- [ ] Coverage mencakup semua edge case yang disebutkan di atas
- [ ] Test guardrail-fail case tidak boleh dihapus/diskip — ini yang paling penting untuk dijaga jangka panjang

---

### TASK-57: Script Migrasi Data
**Status**: [ ] Pending
**Dependencies**: TASK-48
**Output file**: `scripts/migrate_restructuring_v1.py`

**Instruksi untuk agent:**
Backfill `restructure_count = 0` dan `closed_via_restructure = FALSE` untuk semua
kontrak existing. `product_conversion_mapping` dibiarkan kosong sampai tim produk
memberi data asli (lihat Catatan #2 di atas file ini).

**Acceptance Criteria:**
- [ ] Script idempotent, aman dijalankan ulang
- [ ] Tidak mengubah kontrak yang sudah punya `restructure_count` terisi (kalau ada data manual sebelumnya)

---

## PHASE 14 — Backend API Integration

**Konteks**: repo akan punya backend + frontend, di mana CS/collector bisa
query opsi restrukturisasi untuk customer manapun secara on-demand — tidak
cuma yang sudah di-generate batch. Framework backend belum ditentukan di sini
(agnostik) — sesuaikan dengan stack yang dipakai repo Anda.

### TASK-58: Endpoint On-Demand per Customer
**Status**: [ ] Pending
**Dependencies**: TASK-52
**Output file**: `api/routes/restructuring.py` (atau path setara di framework yang dipakai)

**Instruksi untuk agent:**
Buat endpoint `GET /customers/{cust_id}/restructuring-options` dengan logika:

```
1. Cek restructuring_recommendation_output — ada baris untuk cust_id ini
   dengan generated_date = hari ini (source='BATCH')?
   → Ya: kembalikan langsung (cache hit, tidak perlu hitung ulang)
2. Tidak ada / kadaluarsa:
   → Ambil data kontrak + CBS + appraisal terbaru dari DB secara live
   → Panggil assess_restructuring_options() langsung (source='ON_DEMAND')
   → Simpan hasilnya ke restructuring_recommendation_output juga (audit trail)
3. Response HARUS menyertakan eligibility_tier + eligibility_reasons,
   bukan cuma angka offer — frontend butuh ini untuk menentukan apakah
   tombol "tawarkan" aktif langsung atau perlu approval dulu
```

**Contoh response JSON (kontrak-agnostik framework):**
```json
{
  "cust_id": "CUST02",
  "eligibility_tier": "MANUAL_REVIEW",
  "eligibility_reasons": ["DPD 10 di luar window standar (30-180)"],
  "offers": [
    {
      "offer_type": "REFINANCE",
      "recommended_new_tenor_months": 27,
      "recommended_new_rate": 0.144,
      "recommended_new_installment": 653705.0,
      "npv_baseline": 6313333.4,
      "npv_restructured": 15401033.32
    }
  ],
  "source": "ON_DEMAND"
}
```

**Acceptance Criteria:**
- [ ] Response selalu menyertakan `eligibility_tier` dan `eligibility_reasons`, walau `offers` kosong (BLOCKED)
- [ ] Cache hit (batch hari ini) tidak memicu komputasi ulang
- [ ] Response time on-demand (cache miss) terukur dan di-log untuk monitoring

---

### TASK-59: Tambahan Kolom Audit di Schema
**Status**: [ ] Pending
**Dependencies**: TASK-58
**Output file**: `config/schema_v4.sql`

**Instruksi untuk agent:**
```sql
-- config/schema_v4.sql
ALTER TABLE restructuring_recommendation_output
  ADD COLUMN IF NOT EXISTS eligibility_tier    VARCHAR(20) DEFAULT 'AUTO',
  ADD COLUMN IF NOT EXISTS eligibility_reasons TEXT,
  ADD COLUMN IF NOT EXISTS source              VARCHAR(20) DEFAULT 'BATCH',
  ADD COLUMN IF NOT EXISTS requested_by        VARCHAR(50);

ALTER TABLE restructuring_recommendation_output
  ADD CONSTRAINT chk_eligibility_tier CHECK (eligibility_tier IN ('AUTO','MANUAL_REVIEW','BLOCKED')),
  ADD CONSTRAINT chk_source CHECK (source IN ('BATCH','ON_DEMAND'));

-- ── AUDIT LOG: siapa approve tawaran MANUAL_REVIEW ──────────────────
CREATE TABLE IF NOT EXISTS restructuring_override_log (
  restructure_group_id  VARCHAR(40) NOT NULL,
  action                VARCHAR(20) NOT NULL,   -- 'APPROVED' | 'REJECTED'
  actor_id              VARCHAR(50) NOT NULL,
  actor_role            VARCHAR(30) NOT NULL,   -- mis. 'SUPERVISOR', 'COMMITTEE'
  reason                TEXT,
  action_timestamp      TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY (restructure_group_id, action_timestamp)
);
```

**Acceptance Criteria:**
- [ ] Idempotent, tidak mengubah data existing
- [ ] Semua baris lama otomatis dapat default `eligibility_tier='AUTO'`, `source='BATCH'` (asumsi wajar untuk data historis sebelum tiering ini ada)

---

### TASK-60: Alur Approval untuk Tier MANUAL_REVIEW
**Status**: [ ] Pending
**Dependencies**: TASK-59
**Output file**: `api/routes/restructuring_approval.py` (atau path setara)

**Instruksi untuk agent:**
Buat endpoint `POST /restructuring-options/{restructure_group_id}/approve` dan
`.../reject`. Endpoint ini mengubah `offer_status` di
`restructuring_recommendation_output` dari `GENERATED` → `OFFERED` (kalau
approve) HANYA setelah mencatat baris baru di `restructuring_override_log`.

**Poin yang WAJIB dijaga:**
- Tier `AUTO` tidak butuh endpoint ini — sudah otomatis `OFFERED` dari batch
- Tier `BLOCKED` tidak bisa diapprove sama sekali (tidak ada `offers` untuk diapprove)
- Role/permission siapa yang boleh approve adalah keputusan tim Anda (mis. supervisor
  untuk kasus umum, committee untuk `restructure_count >= max`) — modul ini hanya
  menyediakan mekanisme pencatatannya, bukan logika RBAC itu sendiri

**Acceptance Criteria:**
- [ ] Approve/reject tanpa entry di `restructuring_override_log` tidak mungkin terjadi (atomic transaction)
- [ ] Tier AUTO ditolak dari endpoint ini dengan pesan error yang jelas ("tidak perlu approval")

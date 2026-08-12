# AI Reasoning — Spesifikasi Prompt Gemini

Dokumen referensi untuk **bentuk persis** request/response yang dipertukarkan
dengan Gemini pada fitur AI Reasoning (hyper-personalization level-debitur).
Ditulis untuk keperluan showcase/demo — semua isi di bawah diambil langsung
dari kode yang berjalan (`app/backend/services/ai_reasoning_*.py`,
`gemini_client.py`), bukan deskripsi konseptual.

Desain produk & keputusan bisnis di balik fitur ini ada di
[`ai-reasoning-api-upgrade-tasks.md`](ai-reasoning-api-upgrade-tasks.md).
Dokumen ini fokus ke **kontrak teknis prompt itu sendiri**.

---

## 1. Ringkasan alur

```
GET/POST /customers/{cust_id}/ai-reasoning
              │
              ▼
   AiReasoningService.generate()
              │
   ┌──────────┼───────────────────────────────────────────┐
   │ build_instruction()   build_payload()   build_response_schema() │
   │  (statis, sekali)     (per-debitur)     (statis, sekali)         │
   └──────────┼───────────────────────────────────────────┘
              ▼
   GeminiClient.generate(instruction, payload, schema)
              │  POST https://generativelanguage.googleapis.com/
              │       v1beta/models/{model}:generateContent?key=...
              ▼
   { text: "<JSON string>", usageMetadata: {...} }
              │
              ▼
   parse_response_text() → GeminiReasoningOutputSchema.model_validate()
              │  (validasi ULANG di Pydantic — jangan percaya satu lapis saja)
              ▼
   simpan ke ai_reasoning_output (status OK), atau FALLBACK/FAILED kalau
   langkah manapun di atas gagal
```

Satu request HTTP ke Gemini berisi **tiga bagian independen**, dirakit di
`AiReasoningService.generate()`
(`app/backend/services/ai_reasoning_service.py:124`) lalu dikirim oleh
`GeminiClient.generate()` (`app/backend/services/gemini_client.py:60-67`):

```python
body = {
    "system_instruction": {"parts": [{"text": system_instruction}]},
    "contents": [{"role": "user", "parts": [{"text": json.dumps(payload)}]}],
    "generationConfig": {
        "responseMimeType": "application/json",
        "responseSchema": response_schema,
    },
}
```

| Bagian | Sumber | Berubah per-debitur? |
|---|---|---|
| `system_instruction` | `build_instruction()` | Tidak — statis, hanya `{nba_actions}` yang disisipkan |
| `contents[0].parts[0].text` | `build_payload()` → `json.dumps()` | **Ya** — ini satu-satunya bagian yang membawa data debitur |
| `generationConfig.responseSchema` | `build_response_schema()` | Tidak — statis |

---

## 2. System instruction

Sumber: `app/backend/services/ai_reasoning_prompt.py::build_instruction()`.
Teks penuh (Bahasa Indonesia — model diminta menjawab dalam Bahasa Indonesia juga):

```
Anda analis kredit yang membantu petugas collection di perusahaan multifinance Indonesia. Data JSON berikut adalah profil SATU DEBITUR yang mungkin memiliki beberapa kontrak.

Tugas Anda: tentukan SATU strategi penanganan yang konsisten untuk debitur ini sebagai satu orang, bukan rekomendasi terpisah per kontrak.

Aturan wajib:
- primaryNbaAction HARUS salah satu dari: WA, Deskcoll, Visit, Somasi, Pickup. Hanya SATU — debitur ini satu orang, tidak masuk akal menghubunginya lewat beberapa channel bertentangan di waktu yang sama.
- Kalau nba_spread pada portfolio_rollup berisi lebih dari satu nilai, itu berarti kontrak-kontraknya punya rekomendasi berbeda. Rekonsiliasi, dan jelaskan alasannya di consistencyNote.
- Urgensi mengikuti kontrak TERBURUK (field worst_* pada portfolio_rollup), bukan rata-rata.
- Pertimbangkan collection_sensitivity pada customer_profile sebagai preferensi channel debitur; boleh menyimpang kalau tingkat keparahan menuntut, tapi sebutkan alasannya.
- payment_history di setiap kontrak hanya mencatat pembayaran yang TERJADI; angsuran yang tidak dibayar TIDAK muncul sebagai baris. Nilai tunggakan dari dpd_current dan overdue_installment_count pada kontrak, JANGAN disimpulkan dari jumlah baris pembayaran.
- nba_recommendation per kontrak adalah hasil rule engine deterministik dengan cakupan terbatas — ia HANYA menghasilkan "Pickup" pada kondisi yang sangat sempit (segmen won't-pay, saldo besar, riwayat gagal bayar berulang), dan tidak mempertimbangkan portofolio debitur secara keseluruhan. Perlakukan sebagai rekomendasi sistem saat ini yang perlu Anda rekonsiliasi, BUKAN sebagai batas atas tindakan yang boleh Anda usulkan — Anda boleh mengusulkan tindakan yang lebih ringan ATAU lebih berat dari nba_recommendation kalau data portofolio menuntutnya. nba_trigger menjelaskan kondisi apa yang memicu rekomendasi itu — nilai apakah alasannya masih berlaku ketika seluruh kontrak debitur dilihat bersamaan.
- Field yang TIDAK ADA di JSON berarti tidak tersedia — jangan diasumsikan nol, dan jangan mengarang angka yang tidak ada di input. available_models memberi tahu model skor apa yang tersedia; skor dari model yang tidak terdaftar memang tidak ada, bukan bernilai rendah.

Jawab dalam Bahasa Indonesia, ringkas, berbasis data yang diberikan.
```

### Kenapa aturan-aturan ini ada (bukan template generik)

| Aturan | Masalah yang dicegah |
|---|---|
| "BUKAN sebagai batas atas tindakan" | Rule engine per kontrak hanya menghasilkan `Pickup` pada kondisi sempit dan cenderung lebih konservatif dari kondisi gabungan — tanpa kalimat ini Gemini akan membatasi diri ke opsi yang sudah ada di data, padahal justru itu yang ingin diperbaiki (rekonsiliasi lintas kontrak). *(Catatan v2: sebelumnya dokumen ini — dan system instruction-nya — menyatakan rule engine "tidak pernah" menghasilkan Pickup. Klaim itu keliru: setelah perbaikan `historical_default_count`, verifikasi query nyata 2026-08-11 menunjukkan Pickup muncul 10/711 kontrak (1,4%). Diperbaiki di `PROMPT_VERSION="v2"`, lihat §7.)* |
| Larangan menyimpulkan tunggakan dari panjang `payment_history` | Tabel itu hanya mencatat pembayaran yang **terjadi** — kontrak yang macet total punya array pendek, bukan array berisi baris "UNPAID". Tanpa aturan ini Gemini salah membaca "sedikit riwayat" sebagai "sedikit masalah" |
| "jangan diasumsikan nol" + `available_models` | Mengulang bug temuan #17 (skor yang *hilang* dari sistem — belum ada model-nya — disalahtafsirkan sebagai skor *rendah*) |
| Urgensi ikut `worst_*`, bukan rata-rata | Debitur dengan 1 kontrak C3+ dan 2 kontrak C0 tidak boleh "diselamatkan" jadi rata-rata C1 — satu kontrak parah cukup untuk mengangkat urgensi seluruh debitur |

---

## 3. Payload (data per debitur)

Sumber: `app/backend/services/ai_reasoning_payload.py::build_payload()`.
Dikirim sebagai **teks JSON polos** di `contents[0].parts[0].text` — Gemini
membacanya sebagai satu blok data, sepenuhnya dipandu oleh system instruction
di atas (tidak ada structured `contents` per field).

### Bentuk payload

```jsonc
{
  "cust_id": "CUST-00029",
  "as_of": "2026-08-06",
  "available_models": ["recovery", "self_cure", "roll_forward", "ptp_success"],

  "customer_profile": {
    "behavioral_grade": "D",
    "b_list_status": "Y",
    "active_contract_count": 3,
    "total_active_ots": 32742000.0,
    "cbs_as_of": "2026-08-06T11:23:58.085030",
    "ptp_reliability_index": 0.0,          // dihilangkan kalau NULL, bukan dikirim null
    "collection_sensitivity": "WA"          // dihilangkan kalau NULL, bukan dikirim null
  },

  "portfolio_rollup": {
    "worst_dpd": 136,
    "contracts_in_arrears": 3,
    "arrears_ots_share": 1.0,
    "nba_spread": ["Somasi", "Visit", "WA"],
    "worst_risk_segment": "Won't Pay",
    "worst_cycle": "C3+",
    "ots_weighted_recovery_score": 0.4362,
    "max_roll_forward_risk_prob_not_paying": 0.8029
  },

  "contracts": [
    {
      "contract_no": "CTR-00029-3",
      "product_type": "Elektronik & Furnitur",
      "dpd_current": 136,
      "cycle": "C3+",
      "overdue_installment_count": 3,
      "installment_amount": 920000.0,
      "total_ots": 13800000.0,
      "late_fee_amount": 0.0,
      "recent_payments": [
        { "due_date": "2026-03-23", "actual_pay_date": "2026-03-23", "pay_status": "Partial", "delay_days": 0 }
        // ...maks 6 baris terakhir, hanya yang BENAR-BENAR terjadi
      ],
      "risk_segment": "Won't Pay",
      "recovery_score": 0.2463,
      "self_cure_probability": 0.0721,          // BARU di v2 (E1) — sebelumnya tidak dikirim
      "ptp_success_probability": 0.1105,        // BARU di v2 (E1) — sebelumnya tidak dikirim
      "roll_forward_risk_prob_not_paying": 0.8029, // BARU di v2 (E1) — nama self-describing, sama pola dengan rollup
      "nba_recommendation": "Somasi",
      "nba_trigger": "base:wont_pay_mid_ots"
    }
    // ...satu objek per kontrak AKTIF debitur ini
  ]
}
```

> **Catatan v2 (E1):** payload di atas ditulis sebelum perbaikan "lengkapi skor
> model" — dulu `available_models` mengiklankan 4 model tapi hanya
> `recovery_score` yang benar-benar dikirim per kontrak. Tiga baris berkomentar
> "BARU di v2" di atas menunjukkan field yang sekarang ditambahkan; nilainya
> ilustratif (bukan dari payload asli yang di-capture, karena payload asli
> berasal dari sebelum perbaikan ini ada).

> Contoh di atas adalah payload nyata (disamarkan `cust_id`) hasil generate
> langsung dari `build_payload()` terhadap data live — bukan data rekaan.

### Kamus field

| Blok | Field | Arti | Kenapa bentuknya begitu |
|---|---|---|---|
| root | `available_models` | Model scoring yang punya champion (dibaca dari `app/machine-learning/models/registry.json`) | Backend **tidak pernah** meng-`import` modul ML ke prosesnya sendiri — dibaca sebagai JSON mentah, konsisten dengan pola `ai_intelligence_sync_service.py::_has_champion()` |
| `customer_profile` | `behavioral_grade`, `b_list_status` | Grade A–D dan status blacklist dari CBS | — |
| `customer_profile` | `ptp_reliability_index`, `collection_sensitivity` | Bisa `NULL` walau baris CBS ada (belum pernah PTP / belum ada channel dominan) | **Key dihilangkan seluruhnya**, bukan dikirim `null` — supaya "tidak diketahui" tidak terlihat seperti fakta bernilai nol |
| `portfolio_rollup` | `worst_dpd`, `worst_cycle`, `worst_risk_segment` | `MAX()` lintas seluruh kontrak aktif | Urgensi debitur = urgensi kontrak terparahnya, bukan rata-rata |
| `portfolio_rollup` | `nba_spread` | Set unik `nba_recommendation` lintas kontrak | Kalau panjangnya >1 → sinyal konflik nyata yang wajib direkonsiliasi (lihat system instruction) |
| `portfolio_rollup` | `ots_weighted_recovery_score` | Rata-rata `recovery_score`, dibobot `principal_ots + interest_ots` per kontrak | Kontrak bernilai besar lebih dominan daripada rata-rata polos |
| `portfolio_rollup` | `max_roll_forward_risk_prob_not_paying` | `roll_forward_risk` tersimpan **terbalik** di DB (P(tidak bayar), bukan P(bayar)) | Nama field dibuat *self-describing* supaya arahnya tidak bisa disalahtafsirkan tanpa baca dokumentasi lain |
| `contracts[]` | `nba_recommendation` + `nba_trigger` | Rekomendasi rule-engine + label cabang mana yang memicunya (mis. `base:wont_pay_mid_ots`, `override:collection_sensitivity`) | `nba_trigger` memberi Gemini "alasan" di balik rekomendasi, supaya bisa dinilai apakah alasan itu masih relevan saat dilihat gabungan — bukan cuma menerima output rule engine mentah |
| `contracts[]` | `recent_payments` | Maks 6 baris terakhir | Hanya pembayaran yang **terjadi** — lihat aturan wajib di system instruction |

**Sengaja TIDAK dikirim:**
- `historical_default_count` / `income_debt_ratio` — fitur *model*, bukan fakta naratif untuk LLM (concern berbeda, lihat §1.1 `ai-reasoning-api-upgrade-tasks.md`).
- Ringkasan kontrak **lunas** 3 tahun terakhir — direncanakan di §8.1 dokumen desain, ditunda sebagai task terpisah (payload sekarang hanya kontrak **aktif**).

---

## 4. Response schema (dipaksa, bukan diminta)

Sumber: `ai_reasoning_prompt.py::build_response_schema()`. Ini dikirim di
`generationConfig.responseSchema` dengan `responseMimeType: "application/json"`
— Gemini **dipaksa** JSON mode mengikuti skema ini, bukan sekadar diminta lewat
teks:

```json
{
  "type": "OBJECT",
  "properties": {
    "summary": { "type": "STRING" },
    "customerTreatmentStrategy": { "type": "STRING" },
    "keyFactors": { "type": "ARRAY", "items": { "type": "STRING" } },
    "primaryNbaAction": {
      "type": "STRING",
      "enum": ["WA", "Deskcoll", "Visit", "Somasi", "Pickup"]
    },
    "primaryNbaRationale": { "type": "STRING" },
    "perContractFocus": {
      "type": "ARRAY",
      "items": {
        "type": "OBJECT",
        "properties": {
          "contractNo": { "type": "STRING" },
          "urgency": { "type": "STRING", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
          "note": { "type": "STRING" }
        },
        "required": ["contractNo", "urgency", "note"]
      }
    },
    "consistencyNote": { "type": "STRING" }
  },
  "required": [
    "summary", "customerTreatmentStrategy", "keyFactors",
    "primaryNbaAction", "primaryNbaRationale",
    "perContractFocus", "consistencyNote"
  ]
}
```

> **Catatan v2:** `nbaAgreement` (AGREE/DIFFER) DIHAPUS dari skema ini.
> Sebelumnya LLM diminta menilai sendiri apakah pilihannya "setuju" dengan rule
> engine, padahal kata itu tidak pernah didefinisikan di system instruction
> manapun — model menebak semantiknya dari nama field, dan hasilnya tidak bisa
> diverifikasi. Field `nba_agreement` di response API (§5) **tetap ada**, tapi
> sekarang dihitung deterministik di `ai_reasoning_service.py`: `AGREE` kalau
> `primaryNbaAction` ada di `nba_spread` (§3), `DIFFER` kalau tidak, `None`
> kalau `nba_spread` kosong (tidak ada rekomendasi rule untuk dibandingkan).

Field ini dikirim dalam **camelCase** (kontrak Gemini), lalu dikonversi ke
`snake_case` untuk API publik backend — lihat §5.

---

## 5. Contoh nyata ujung ke ujung

> **Catatan v2:** contoh di bawah adalah panggilan nyata dari `PROMPT_VERSION="v1"`
> (sebelum payload dilengkapi §1.1/E1 dan sebelum `nbaAgreement` dihapus/E2).
> `nbaAgreement` di respons ini adalah nilai self-report LLM lama — pada v2,
> field yang sama (`nba_agreement` di response API) dihitung server-side, lihat
> catatan v2 di §4. Bentuk respons lainnya (summary, keyFactors, dst) tidak
> berubah.

Payload di §3 (untuk debitur 3-kontrak dengan `nba_spread: ["Somasi","Visit","WA"]`,
kontrak terparah `Won't Pay` DPD 136) menghasilkan output nyata berikut dari
Gemini (`gemini-3.6-flash`, uji langsung dengan API key asli):

```json
{
  "summary": "Debitur CUST-00607 memiliki 3 kontrak aktif yang seluruhnya menunggak dengan DPD terburuk 136 hari (C3+), segmen risiko terburuk Won't Pay, status B-list Y, dan total OTS Rp32.742.000.",
  "customerTreatmentStrategy": "Lakukan penanganan tegas melalui pengiriman Somasi secara terkonsolidasi untuk menekan debitur agar segera menyelesaikan seluruh tunggakan pada ketiga kontrak.",
  "keyFactors": [
    "DPD terburuk mencapai 136 hari (C3+) pada segmen Won't Pay",
    "Status B-list Y dengan indeks keandalan PTP 0.0",
    "Probabilitas risiko tidak membayar mencapai 80.29%",
    "Seluruh 3 kontrak aktif mengalami keterlambatan pembayaran"
  ],
  "primaryNbaAction": "Somasi",
  "primaryNbaRationale": "Mengingat tingkat tunggakan sudah masuk kategori C3+ (DPD 136), risiko Won't Pay, serta PTP reliability 0.0, tindakan tegas melalui Somasi diperlukan untuk memberikan dorongan hukum dan komitmen pembayaran.",
  "nbaAgreement": "AGREE",
  "perContractFocus": [
    { "contractNo": "CTR-00607-3", "urgency": "CRITICAL", "note": "DPD 136 hari, segmen Won't Pay dengan total OTS Rp13.800.000. Menjadi pemicu utama eskalasi tindakan Somasi." },
    { "contractNo": "CTR-00607-1", "urgency": "CRITICAL", "note": "DPD 132 hari, segmen Cannot Pay dengan 4 angsuran tertunggak dan total OTS Rp11.935.000." },
    { "contractNo": "CTR-00607-2", "urgency": "LOW", "note": "DPD 9 hari, segmen Can Pay. Dilibatkan dalam penyelesaian konsolidasi total tunggakan." }
  ],
  "consistencyNote": "NBA Spread mencakup WA, Visit, dan Somasi. Karena strategi didasarkan pada risiko kontrak terburuk (DPD 136, Won't Pay), maka ditetapkan Somasi sebagai tindakan tunggal utama, mengabaikan preferensi saluran WA debitur karena keparahan kondisi portofolio."
}
```

Observabilitas dari panggilan ini (tersimpan di `ai_reasoning_output`):
**1892 prompt token + 491 completion token (total 4094 di `usageMetadata`)**,
**latensi 11.3 detik**, `model_used: "gemini-3.6-flash"`.

---

## 6. Lapisan keamanan setelah respons kembali

Tidak ada yang disimpan mentah — respons Gemini melewati dua validasi berlapis
sebelum masuk `ai_reasoning_output`:

1. **Parse JSON** (`parse_response_text`) — gagal parse (`json.JSONDecodeError`)
   → status `FALLBACK`.
2. **Validasi ulang ke Pydantic** (`GeminiReasoningOutputSchema.model_validate()`,
   `app/backend/schemas/ai_reasoning.py`) — meski sudah dipaksa `responseSchema`
   di sisi Gemini, tetap divalidasi ulang di sisi backend. Enum tidak dikenal,
   field wajib hilang, dsb → `ValidationError` → status `FALLBACK`, **bukan**
   disimpan mentah dan **bukan** membuat endpoint 500.

`FALLBACK` sendiri bukan kosong — service membangun template rule-based dari
kontrak dengan OTS terbesar (`risk_segment` + `nba_recommendation` yang **sudah
ada** di DB), diberi label jelas `"[Template otomatis — bukan hasil analisa
AI]"` di `summary`, supaya frontend bisa merender badge yang membedakannya dari
hasil AI asli (lihat `AiReasoningCard.tsx`).

---

## 7. Versioning & cache

`PROMPT_VERSION = "v2"` (di `ai_reasoning_prompt.py`) adalah bagian dari
`UNIQUE (cust_id, source_signature, prompt_version)` di tabel
`ai_reasoning_output`. Begitu system instruction atau response schema di atas
berubah secara substantif, **versi ini wajib dinaikkan** — supaya:

- Histori hasil dari prompt versi lama tidak pernah tertimpa hasil versi baru.
- Cache tidak salah mengira hasil versi prompt lama masih valid untuk versi
  baru (GET/POST selalu menyaring `WHERE prompt_version = PROMPT_VERSION`
  yang berlaku saat ini).
- Model Health (`success_rate_7d` di halaman AI Intelligence) bisa menghitung
  rasio OK/FALLBACK/FAILED yang benar-benar mencerminkan prompt yang sedang aktif.

`source_signature` sendiri (hash `sha256` dari `sorted (contract_no,
scoring_date)` seluruh kontrak aktif debitur) yang menentukan basi-tidaknya
cache **di dalam** satu `prompt_version` yang sama — lihat
`ai_reasoning_payload.py::compute_source_signature()`.

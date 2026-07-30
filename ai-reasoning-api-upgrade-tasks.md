# CollectAI — Upgrade "AI Reasoning" jadi Analisa Nyata Berbasis Data Customer (Task List untuk Review)

**Status: BELUM diimplementasikan.** Revisi final — semua keputusan arsitektur sudah dijawab.

## Ringkasan keputusan

| # | Keputusan |
|---|---|
| 1 | **LLM eksternal — Google AI Studio (Gemini API)**, bukan self-hosted. |
| 2 | **On-demand + cache**, dipicu manual lewat tombol di Customer Detail (bukan otomatis saat halaman dibuka). |
| 3 | Cache valid sampai `scoring_date` berubah — tidak ada TTL tambahan (rekomendasi saya dipakai). |
| 4 | `targetNbaAction` dibatasi ke daftar aksi tetap (rekomendasi saya dipakai) — contoh input/output ada di bawah. |
| 5 | Provider dikonfirmasi: **Google AI Studio**. |

---

## 1. LLM: Google AI Studio (Gemini API) ✅ **DIPUTUSKAN**

Ini eksternal API (bukan self-hosted) — konsekuensinya:
- Data customer yang sudah **teragregasi** (bukan raw PII) tetap terkirim ke server Google. Sesuai
  arahan Anda, ini diterima sebagai keputusan sadar — tidak saya perdebatkan ulang, cukup dicatat di
  sini supaya ada jejak keputusannya kalau nanti ditanya audit/compliance.
- Karena ini bukan model self-hosted, penyebutan **"Local LLM System Prompt"** di halaman AI
  Intelligence yang lama **tidak akurat lagi** — sudah diantisipasi lewat rename ke "Prompting
  Rules" di `frontend-layout-upgrade-tasks.md` TASK-F, jadi tidak perlu perubahan tambahan di sana.
- **API key** disimpan di `.env` root (pola yang sama seperti kredensial Postgres) — variabel baru
  mis. `GOOGLE_AI_STUDIO_API_KEY`, dimuat lewat `core/config.py` backend (dotenv, sama seperti
  `PGPASSWORD` dkk), **jangan hardcode**. Tambahkan ke `.env.example` sebagai placeholder.
- **Pilihan model Gemini**: pilih varian "flash" (murah, cepat — cocok untuk alur klik-generate yang
  butuh respons cepat) sebagai default, dengan opsi ganti ke varian "pro" lewat config kalau kualitas
  reasoning dirasa kurang. Nama model persisnya dicek saat implementasi (tergantung apa yang
  tersedia di AI Studio saat itu) — jangan di-hardcode di banyak tempat, taruh 1 constant di
  `model_governance_config` (menyatu dengan Prompting Rules, TASK-F) supaya bisa diganti tanpa
  deploy ulang.
- **Structured output**: Gemini API mendukung `responseSchema`/JSON mode (memaksa output sesuai
  skema JSON yang kita definisikan) — ini yang dipakai untuk memenuhi keputusan #4 (`targetNbaAction`
  dibatasi ke daftar tetap), bukan cuma "diminta baik-baik" lewat teks prompt. Lihat schema di
  bagian Output di bawah.

---

## 2. Timing: on-demand + cache, dipicu tombol di Customer Detail ✅ **DIPUTUSKAN**

**Desain UI** (sesuai deskripsi Anda): card lebar di Customer Detail, background biru gelap, isi
kosong dengan 1 tombol di tengah: **"Generate AI Reasoning & Analysis"**.

```
┌────────────────────────────────────────────────────────────────┐
│                                                                  │
│                 [ Generate AI Reasoning & Analysis ]            │  ← background biru gelap
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

**Perilaku:**
- Card ini **kosong secara default** setiap kali belum ada reasoning ter-cache yang masih valid
  untuk `scoring_date` kontrak saat ini.
- Klik tombol → memanggil endpoint (lihat di bawah) → card menampilkan **loading state** (LLM call
  butuh beberapa detik, bukan instan) → begitu selesai, isi card diganti jadi hasil reasoning
  (bukan tombol lagi).
- **Kunjungan berikutnya ke Customer Detail yang sama** (selama `scoring_date` belum berubah): card
  langsung menampilkan hasil yang sudah ter-cache, **tanpa perlu klik ulang** — tombol generate
  hanya muncul lagi kalau cache sudah basi (`scoring_date` berubah) atau memang belum pernah
  digenerate sama sekali. Ini konsisten dengan semangat "on-demand + cache" — generate sekali per
  siklus scoring, bukan tiap buka halaman.
- Endpoint dipanggil **hanya saat tombol diklik**, bukan otomatis bareng `GET /customers/{cust_id}`
  saat halaman dibuka — beda dari rancangan awal saya sebelumnya, ini yang mengoreksi.

**Endpoint (revisi dari GET jadi POST):**
```
POST /api/v1/customers/{cust_id}/ai-reasoning
```
Dipilih `POST` (bukan `GET` seperti draft awal saya) karena ini eksplisit sebuah **aksi** yang
dipicu user (tombol "Generate...") dan bisa memicu panggilan API berbayar ke pihak ketiga — secara
semantik lebih pas sebagai action endpoint. Tetap aman dipanggil berulang kali (idempotent secara
efek): kalau cache masih valid, langsung kembalikan cache tanpa panggil LLM lagi.

**Cara Customer Detail tahu harus tampilkan tombol atau hasil:** field ringan (mis.
`hasReasoning: boolean`, `reasoningStale: boolean`) disertakan di response `GET /customers/{cust_id}`
yang sudah ada, supaya frontend tidak perlu request tambahan hanya untuk tahu "harus tampil tombol
atau hasil" — begitu tahu ada hasil valid, frontend baru fetch isinya lewat endpoint yang sama di
atas (dipanggil dengan method yang sama, backend cukup pintar mengembalikan cache tanpa
regenerate).

---

## 3. Cache & staleness ✅ **DIPUTUSKAN (rekomendasi saya dipakai)**

Valid **sampai `scoring_date` kontrak berubah** (dari `ai_intelligence_output.scoring_date`) — tidak
ada TTL tambahan berbasis waktu maupun trigger dari kontak/pembayaran baru. Simpel untuk fase
pertama; kalau nanti dirasa reasoning terlalu cepat "basi rasanya" meski `scoring_date` belum
berubah (mis. ada kontak besar di antara siklus scoring), bisa ditambah trigger lain belakangan.

Tabel `ai_reasoning_output` (tidak berubah dari draft sebelumnya): `contract_no`, `cust_id`,
`generated_at`, `source_scoring_date`, `prompt_version`, `model_used`, `status`
(`OK`/`FAILED`/`FALLBACK`), plus kolom isi (lihat schema Output di bawah, bukan 1 kolom teks lagi).

---

## 4. Output terstruktur + Contoh Konkret Input/Output ✅ **DIPUTUSKAN (rekomendasi saya dipakai)**

Karena tombolnya "Generate AI Reasoning **& Analysis**" (bukan cuma 1 kalimat justifikasi), saya
perluas skema output dari draft sebelumnya — sekarang mencakup ringkasan analisis + faktor kunci +
next-best-action (dibatasi enum) + rekomendasi tindakan, supaya 1 card ini juga menggantikan fungsi
`aiReasoning`/`aiRecommendations` yang dulu ada di Collector Workbench (yang sudah dihapus, lihat
`frontend-layout-upgrade-tasks.md` TASK-A) — jadi tidak ada 2 tempat terpisah untuk hal yang mirip.

### Contoh input (konteks yang dikirim backend ke Gemini)

Contoh untuk `CUST-00029` / `CTR-00029-1`, dengan 3 grup data field default-ON dari TASK-F (Skor &
Segmentasi, Status Perilaku/CBS, Riwayat Pembayaran) plus Riwayat Kontak (grup opsional, saya
nyalakan di contoh ini biar lebih kaya):

```json
{
  "cust_id": "CUST-00029",
  "contract_no": "CTR-00029-1",
  "scoring": {
    "recovery_score": 0.42,
    "risk_segment": "Cannot Pay",
    "self_cure_probability": 0.18,
    "roll_forward_risk": 0.71,
    "ptp_success_probability": 0.35,
    "nba_recommendation": "Personalized SMS Hook",
    "confidence_level": 0.81
  },
  "behavioral": {
    "behavioral_grade": "C",
    "ptp_reliability_index": 0.40,
    "b_list_status": "N",
    "restructure_count": 0
  },
  "payment_pattern_last_6_months": {
    "full": 2,
    "partial": 1,
    "late_or_missed": 3,
    "self_cure_flag_rate": 0.10
  },
  "contact_summary_last_90_days": {
    "total_contacts": 8,
    "contact_success_rate": 0.375,
    "ptp_kept": 1,
    "ptp_broken": 2,
    "most_responsive_channel": "WhatsApp"
  }
}
```

(Kalau grup "Riwayat Kontak/Interaksi" dimatikan di Prompting Rules — default-nya OFF — bagian
`contact_summary_last_90_days` ini tidak ikut dikirim sama sekali.)

### Instruksi ke model (disederhanakan dari Prompting Rules)

> "Anda analis kredit yang membantu petugas collection. Berdasarkan data JSON berikut, buat ringkasan
> analisis risiko, daftar faktor kunci yang mendasari, dan rekomendasi tindakan. `targetNbaAction`
> WAJIB salah satu dari: [`Personalized SMS Hook`, `Priority Call - Senior Collector`,
> `WhatsApp Reminder`, `Offer Restructuring Review`, `Legal Notice Escalation`, `Monitor - No Action`].
> Jawab dalam Bahasa Indonesia, singkat dan berbasis data yang diberikan — jangan mengarang angka
> yang tidak ada di input."

(Daftar enum di atas contoh ilustratif — daftar final perlu disepakati dengan tim collection saat
implementasi, kemungkinan besar tumpang tindih dengan nilai `nba_recommendation` yang sudah ada di
`ai_intelligence_output`.)

### Contoh output (dipaksa lewat `responseSchema` Gemini, bukan cuma diminta di teks prompt)

```json
{
  "summary": "Nasabah menunjukkan pola pembayaran yang memburuk dalam 6 bulan terakhir (3 dari 6 bulan telat/tidak bayar), dengan tingkat keberhasilan kontak hanya 37.5% meski sudah dihubungi 8 kali dalam 90 hari terakhir. Dari 3 janji bayar terakhir, 2 di antaranya gagal ditepati. Skor roll-forward risk yang tinggi (0.71) mengindikasikan risiko kontrak ini naik ke bucket DPD berikutnya cukup besar, sementara kemungkinan self-cure tergolong rendah (18%), sehingga intervensi aktif lebih disarankan dibanding menunggu.",
  "keyFactors": [
    "3 dari 6 bulan terakhir pembayaran telat atau tidak bayar",
    "2 dari 3 janji bayar (PTP) terakhir gagal ditepati",
    "Roll-forward risk tinggi (0.71) — indikasi risiko naik bucket DPD",
    "Self-cure probability rendah (18%) — kecil kemungkinan membaik sendiri"
  ],
  "targetNbaAction": "Personalized SMS Hook",
  "recommendedActions": [
    "Kirim pengingat lewat WhatsApp (channel paling responsif untuk nasabah ini)",
    "Jika kontak berikutnya masih gagal, pertimbangkan eskalasi ke opsi restrukturisasi"
  ]
}
```

**Tampilan di card** (menggantikan tombol setelah generate selesai): paragraf `summary` di atas,
bullet list `keyFactors`, badge `targetNbaAction`, bullet list `recommendedActions`. Field
`confidence_level` dari input **tidak perlu ditampilkan mentah ke user** — cukup dipakai internal
untuk nge-log kualitas, kecuali Anda mau ditampilkan juga (beri tahu kalau iya).

---

## 5. Fallback tetap seperti draft sebelumnya

Kalau panggilan Gemini gagal/timeout, tampilkan fallback rule-based (template dari `risk_segment` +
`nba_recommendation` yang sudah ada di `ai_intelligence_output`) supaya card tidak pernah kosong
error — tandai `status: FALLBACK` di `ai_reasoning_output` untuk dipantau di Model Health
(`frontend-layout-upgrade-tasks.md` TASK-F).

---

## Rancangan alur (final)

```
User klik "Generate AI Reasoning & Analysis" di Customer Detail
        │
        ▼
POST /api/v1/customers/{cust_id}/ai-reasoning
        │
        ▼
services/ai_reasoning_service.py
        │
        ├─ ada di ai_reasoning_output & source_scoring_date == scoring_date terkini? ──► kembalikan cache
        │
        └─ tidak ada / basi:
                ├─ kumpulkan konteks sesuai grup data field yang ON (dari model_governance_config)
                ├─ panggil Gemini API (Google AI Studio) dengan system prompt versi terbaru +
                │  responseSchema yang memaksa bentuk output di atas
                ├─ simpan ke ai_reasoning_output (status OK)
                └─ kalau gagal → simpan+kembalikan fallback rule-based, status=FALLBACK
```

---

## Yang TIDAK termasuk scope dokumen ini (tidak berubah)

- Field `aiReasoning`/`aiRecommendations` terpisah di Collector Workbench — sudah tidak relevan,
  Workbench dihapus total (`frontend-layout-upgrade-tasks.md` TASK-A), fungsinya melebur ke card ini.
- Prompt engineering detail / isi system prompt final — itu diedit lewat Prompting Rules
  (`frontend-layout-upgrade-tasks.md` TASK-F), bukan bagian desain teknis di sini.
- Integrasi WhatsApp/Email template otomatis — fitur terpisah (outbound messaging).

---

## Catatan penutup

Tidak ada pertanyaan terbuka tersisa untuk desain ini. Satu hal kecil untuk fase implementasi nanti
(bukan keputusan produk): daftar enum `targetNbaAction` di contoh atas masih ilustratif — perlu
difinalkan bersama tim collection sebelum `responseSchema` Gemini benar-benar dikunci di kode.

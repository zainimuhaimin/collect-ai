"""Prompt & response schema untuk AI Reasoning (ai-reasoning-api-upgrade-tasks.md).

`PROMPT_VERSION` dinaikkan setiap kali instruksi/skema di bawah berubah secara
substantif — nilai ini ikut `source_signature` menentukan cache basi/tidaknya
di ai_reasoning_output (lihat ai_reasoning_service.py).

Grup data field yang aktif TIDAK menunggu TASK-F Prompting Rules (yang belum
ada kodenya — model_governance_config hanya punya 1 config_key terpakai:
'cbs_weights'). Konstanta di bawah adalah default fase 1; TASK-F nanti tinggal
menampilkan/mengedit nilai ini lewat config_key kedua, bukan prasyarat."""
from __future__ import annotations

import json

# v1 -> v2 (post-presentation-review-tasks.md TASK-E2/E3): (1) nbaAgreement
# dihapus dari response schema — dihitung deterministik di
# ai_reasoning_service.py, bukan lagi self-report LLM; (2) klaim "rule engine
# tidak pernah menghasilkan Pickup" diperbaiki — TERBUKTI SALAH lewat query
# nyata setelah perbaikan historical_default_count (Fase 0): 10 dari 711
# kontrak (1,4%) di run verifikasi 2026-08-11 menghasilkan Pickup
# (SELECT nba_recommendation, count(*) FROM ai_intelligence_output GROUP BY 1).
PROMPT_VERSION = "v2"

# SAMA dengan app/machine-learning/src/business_rules.py:27 CHANNEL_RANK.
# TIDAK di-import langsung — backend SENGAJA tidak mengimpor modul ml/ ke
# prosesnya sendiri (lihat komentar ai_intelligence_sync_service.py soal
# _has_champion() yang membaca registry.json mentah alih-alih model_registry.py,
# dan governance_repository.py yang mendup WEIGHT_PAYMENT_RATE dkk dengan
# catatan yang sama). Kalau CHANNEL_RANK berubah di sana, perbarui juga di sini.
NBA_ACTIONS = ["WA", "Deskcoll", "Visit", "Somasi", "Pickup"]

_SYSTEM_INSTRUCTION_TEMPLATE = """Anda analis kredit yang membantu petugas collection di perusahaan multifinance Indonesia. Data JSON berikut adalah profil SATU DEBITUR yang mungkin memiliki beberapa kontrak.

Tugas Anda: tentukan SATU strategi penanganan yang konsisten untuk debitur ini sebagai satu orang, bukan rekomendasi terpisah per kontrak.

Aturan wajib:
- primaryNbaAction HARUS salah satu dari: {nba_actions}. Hanya SATU — debitur ini satu orang, tidak masuk akal menghubunginya lewat beberapa channel bertentangan di waktu yang sama.
- Kalau nba_spread pada portfolio_rollup berisi lebih dari satu nilai, itu berarti kontrak-kontraknya punya rekomendasi berbeda. Rekonsiliasi, dan jelaskan alasannya di consistencyNote.
- Urgensi mengikuti kontrak TERBURUK (field worst_* pada portfolio_rollup), bukan rata-rata.
- Pertimbangkan collection_sensitivity pada customer_profile sebagai preferensi channel debitur; boleh menyimpang kalau tingkat keparahan menuntut, tapi sebutkan alasannya.
- payment_history di setiap kontrak hanya mencatat pembayaran yang TERJADI; angsuran yang tidak dibayar TIDAK muncul sebagai baris. Nilai tunggakan dari dpd_current dan overdue_installment_count pada kontrak, JANGAN disimpulkan dari jumlah baris pembayaran.
- nba_recommendation per kontrak adalah hasil rule engine deterministik dengan cakupan terbatas — ia HANYA menghasilkan "Pickup" pada kondisi yang sangat sempit (segmen won't-pay, saldo besar, riwayat gagal bayar berulang), dan tidak mempertimbangkan portofolio debitur secara keseluruhan. Perlakukan sebagai rekomendasi sistem saat ini yang perlu Anda rekonsiliasi, BUKAN sebagai batas atas tindakan yang boleh Anda usulkan — Anda boleh mengusulkan tindakan yang lebih ringan ATAU lebih berat dari nba_recommendation kalau data portofolio menuntutnya. nba_trigger menjelaskan kondisi apa yang memicu rekomendasi itu — nilai apakah alasannya masih berlaku ketika seluruh kontrak debitur dilihat bersamaan.
- Field yang TIDAK ADA di JSON berarti tidak tersedia — jangan diasumsikan nol, dan jangan mengarang angka yang tidak ada di input. available_models memberi tahu model skor apa yang tersedia; skor dari model yang tidak terdaftar memang tidak ada, bukan bernilai rendah.

Jawab dalam Bahasa Indonesia, ringkas, berbasis data yang diberikan."""


def build_instruction() -> str:
    return _SYSTEM_INSTRUCTION_TEMPLATE.format(nba_actions=", ".join(NBA_ACTIONS))


def build_response_schema() -> dict:
    """Skema JSON dipaksa lewat generationConfig.responseSchema Gemini (JSON
    mode) — bukan cuma diminta lewat teks prompt. Tetap divalidasi ulang ke
    Pydantic (schemas/ai_reasoning.py) sebelum disimpan; pelanggaran skema di
    sisi Gemini sendiri seharusnya tidak lolos, tapi validasi ulang tetap
    wajib (jangan percaya buta pada satu lapis saja).

    TIDAK ADA field nbaAgreement (AGREE/DIFFER) di sini secara sengaja — versi
    lama meminta LLM menilai sendiri apakah pilihannya "setuju" dengan rule
    engine, padahal kata itu tidak pernah didefinisikan di system instruction
    manapun, sehingga model menebak semantiknya dari nama field dan hasilnya
    tidak bisa diverifikasi. Sekarang dihitung deterministik di
    ai_reasoning_service.py: AGREE kalau primaryNbaAction ada di nba_spread
    (compute_nba_spread di ai_reasoning_payload.py), DIFFER kalau tidak, None
    kalau nba_spread kosong (tidak ada rekomendasi rule untuk dibandingkan)."""
    return {
        "type": "OBJECT",
        "properties": {
            "summary": {"type": "STRING"},
            "customerTreatmentStrategy": {"type": "STRING"},
            "keyFactors": {"type": "ARRAY", "items": {"type": "STRING"}},
            "primaryNbaAction": {"type": "STRING", "enum": NBA_ACTIONS},
            "primaryNbaRationale": {"type": "STRING"},
            "perContractFocus": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "contractNo": {"type": "STRING"},
                        "urgency": {"type": "STRING", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                        "note": {"type": "STRING"},
                    },
                    "required": ["contractNo", "urgency", "note"],
                },
            },
            "consistencyNote": {"type": "STRING"},
        },
        "required": [
            "summary", "customerTreatmentStrategy", "keyFactors",
            "primaryNbaAction", "primaryNbaRationale",
            "perContractFocus", "consistencyNote",
        ],
    }


def parse_response_text(text: str) -> dict:
    """Parse teks JSON mentah dari Gemini. Melempar json.JSONDecodeError kalau
    gagal — caller (ai_reasoning_service.py) menangkapnya sebagai FALLBACK,
    bukan meloloskan JSON rusak ke database."""
    return json.loads(text)

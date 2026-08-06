"""Gate kecukupan data (ai-reasoning-api-upgrade-tasks.md §8.2) — dievaluasi
SEBELUM memanggil Gemini. Kalau gagal, generate() TIDAK memanggil LLM sama
sekali: tidak membayar panggilan yang hanya bisa menghasilkan narasi kabur,
dan yang lebih penting, TIDAK menghasilkan halusinasi yang terdengar
meyakinkan di atas data yang sebenarnya tidak ada (temuan #16 — contoh nyata:
38/2000 debitur tanpa baris CBS akan ter-grade 'D' secara diam-diam kalau
nilai default dikirim sebagai fakta).

Pure function murni (tidak menyentuh DB sendiri) — payload builder yang
menyediakan data, gate ini hanya menilai. Ini membuatnya gampang dites tanpa
database sama sekali."""
from __future__ import annotations

from typing import List, Optional, Tuple

from domain.models import ContractDetail, CustomerBehavioralRaw

MIN_PAYMENT_ROWS = 3
MAX_ACTIVE_CONTRACTS = 15

# NOTE: kriteria "months_on_book kontrak tertua >= 3" di desain awal
# (§8.2 dokumen) TIDAK bisa diimplementasikan — contract_snapshot tidak
# punya kolom tanggal originasi/disbursement sama sekali, hanya
# maturity_date. Kriteria MIN_PAYMENT_ROWS sudah berfungsi sebagai proxy
# yang wajar: kontrak yang genuinely baru belum sempat mengumpulkan >=3
# baris pembayaran. Ini simplifikasi yang sama semangatnya dengan temuan
# "late_or_missed tidak mungkin dibangun" di dokumen — dicatat eksplisit,
# bukan didiamkan.


def data_sufficiency(
    behavioral: Optional[CustomerBehavioralRaw],
    active_contracts: List[ContractDetail],
) -> Tuple[bool, Optional[str]]:
    """Return (ok, reason). `reason` salah satu dari NO_CBS / TOO_FEW_PAYMENTS /
    NO_SCORE / TOO_MANY_CONTRACTS kalau ok=False, None kalau ok=True."""
    if behavioral is None or not behavioral.has_cbs_row:
        return False, "NO_CBS"

    if len(active_contracts) > MAX_ACTIVE_CONTRACTS:
        # Safety valve, bukan batas normal — data nyata menunjukkan maksimum
        # 3 kontrak aktif/debitur. >15 kemungkinan besar akun korporat/fleet
        # atau masalah integritas data, butuh penanganan manual.
        return False, "TOO_MANY_CONTRACTS"

    total_payments = sum(len(c.payment_history) for c in active_contracts)
    if total_payments < MIN_PAYMENT_ROWS:
        return False, "TOO_FEW_PAYMENTS"

    has_any_score = any(c.ai_scoring is not None for c in active_contracts)
    if not has_any_score:
        return False, "NO_SCORE"

    return True, None

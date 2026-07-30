"""
Restructuring Offer Calculator — Fase 1 (rule-based, deterministik)
CollectAI — Restructuring Recommendation Engine

SATU-SATUNYA salinan modul ini (app/shared/). Dulu ada 3 copy fisik (root,
app/backend/ml/, dan rencana app/machine-learning/business_rules/) yang
harus disinkronkan manual tiap ada revisi logika — sekarang app/backend/
dan app/machine-learning/ SAMA-SAMA meng-import dari sini, tidak ada lagi
salinan. Jangan copy-paste file ini ke tempat lain; import langsung
`from shared.restructuring_offer_calculator import ...` (lihat masing-masing
caller untuk cara wiring sys.path ke app/).

Modul ini HANYA menghitung angka tawaran secara deterministik, dan TIDAK
BOLEH mengimpor apapun dari app/backend/ (FastAPI dll) atau
app/machine-learning/ (config/settings.py dll) — kalau perlu policy dari
config masing-masing app, caller yang membangun `RestructurePolicy(...)`
lalu meneruskannya ke sini, bukan modul ini yang menariknya sendiri.

Model ML acceptance probability adalah lapisan TERPISAH yang baru
dibangun di Fase 2, setelah restructuring_history terkumpul cukup data
(lihat TASK-55 di restructuring-engine-tasks.md).

PENTING: apply_guardrail() adalah lapisan yang PERMANEN. Fase 2 nanti
hanya mengganti cara MERANKING kandidat (expected value = P(accept) x
npv_restructured), bukan menghapus guardrail ini.

── Tiga koreksi mendasar (audit 2026-07-30) ────────────────────────────
Sebelum ini engine menghasilkan tawaran yang secara sistematis LEBIH BERAT
bagi nasabah: 79.9% dari 2.802 tawaran nyata mengusulkan cicilan bulanan
LEBIH TINGGI (rata-rata 2,27x) dan 97,9% menaikkan total bayar (rata-rata
2,97x), sementara 100% lolos guardrail. Penyebabnya tiga hal yang saling
memperkuat, semuanya dikoreksi di modul ini:

1. Yang diamortisasi salah. `total_ots` = prnc_ots + intr_ots adalah
   kewajiban BRUTO, sudah termasuk bunga masa depan yang belum jatuh tempo.
   Memakainya sebagai POKOK berarti bunga baru ditumpuk di atas bunga lama.
   Sekarang yang diamortisasi `principal_ots` (lihat ContractInput) — dalam
   refinance, bunga sisa kontrak lama dibatalkan dan diganti bunga baru atas
   pokok terutang, itulah makna re-originasi.

2. Sisa tenor salah. Dulu dihitung dari `maturity_date` - hari ini, yang
   mengabaikan tunggakan: nasabah yang menunggak masih punya sisa cicilan
   jauh melebihi tanggal jatuh tempo kontraknya. Rata-rata ini menaksir
   TERLALU RENDAH sebanyak 7,3 bulan, sehingga saldo besar dipaksa masuk ke
   jendela pendek dan cicilannya meledak. Sekarang dipakai jumlah cicilan
   yang benar-benar masih terutang (lihat effective_remaining_tenor()).

3. Guardrail-nya tidak bisa gagal, dan tidak pernah menguji sisi nasabah.
   `npv_baseline` dikali recovery_score (~0,3 → diskon ~70%) sementara
   `npv_restructured` dibandingkan MENTAH — dua sisi yang tidak sebanding,
   rata-rata rasionya 22,1x. Sekarang kedua sisi risk-adjusted, DAN ada
   syarat manfaat nasabah yang eksplisit (cicilan harus turun, total bayar
   tidak boleh melonjak). Tawaran yang tidak memenuhinya di-BLOCK, tidak
   ditampilkan ke CS — lebih baik tidak ada tawaran daripada tawaran yang
   pasti ditolak dan merusak kredibilitas penawaran berikutnya.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ── POLICY CONFIG (harus sinkron dengan config/settings.py) ─────────

@dataclass(frozen=True)
class RestructurePolicy:
    max_haircut_pct: float = 0.40              # turun maks 40% relatif dari rate asal
    min_rate_floor: float = 0.09               # floor absolut ~cost of fund + margin
    max_tenor_extension_months: int = 24
    max_tenor_extension_ratio: float = 0.50    # atau maks 50% dari sisa tenor asli
    min_dpd_for_restructure: int = 30
    max_dpd_for_restructure: int = 180
    max_restructure_per_customer: int = 2
    asset_value_min_ratio: float = 0.50        # nilai aset min. tutup 50% OTS
    appraisal_max_age_months: int = 3
    consolidation_min_active_contracts: int = 2
    discount_rate_annual: float = 0.12         # dipakai utk NPV, BUKAN bunga kontrak

    # ── Syarat manfaat nasabah (guardrail sisi nasabah) ──────────────────
    # Cicilan baru minimal harus X lebih rendah dari cicilan sekarang. Bukan
    # sekadar ">0 lebih rendah": penurunan Rp1.411/bulan (kasus nyata di data
    # lama) secara teknis "lebih rendah" tapi tidak mungkin dijual sebagai
    # keringanan. 5% adalah batas terendah yang masih bisa dikalimatkan CS.
    min_installment_reduction_pct: float = 0.05
    # Kenaikan probabilitas bayar (poin absolut) yang diasumsikan didapat dari
    # jadwal yang lebih terjangkau. INI ASUMSI YANG HARUS EKSPLISIT, karena
    # tanpanya perbandingan NPV tidak masuk akal di kedua arah:
    #   - Perilaku lama: sisi restrukturisasi TIDAK didiskon sama sekali, sama
    #     dengan mengasumsikan p=100% — jadi selalu menang (rata-rata 22,1x).
    #   - Memakai recovery_score yang SAMA di kedua sisi: keringanan selalu
    #     mengurangi kas nominal, jadi tidak akan pernah lolos. Terbukti: dengan
    #     asumsi itu 392 dari 392 kontrak uji ditolak, padahal cicilannya
    #     benar-benar turun (mis. 298rb -> 196rb).
    # Justifikasi restrukturisasi memang terletak di sini: jadwal yang mampu
    # dibayar MENAIKKAN peluang bayar. 0,25 poin adalah placeholder konservatif
    # — GANTI dengan model performa pasca-restrukturisasi begitu
    # restructuring_history punya cukup data realisasi (Fase 2).
    restructure_recovery_uplift_pct: float = 0.25
    max_restructured_recovery: float = 0.95   # tidak pernah mengasumsikan pasti bayar
    # Memperpanjang tenor memang menaikkan total bayar — itu harga wajar dari
    # cicilan yang lebih ringan, jadi TIDAK diblokir. Yang diblokir adalah
    # lonjakan yang tidak proporsional (data lama rata-rata 2,97x).
    max_total_repayment_ratio: float = 1.50


# ── INPUT DATA CONTRACTS ──────────────────────────────────────────────

@dataclass
class ContractInput:
    contract_no: str
    cust_id: str
    product_type: str
    total_ots: float                # kewajiban BRUTO tersisa (pokok + bunga blm jatuh tempo)
    interest_rate: float            # annual, decimal, mis. 0.24 = 24% p.a.
    remaining_tenor_months: int     # dari maturity_date — TIDAK sadar tunggakan,
                                    # jangan dipakai langsung, lihat effective_remaining_tenor()
    installment_amount: float
    dpd_current: int
    risk_segment: str               # 'Cannot Pay' | 'Self Cure' | "Won't Pay"
    recovery_score: float
    self_cure_probability: float
    closed_via_restructure: bool = False
    # Pokok terutang saja (prnc_ots), TANPA bunga masa depan — INILAH yang
    # diamortisasi ulang. Default 0.0 = pemanggil tidak menyediakannya; kita
    # jatuh kembali ke total_ots supaya tidak crash, tapi hasilnya akan
    # menghitung bunga di atas bunga (lihat koreksi #1 di docstring modul),
    # jadi pemanggil sebaiknya SELALU mengisi ini.
    principal_ots: float = 0.0


@dataclass
class CustomerContext:
    cust_id: str
    b_list_status: str              # 'Y' / 'N'
    restructure_count: int
    active_contract_count: int


@dataclass
class AssetAppraisal:
    contract_no: str
    appraised_value: float
    appraisal_date: date


class OfferType(str, Enum):
    REFINANCE = "REFINANCE"
    CONSOLIDATE = "CONSOLIDATE"
    TAKEOVER = "TAKEOVER"


@dataclass
class RestructureOffer:
    offer_type: OfferType
    contract_nos: list[str]
    cust_id: str
    total_ots_combined: float
    recommended_new_tenor_months: int
    recommended_new_rate: float
    recommended_new_installment: float
    recovery_from_asset: float = 0.0
    npv_baseline: float = 0.0
    npv_restructured: float = 0.0
    # ── Tambahan display-only (Round 4 #6) — TIDAK dipakai guardrail/ranking,
    # yang tetap harus pakai npv_restructured mentah di atas (lihat
    # apply_guardrail() dan sort key di assess_restructuring_options()). ──
    npv_restructured_risk_adjusted: float = 0.0
    total_remaining_current: float = 0.0
    total_new_schedule: float = 0.0
    # Cicilan/bulan yang nasabah bayar SEKARANG (dijumlah lintas kontrak untuk
    # CONSOLIDATE). Wajib ada karena guardrail sisi nasabah membandingkan
    # recommended_new_installment terhadap angka ini — tanpa pembanding,
    # "cicilan baru" adalah angka tanpa makna.
    current_installment_total: float = 0.0
    is_guardrail_passed: bool = False
    rejection_reasons: list[str] = field(default_factory=list)


# ── ELIGIBILITY — TIERED, BUKAN GATE BINER ──────────────────────────────
# AUTO           → lolos semua kriteria standar, daily batch boleh mendorong
#                  ke collector secara otomatis (proaktif).
# MANUAL_REVIEW  → angka TETAP DIHITUNG. Dipakai saat backend query on-demand
#                  per customer — CS/supervisor bisa lihat opsinya, tapi perlu
#                  approval sebelum benar-benar ditawarkan ke nasabah.
# BLOCKED        → data tidak valid/tidak cukup untuk dihitung sama sekali.
#                  Ini SATU-SATUNYA tier yang tidak menghasilkan angka.

class EligibilityTier(str, Enum):
    AUTO = "AUTO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass
class EligibilityResult:
    tier: EligibilityTier
    reasons: list[str] = field(default_factory=list)


def classify_eligibility(
    contract: ContractInput, customer: CustomerContext, policy: RestructurePolicy
) -> EligibilityResult:
    # ── BLOCKED: murni masalah data/status kontrak, BUKAN judgment bisnis ──
    blocked_reasons: list[str] = []
    if contract.closed_via_restructure:
        blocked_reasons.append("kontrak sudah ditutup lewat restrukturisasi sebelumnya")
    if contract.interest_rate is None or contract.interest_rate <= 0:
        blocked_reasons.append("interest_rate tidak valid — tidak bisa hitung amortisasi")
    if contract.total_ots is None or contract.total_ots <= 0:
        blocked_reasons.append("total_ots tidak valid")

    if blocked_reasons:
        return EligibilityResult(tier=EligibilityTier.BLOCKED, reasons=blocked_reasons)

    # ── MANUAL_REVIEW: judgment bisnis — angka tetap dihitung di bawah ──────
    review_reasons: list[str] = []
    if contract.risk_segment != "Cannot Pay":
        review_reasons.append(f"risk_segment '{contract.risk_segment}' bukan target standar")
    if customer.b_list_status == "Y":
        review_reasons.append("nasabah B_LIST — butuh approval manual")
    if contract.self_cure_probability >= 0.70:
        review_reasons.append("self_cure_probability tinggi — pertimbangkan biarkan self-cure")
    if not (policy.min_dpd_for_restructure <= contract.dpd_current <= policy.max_dpd_for_restructure):
        review_reasons.append(
            f"DPD {contract.dpd_current} di luar window standar "
            f"({policy.min_dpd_for_restructure}-{policy.max_dpd_for_restructure})"
        )
    if customer.restructure_count >= policy.max_restructure_per_customer:
        review_reasons.append(f"restructure_count ({customer.restructure_count}) sudah mencapai batas standar")

    if review_reasons:
        return EligibilityResult(tier=EligibilityTier.MANUAL_REVIEW, reasons=review_reasons)

    return EligibilityResult(tier=EligibilityTier.AUTO, reasons=[])


# ── AMORTISASI & NPV HELPER ────────────────────────────────────────────

def calculate_installment(principal: float, annual_rate: float, tenor_months: int) -> float:
    """Reducing-balance / annuity. Kalau produk pakai flat rate, ganti fungsi
    ini di implementasi final — jangan campur dua metode dalam satu engine."""
    if tenor_months <= 0:
        return principal
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / tenor_months
    factor = (1 + monthly_rate) ** tenor_months
    return principal * monthly_rate * factor / (factor - 1)


def npv_of_installments(installment: float, tenor_months: int, annual_discount_rate: float) -> float:
    monthly_discount = annual_discount_rate / 12
    return sum(installment / ((1 + monthly_discount) ** m) for m in range(1, tenor_months + 1))


def restructured_recovery_probability(recovery_score: float, policy: RestructurePolicy) -> float:
    """Peluang jadwal BARU benar-benar terbayar. Sengaja fungsi terpisah supaya
    asumsi kunci ini punya satu tempat untuk diganti model Fase 2 — lihat
    RestructurePolicy.restructure_recovery_uplift_pct untuk alasannya."""
    return min(
        policy.max_restructured_recovery,
        max(0.0, recovery_score) + policy.restructure_recovery_uplift_pct,
    )


def amortizable_principal(contract: ContractInput) -> float:
    """Pokok yang boleh diamortisasi ulang — lihat koreksi #1 di docstring
    modul. `total_ots` mengandung bunga masa depan yang belum jatuh tempo;
    memakainya sebagai pokok menumpuk bunga di atas bunga."""
    if contract.principal_ots and contract.principal_ots > 0:
        return contract.principal_ots
    return contract.total_ots


def effective_remaining_tenor(contract: ContractInput) -> int:
    """Jumlah cicilan yang MASIH TERUTANG, bukan jarak ke maturity_date.

    Nasabah menunggak punya sisa cicilan melebihi tanggal jatuh tempo
    kontraknya — `remaining_tenor_months` (turunan maturity_date) mengabaikan
    itu dan rata-rata menaksir terlalu rendah 7,3 bulan pada data nyata,
    sehingga saldo besar dipaksa masuk jendela pendek dan cicilan barunya
    meledak (lihat koreksi #2 di docstring modul). Kewajiban bruto dibagi
    besar cicilan memberi jumlah cicilan tersisa yang sebenarnya.

    maturity_date hanya dipakai sebagai fallback kalau installment_amount
    tidak tersedia/nol — tanpa itu rasio ini tidak bisa dihitung."""
    if contract.installment_amount and contract.installment_amount > 0 and contract.total_ots > 0:
        return max(1, round(contract.total_ots / contract.installment_amount))
    return max(1, contract.remaining_tenor_months)


# ── CABANG 1: REFINANCE ────────────────────────────────────────────────

def calculate_refinance_offer(contract: ContractInput, policy: RestructurePolicy) -> RestructureOffer:
    base_tenor = effective_remaining_tenor(contract)
    tenor_ext = min(
        policy.max_tenor_extension_months,
        int(base_tenor * policy.max_tenor_extension_ratio),
    )
    new_tenor = base_tenor + tenor_ext
    new_rate = max(contract.interest_rate * (1 - policy.max_haircut_pct), policy.min_rate_floor)
    new_installment = calculate_installment(amortizable_principal(contract), new_rate, new_tenor)

    # Baseline dan proposal dibandingkan di basis yang SAMA (dua-duanya
    # risk-adjusted) — lihat koreksi #3 di docstring modul.
    npv_baseline = (
        npv_of_installments(contract.installment_amount, base_tenor, policy.discount_rate_annual)
        * contract.recovery_score
    )
    npv_restructured = npv_of_installments(new_installment, new_tenor, policy.discount_rate_annual)
    npv_restructured_risk_adjusted = npv_restructured * restructured_recovery_probability(
        contract.recovery_score, policy
    )
    total_remaining_current = contract.installment_amount * base_tenor
    total_new_schedule = new_installment * new_tenor

    return RestructureOffer(
        offer_type=OfferType.REFINANCE,
        contract_nos=[contract.contract_no],
        cust_id=contract.cust_id,
        total_ots_combined=contract.total_ots,
        recommended_new_tenor_months=new_tenor,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
        npv_restructured_risk_adjusted=round(npv_restructured_risk_adjusted, 2),
        total_remaining_current=round(total_remaining_current, 2),
        total_new_schedule=round(total_new_schedule, 2),
        current_installment_total=round(contract.installment_amount, 2),
    )


# ── CABANG 2: CONSOLIDATE ───────────────────────────────────────────────

def calculate_consolidation_offer(
    contracts: list[ContractInput], policy: RestructurePolicy
) -> Optional[RestructureOffer]:
    if len(contracts) < policy.consolidation_min_active_contracts:
        return None

    total_ots = sum(c.total_ots for c in contracts)
    total_principal = sum(amortizable_principal(c) for c in contracts)
    weighted_rate = sum(c.total_ots * c.interest_rate for c in contracts) / total_ots
    tenor_by_contract = {c.contract_no: effective_remaining_tenor(c) for c in contracts}
    longest_tenor = max(tenor_by_contract.values())

    tenor_ext = min(policy.max_tenor_extension_months, int(longest_tenor * policy.max_tenor_extension_ratio))
    new_tenor = longest_tenor + tenor_ext
    # Rate gabungan tidak boleh melebihi rate kontrak TERMURAH yang dilebur.
    # Rata-rata tertimbang bisa lebih tinggi dari salah satu kontrak, sehingga
    # menggabungkan justru menaikkan bunga pinjaman termurah nasabah (kasus
    # nyata: 12,24% + 37,69% → hasil 19,24%, pinjaman murahnya naik 57%).
    # Nasabah tahu rate-nya sendiri; "satu rate lebih ringan" yang ternyata
    # lebih mahal dari salah satu pinjamannya adalah cara tercepat kehilangan
    # kepercayaan. min_rate_floor tetap menang kalau lebih tinggi dari itu.
    cheapest_existing_rate = min(c.interest_rate for c in contracts)
    new_rate = max(
        min(weighted_rate * (1 - policy.max_haircut_pct), cheapest_existing_rate),
        policy.min_rate_floor,
    )
    new_installment = calculate_installment(total_principal, new_rate, new_tenor)

    npv_baseline = sum(
        npv_of_installments(c.installment_amount, tenor_by_contract[c.contract_no], policy.discount_rate_annual)
        * c.recovery_score
        for c in contracts
    )
    npv_restructured = npv_of_installments(new_installment, new_tenor, policy.discount_rate_annual)
    mean_recovery_score = sum(c.recovery_score for c in contracts) / len(contracts)
    npv_restructured_risk_adjusted = npv_restructured * restructured_recovery_probability(
        mean_recovery_score, policy
    )
    total_remaining_current = sum(
        c.installment_amount * tenor_by_contract[c.contract_no] for c in contracts
    )
    total_new_schedule = new_installment * new_tenor

    return RestructureOffer(
        offer_type=OfferType.CONSOLIDATE,
        contract_nos=[c.contract_no for c in contracts],
        cust_id=contracts[0].cust_id,
        total_ots_combined=round(total_ots, 2),
        recommended_new_tenor_months=new_tenor,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
        npv_restructured_risk_adjusted=round(npv_restructured_risk_adjusted, 2),
        total_remaining_current=round(total_remaining_current, 2),
        total_new_schedule=round(total_new_schedule, 2),
        current_installment_total=round(sum(c.installment_amount for c in contracts), 2),
    )


# ── CABANG 3: TAKEOVER ──────────────────────────────────────────────────

def calculate_takeover_offer(
    contract: ContractInput,
    appraisal: AssetAppraisal,
    policy: RestructurePolicy,
    today: Optional[date] = None,
) -> Optional[RestructureOffer]:
    today = today or date.today()
    appraisal_age_months = (today.year - appraisal.appraisal_date.year) * 12 + (
        today.month - appraisal.appraisal_date.month
    )
    if appraisal_age_months > policy.appraisal_max_age_months:
        return None  # appraisal basi — perlu re-appraisal dulu

    if appraisal.appraised_value / contract.total_ots < policy.asset_value_min_ratio:
        return None  # nilai aset tidak cukup signifikan menutup OTS

    recovery_from_asset = min(appraisal.appraised_value, contract.total_ots)
    sisa_ots = contract.total_ots - recovery_from_asset

    if sisa_ots <= 0:
        npv_restructured_early = recovery_from_asset
        return RestructureOffer(
            offer_type=OfferType.TAKEOVER,
            contract_nos=[contract.contract_no],
            cust_id=contract.cust_id,
            total_ots_combined=contract.total_ots,
            recommended_new_tenor_months=0,
            recommended_new_rate=0.0,
            recommended_new_installment=0.0,
            recovery_from_asset=round(recovery_from_asset, 2),
            npv_baseline=contract.total_ots * contract.recovery_score,
            npv_restructured=npv_restructured_early,
            # Cabang ini tidak ada sisa cicilan sama sekali (aset menutup penuh
            # OTS) — pakai total_ots sebagai "sisa kewajiban saat ini" dan
            # recovery_from_asset sendiri sebagai "jadwal baru" (lunas sekali bayar).
            npv_restructured_risk_adjusted=round(
                npv_restructured_early
                * restructured_recovery_probability(contract.recovery_score, policy),
                2,
            ),
            total_remaining_current=round(contract.total_ots, 2),
            total_new_schedule=round(recovery_from_asset, 2),
            current_installment_total=round(contract.installment_amount, 2),
        )

    base_tenor = effective_remaining_tenor(contract)
    # Aset menutup sebagian kewajiban bruto, jadi pokok yang tersisa untuk
    # diamortisasi ikut menyusut proporsional — bukan sisa bruto langsung,
    # yang akan menumpuk bunga di atas bunga (koreksi #1).
    principal = amortizable_principal(contract)
    remaining_principal = max(0.0, principal * (sisa_ots / contract.total_ots))
    new_rate = max(contract.interest_rate * (1 - policy.max_haircut_pct), policy.min_rate_floor)
    new_installment = calculate_installment(remaining_principal, new_rate, base_tenor)

    npv_baseline = contract.total_ots * contract.recovery_score
    npv_restructured = recovery_from_asset + npv_of_installments(
        new_installment, base_tenor, policy.discount_rate_annual
    )
    npv_restructured_risk_adjusted = npv_restructured * restructured_recovery_probability(
        contract.recovery_score, policy
    )
    total_remaining_current = contract.installment_amount * base_tenor
    total_new_schedule = recovery_from_asset + new_installment * base_tenor

    return RestructureOffer(
        offer_type=OfferType.TAKEOVER,
        contract_nos=[contract.contract_no],
        cust_id=contract.cust_id,
        total_ots_combined=contract.total_ots,
        recommended_new_tenor_months=contract.remaining_tenor_months,
        recommended_new_rate=round(new_rate, 4),
        recommended_new_installment=round(new_installment, 2),
        recovery_from_asset=round(recovery_from_asset, 2),
        npv_baseline=round(npv_baseline, 2),
        npv_restructured=round(npv_restructured, 2),
        npv_restructured_risk_adjusted=round(npv_restructured_risk_adjusted, 2),
        total_remaining_current=round(total_remaining_current, 2),
        total_new_schedule=round(total_new_schedule, 2),
        current_installment_total=round(contract.installment_amount, 2),
    )


# ── GUARDRAIL — LAPISAN TERAKHIR, PERMANEN ──────────────────────────────

def apply_guardrail(offer: RestructureOffer, policy: RestructurePolicy) -> RestructureOffer:
    """DUA sisi yang harus lolos: sisi lender (NPV membaik) dan sisi nasabah
    (tawaran benar-benar keringanan). Sebelum audit 2026-07-30 hanya sisi
    lender yang diuji, dan ujinya pun tidak sebanding — akibatnya 100% tawaran
    lolos sambil 80%-nya menaikkan cicilan nasabah (lihat docstring modul).

    `policy` sekarang WAJIB: batas manfaat nasabah adalah kebijakan, bukan
    konstanta tersembunyi di dalam fungsi ini."""
    reasons: list[str] = []

    # ── Sisi lender — kedua sisi risk-adjusted, apple-to-apple ─────────────
    # npv_baseline sudah dikali recovery_score di semua calculate_*_offer();
    # membandingkannya dengan npv_restructured MENTAH (perilaku lama) berarti
    # satu sisi didiskon ~70% dan sisi lain tidak, sehingga selalu lolos.
    if offer.npv_restructured_risk_adjusted <= offer.npv_baseline:
        reasons.append("NPV risk-adjusted tidak lebih baik dari baseline")

    # ── Sisi nasabah ──────────────────────────────────────────────────────
    # Dilewati hanya untuk TAKEOVER pelunasan penuh (tidak ada cicilan baru
    # sama sekali — aset menutup seluruh kewajiban, jadi tidak ada "cicilan
    # lebih ringan" yang bisa dibandingkan).
    is_full_payoff = offer.recommended_new_tenor_months <= 0 and offer.recommended_new_installment <= 0
    if not is_full_payoff:
        if offer.current_installment_total <= 0:
            # Tanpa pembanding, klaim "lebih ringan" tidak bisa dibuktikan —
            # tolak, jangan diam-diam diloloskan.
            reasons.append("cicilan saat ini tidak diketahui — manfaat nasabah tidak bisa diverifikasi")
        else:
            max_new_installment = offer.current_installment_total * (1 - policy.min_installment_reduction_pct)
            if offer.recommended_new_installment > max_new_installment:
                reasons.append(
                    f"cicilan baru {offer.recommended_new_installment:,.0f} tidak turun minimal "
                    f"{policy.min_installment_reduction_pct:.0%} dari cicilan sekarang "
                    f"{offer.current_installment_total:,.0f}"
                )

        if offer.total_remaining_current > 0:
            max_total = offer.total_remaining_current * policy.max_total_repayment_ratio
            if offer.total_new_schedule > max_total:
                reasons.append(
                    f"total bayar naik jadi {offer.total_new_schedule / offer.total_remaining_current:.2f}x "
                    f"(batas {policy.max_total_repayment_ratio:.2f}x)"
                )

    offer.is_guardrail_passed = len(reasons) == 0
    offer.rejection_reasons = reasons
    return offer


# ── ORCHESTRATOR ─────────────────────────────────────────────────────────

@dataclass
class RestructuringAssessment:
    """Hasil lengkap untuk satu customer/kontrak — ini yang diserialisasi
    jadi response API buat backend, baik dari hasil batch maupun on-demand."""
    cust_id: str
    contract_no: str
    eligibility_tier: EligibilityTier
    eligibility_reasons: list[str]
    offers: list[RestructureOffer] = field(default_factory=list)


def assess_restructuring_options(
    contract: ContractInput,
    customer: CustomerContext,
    policy: RestructurePolicy,
    sibling_contracts: Optional[list[ContractInput]] = None,
    appraisal: Optional[AssetAppraisal] = None,
    today: Optional[date] = None,
) -> RestructuringAssessment:
    eligibility = classify_eligibility(contract, customer, policy)

    if eligibility.tier == EligibilityTier.BLOCKED:
        # Satu-satunya kasus tidak ada angka sama sekali — data tidak valid.
        return RestructuringAssessment(
            cust_id=contract.cust_id, contract_no=contract.contract_no,
            eligibility_tier=eligibility.tier, eligibility_reasons=eligibility.reasons, offers=[],
        )

    # AUTO maupun MANUAL_REVIEW tetap dihitung angkanya — bedanya cuma
    # apakah backend boleh mendorongnya otomatis atau harus lewat approval dulu.
    candidates: list[RestructureOffer] = [calculate_refinance_offer(contract, policy)]

    if sibling_contracts:
        consolidation = calculate_consolidation_offer([contract] + sibling_contracts, policy)
        if consolidation:
            candidates.append(consolidation)

    if appraisal:
        takeover = calculate_takeover_offer(contract, appraisal, policy, today)
        if takeover:
            candidates.append(takeover)

    candidates = [apply_guardrail(o, policy) for o in candidates]
    passed = [o for o in candidates if o.is_guardrail_passed]

    # Ranking Fase 1: NPV gain terbesar, di basis risk-adjusted yang sama
    # dipakai guardrail. Memakai npv_restructured MENTAH (perilaku lama)
    # berarti mengurutkan berdasarkan "tawaran mana yang paling banyak menyerap
    # uang nasabah" dan menaruhnya di offers[0] sebagai rekomendasi utama.
    # Fase 2 (setelah ada model acceptance): ganti key ini dengan
    # expected_value = acceptance_probability(o) * o.npv_restructured_risk_adjusted
    passed.sort(key=lambda o: (o.npv_restructured_risk_adjusted - o.npv_baseline), reverse=True)

    return RestructuringAssessment(
        cust_id=contract.cust_id, contract_no=contract.contract_no,
        eligibility_tier=eligibility.tier, eligibility_reasons=eligibility.reasons, offers=passed,
    )


if __name__ == "__main__":
    # Contoh pakai — sekaligus jadi smoke test manual
    policy = RestructurePolicy()

    # Kasus 1: memenuhi semua kriteria standar → tier AUTO
    contract_auto = ContractInput(
        contract_no="C001", cust_id="CUST01", product_type="Kredit Motor",
        total_ots=15_000_000, interest_rate=0.24, remaining_tenor_months=18,
        installment_amount=1_100_000, dpd_current=45, risk_segment="Cannot Pay",
        recovery_score=0.35, self_cure_probability=0.20,
    )
    customer_auto = CustomerContext(cust_id="CUST01", b_list_status="N", restructure_count=0, active_contract_count=1)
    print("=== Kasus AUTO ===")
    print(assess_restructuring_options(contract_auto, customer_auto, policy))

    # Kasus 2: DPD masih terlalu dini (10 hari) → tier MANUAL_REVIEW,
    # tapi angka tetap dihitung — ini yang tadinya hilang total di versi lama
    contract_review = ContractInput(
        contract_no="C002", cust_id="CUST02", product_type="Kredit Motor",
        total_ots=15_000_000, interest_rate=0.24, remaining_tenor_months=18,
        installment_amount=1_100_000, dpd_current=10, risk_segment="Cannot Pay",
        recovery_score=0.35, self_cure_probability=0.20,
    )
    customer_review = CustomerContext(cust_id="CUST02", b_list_status="N", restructure_count=0, active_contract_count=1)
    print("\n=== Kasus MANUAL_REVIEW (DPD masih dini) ===")
    print(assess_restructuring_options(contract_review, customer_review, policy))

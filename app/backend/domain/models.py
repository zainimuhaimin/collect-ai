"""
Domain models — dataclass murni, TIDAK bergantung ke FastAPI/Pydantic/DB apapun.
Ini yang membuat domain/ dan ml/ bisa dites tanpa perlu jalankan server sama sekali.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class Customer:
    cust_id: str
    name: str
    b_list_status: str            # 'Y' / 'N'
    restructure_count: int
    active_contract_count: int
    behavioral_grade: str


@dataclass
class Contract:
    contract_no: str
    cust_id: str
    product_type: str
    total_ots: float                # BRUTO: prnc_ots + intr_ots (bunga blm jatuh tempo termasuk)
    interest_rate: float            # annual, decimal, mis. 0.24 = 24% p.a.
    remaining_tenor_months: int
    installment_amount: float
    dpd_current: int
    risk_segment: str               # 'Cannot Pay' | 'Self Cure' | "Won't Pay"
    recovery_score: float
    self_cure_probability: float
    closed_via_restructure: bool = False
    # Pokok terutang saja (prnc_ots), dipisah dari total_ots karena engine
    # restrukturisasi hanya boleh mengamortisasi ulang POKOK — memakai yang
    # bruto menumpuk bunga di atas bunga (lihat koreksi #1 di
    # shared/restructuring_offer_calculator.py).
    principal_ots: float = 0.0


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    name: str
    role: str               # label tampilan bebas, mis. 'Regional Manager' — bukan enum/RBAC
    is_active: bool = True


@dataclass
class RestructuringOfferRecord:
    """Satu baris restructuring_recommendation_output — dipakai untuk
    validasi transisi status (bukan hasil kalkulasi ml/, itu tetap
    RestructureOffer dari shared/restructuring_offer_calculator.py)."""
    restructure_group_id: str
    cust_id: str
    offer_type: str
    offer_status: str            # GENERATED | OFFERED | ACCEPTED | REJECTED | EXPIRED
    generated_date: date
    expiry_date: Optional[date]
    response_date: Optional[date] = None


# ── TASK-C/D: Customer & Contract list + detail (frontend-layout-upgrade) ──


@dataclass
class PageInfo:
    """Pola paginasi generik dipakai bersama list Customer & list Contract."""
    showing_from: int
    showing_to: int
    total_count: int
    total_pages: int


@dataclass
class CustomerListRow:
    cust_id: str
    name: str                        # dari customer_master.cust_name, fallback cust_id kalau NULL
    active_contract_count: int       # dari customer_behavioral_standing.active_contract_count
    behavioral_grade: str            # dari customer_behavioral_standing.behavioral_grade
    b_list_status: str               # 'Y' / 'N' — dari customer_behavioral_standing.b_list_status
    priority: str                    # 'Critical' | 'High' | 'Medium' — MAX() lintas kontrak AKTIF
                                      # customer ini (bukan dari 1 kontrak arbitrer lagi), lihat
                                      # CustomerRepository._CUSTOMER_LIST_BASE_CTE


@dataclass
class CustomerProfile:
    """360 view 1 customer — join customer_master + customer_behavioral_standing
    + kontrak utama (primary contract) + skor ai_intelligence_output kontrak itu."""
    cust_id: str
    name: str
    outstanding_balance: float
    risk_segment: Optional[str]
    recovery_score: float
    self_cure_probability: float
    roll_forward_risk: float
    ptp_success_probability: float
    nba_recommendation: Optional[str]
    behavioral_grade: str
    b_list_status: str
    restructure_count: int
    active_contract_count: int


@dataclass
class ContractListRow:
    contract_no: str
    cust_id: str
    product_type: str
    dpd_current: int
    outstanding: float
    risk_segment: Optional[str]
    priority: str = "Medium"   # dipakai internal untuk filter high_amount, TIDAK diekspos di response list
    # default "" dipakai oleh list_for_customer() (query itu TIDAK join customer_master,
    # cust_name tidak diekspos di response endpoint itu — sudah dalam konteks 1 customer,
    # redundan). list_contracts_page() SELALU mengisi ini dari customer_master.cust_name.
    cust_name: str = ""


@dataclass
class AiScoringSnapshot:
    recovery_score: float
    risk_segment: Optional[str]
    self_cure_probability: float
    roll_forward_risk: float
    ptp_success_probability: float
    nba_recommendation: Optional[str]
    confidence_level: float
    scoring_date: Optional[date]
    # Label singkat cabang apply_nba() (business_rules.py) yang menghasilkan
    # nba_recommendation di atas, mis. "override:collection_sensitivity" —
    # dipakai fitur AI Reasoning supaya LLM tahu ALASAN rekomendasi tanpa
    # merekonstruksi ulang logika last-write-wins-nya (lihat schema_v5.sql).
    nba_trigger: Optional[str] = None


@dataclass
class PaymentHistoryEntry:
    due_date: Optional[date]
    actual_pay_date: Optional[date]
    payment_amount: float
    pay_status: Optional[str]
    delay_days: Optional[int]
    recovery_source: Optional[str]


@dataclass
class RestructuringStatusSnapshot:
    restructure_group_id: str
    offer_status: str
    eligibility_tier: str


@dataclass
class ContractDetail:
    contract_no: str
    cust_id: str
    cust_name: str
    product_type: str
    cycle: Optional[str]
    prev_cycle: Optional[str]
    closed_via_restructure: bool
    new_contract_no: Optional[str]
    loan_amount: float
    installment_amount: float
    interest_rate: float
    maturity_date: Optional[date]
    remaining_tenor_months: int
    dpd_current: int
    overdue_installment_count: int
    late_fee_amount: float
    ambc: float
    principal_ots: float
    interest_ots: float
    ai_scoring: Optional[AiScoringSnapshot]
    payment_history: List[PaymentHistoryEntry] = field(default_factory=list)
    restructuring_status: Optional[RestructuringStatusSnapshot] = None


@dataclass
class ActivityLogEntry:
    """1 baris lkp_interaction — mapping ke icon/title/tone dilakukan di
    service layer (pure Python, gampang dites tanpa DB)."""
    lkp_id: str
    action_date: Optional[date]
    treatment_type: Optional[str]
    result_code: Optional[str]
    ptp_status: Optional[str]


# ── TASK-B: Dashboard summary ──


@dataclass
class DpdBucketRow:
    bucket: str            # 'C0' | 'C1' | 'C2' | 'C3+'
    settled: int
    active_ptp: int
    broken: int
    total: int


@dataclass
class ChannelEfficiencyRow:
    treatment_type: str
    contact_success_rate: float     # 0..1


@dataclass
class DashboardSummary:
    # kpis/contactability_funnel/restructuring_pipeline_snapshot/risk_segment_distribution
    # sengaja dict label->angka (bukan dataclass tersendiri) — semuanya cuma
    # agregat key-value sederhana untuk 1 endpoint laporan, tidak dipakai ulang
    # di tempat lain yang butuh tipe kuat.
    kpis: Dict[str, float]
    dpd_buckets: List[DpdBucketRow]
    contactability_funnel: Dict[str, int]
    channel_efficiency: List[ChannelEfficiencyRow]
    restructuring_pipeline_snapshot: Dict[str, int]
    risk_segment_distribution: Dict[str, int]
    sync_note: str


# ── TASK-E: Restructuring approval queue ──


@dataclass
class RestructuringGroupSummary:
    restructure_group_id: str
    cust_id: str
    contract_nos: List[str]
    offer_type: str
    eligibility_tier: str
    eligibility_reasons: Optional[str]
    npv_baseline: Optional[float]
    npv_restructured: Optional[float]
    generated_date: date
    offer_status: str
    # Tambahan display-only (Round 4 #6) — TIDAK dipersist ke
    # restructuring_recommendation_output (lihat schema_combined.sql, tabel
    # itu belum punya kolomnya), jadi untuk grup dari batch ML/
    # restructuring_runner.py ini dihitung ULANG dari data yang sudah ada
    # (recovery_score per kontrak di ai_intelligence_output, jadwal saat ini
    # di contract_snapshot — lihat RestructuringOfferRepository._row_to_summary
    # + _GROUP_CONTRACT_STATS_CTE), bukan re-run kalkulator. Bisa None hanya
    # kalau kontrak grup ini belum pernah discoring sama sekali (fresh-demo
    # state). Endpoint on-demand (GET .../restructuring-options, lihat
    # RestructureOfferSchema) mengisinya dari kalkulator langsung.
    npv_restructured_risk_adjusted: Optional[float] = None
    total_remaining_current: Optional[float] = None
    total_new_schedule: Optional[float] = None


# ── TASK-F: AI Intelligence — governance (Bobot CBS + audit + model health) ──


@dataclass
class CbsWeight:
    label: str               # key stabil, mis. 'WEIGHT_PAYMENT_RATE'
    weight: float             # 0..100 (persen, BUKAN 0..1)
    description: str


@dataclass
class ModelHealthSnapshot:
    run_date: Optional[date]
    auc: Optional[float]
    calibration_gap: Optional[float]
    n_critical_drift: int
    n_warning_drift: int
    retrain_triggered: bool
    champion_version: Optional[str]


@dataclass
class GovernanceAuditEntry:
    timestamp: datetime
    action: str
    user: Optional[str]
    status: str = "Success"


# ── AI Intelligence Sync: training-if-missing + scoring (background job) ──


@dataclass
class SyncStep:
    """1 langkah job Sync AI Intelligence — 4 model_type (recovery/self_cure/
    roll_forward/ptp_success) + 1 langkah `daily_scoring` gabungan di akhir
    (lihat AiIntelligenceSyncService)."""
    model_type: str
    action: str    # 'train_then_score' | 'score_only' (4 model_type) | 'score' (daily_scoring)
    status: str = "pending"   # 'pending' | 'running' | 'done' | 'failed'


@dataclass
class SyncJobState:
    """State job in-memory — process-local, TIDAK disimpan ke tabel apapun
    (ephemeral, hilang kalau proses backend restart, itu sudah cukup untuk
    kebutuhan tombol Sync di frontend)."""
    status: str = "idle"    # 'idle' | 'running' | 'completed' | 'failed'
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    steps: List[SyncStep] = field(default_factory=list)
    error: Optional[str] = None
    # True kalau job ini melatih >=1 model_type dari nol (registry.json belum
    # punya champion sama sekali) — dipakai _run_job() untuk memutuskan apakah
    # perlu menjalankan pipelines/weekly_mlops.py tambahan setelah daily_scoring
    # (lihat AiIntelligenceSyncService, Round 4 #8).
    did_train_from_scratch: bool = False


# ── AI Reasoning (ai-reasoning-api-upgrade-tasks.md) — grain DEBITUR ────────


@dataclass
class CustomerBehavioralRaw:
    """customer_behavioral_standing APA ADANYA — TIDAK meng-coalesce NULL ke
    0/default seperti CustomerProfile/Customer di atas. Payload AI Reasoning
    butuh membedakan "tidak ada data" dari "nol" (temuan #9/#16
    ai-reasoning-api-upgrade-tasks.md): debitur baru tanpa baris CBS harus
    terlihat sebagai TIDAK ADA data, bukan diam-diam ter-grade 'D'."""
    cust_id: str
    has_cbs_row: bool          # False = belum pernah dibangun untuk cust_id ini
    behavioral_grade: Optional[str]
    ptp_reliability_index: Optional[float]
    collection_sensitivity: Optional[str]
    b_list_status: Optional[str]
    active_contract_count: int
    total_active_ots: float
    cbs_as_of: Optional[datetime]     # customer_behavioral_standing.update_timestamp


@dataclass
class AiReasoningHealthSnapshot:
    """Agregat ai_reasoning_output 7 hari terakhir — dipakai mengganti
    AiReasoningHealthPlaceholder di kartu Model Health (halaman AI
    Intelligence) begitu tabelnya ada isinya."""
    last_generated_at: Optional[datetime]
    total_7d: int
    success_rate_7d: Optional[float]   # None kalau total_7d == 0


@dataclass
class AiReasoningRecord:
    """1 baris ai_reasoning_output — hasil (atau status kegagalan/kekurangan
    data) analisa hyper-personalization 1 debitur. `status` menentukan field
    mana yang terisi: OK/FALLBACK mengisi summary dst, INSUFFICIENT_DATA hanya
    mengisi insufficient_reason, FAILED hanya mengisi error_code."""
    cust_id: str
    source_signature: str
    prompt_version: str
    status: str    # OK | FALLBACK | FAILED | RUNNING | INSUFFICIENT_DATA
    insufficient_reason: Optional[str] = None
    model_used: Optional[str] = None
    generated_at: Optional[datetime] = None
    summary: Optional[str] = None
    customer_treatment_strategy: Optional[str] = None
    key_factors: List[str] = field(default_factory=list)
    primary_nba_action: Optional[str] = None
    primary_nba_rationale: Optional[str] = None
    nba_agreement: Optional[str] = None    # AGREE | DIFFER
    per_contract_focus: List[Dict] = field(default_factory=list)
    consistency_note: Optional[str] = None
    analyzed_contract_nos: List[str] = field(default_factory=list)
    latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_code: Optional[str] = None
    payload_bytes: Optional[int] = None
    created_at: Optional[datetime] = None

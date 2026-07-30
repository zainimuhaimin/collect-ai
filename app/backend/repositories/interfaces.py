"""
Interface repository — abstraksi yang di-depend oleh service layer (DIP).
Sengaja dipecah jadi 3 interface kecil (ISP), bukan 1 interface besar:
service yang cuma butuh data customer tidak perlu tahu soal kontrak, dan
sebaliknya. Implementasi konkret (CustomerRepository, ContractRepository,
RestructuringOfferRepository di file sebelah — semua Postgres) tinggal
mengimplementasikan interface ini — service layer TIDAK PERNAH diubah
kalau implementasinya diganti (mis. provider DB lain) (LSP + OCP).
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional, Tuple

from domain.models import (
    ActivityLogEntry,
    CbsWeight,
    Contract,
    ContractDetail,
    ContractListRow,
    Customer,
    CustomerListRow,
    CustomerProfile,
    DashboardSummary,
    GovernanceAuditEntry,
    ModelHealthSnapshot,
    RestructuringGroupSummary,
    RestructuringOfferRecord,
    User,
)


class ICustomerRepository(ABC):
    @abstractmethod
    def list_customers(self) -> List[Customer]:
        ...

    @abstractmethod
    def get_customer(self, cust_id: str) -> Optional[Customer]:
        ...

    @abstractmethod
    def list_customers_page(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[CustomerListRow], int]:
        """List Customer dengan filter chip/search/paginasi (TASK-C). Return
        (baris utk halaman ini, total_count SETELAH filter) — total_count
        dipakai untuk hitung page_info di service."""
        ...

    @abstractmethod
    def get_customer_profile(self, cust_id: str) -> Optional[CustomerProfile]:
        """360 view (TASK-C reshape total) — None kalau cust_id tidak ada
        sama sekali di customer_master."""
        ...

    @abstractmethod
    def exists(self, cust_id: str) -> bool:
        ...


class IContractRepository(ABC):
    @abstractmethod
    def get_contract(self, contract_no: str) -> Optional[Contract]:
        ...

    @abstractmethod
    def get_primary_contract_for_customer(self, cust_id: str) -> Optional[Contract]:
        ...

    @abstractmethod
    def get_sibling_contracts(self, cust_id: str, exclude_contract_no: str) -> List[Contract]:
        ...

    @abstractmethod
    def list_for_customer(self, cust_id: str) -> List[ContractListRow]:
        """Daftar ringan kontrak milik 1 customer, ORDER BY dpd_current DESC
        (TASK-C, dipakai expandable contract list di Customer Detail)."""
        ...

    @abstractmethod
    def list_contracts_page(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[ContractListRow], int]:
        """List Contract dengan filter/search/paginasi (TASK-D) — sama seperti
        Customer tapi murni per-baris (bukan agregat 'punya kontrak yang...')."""
        ...

    @abstractmethod
    def get_contract_detail(self, contract_no: str) -> Optional[ContractDetail]:
        """Detail 7-bagian (TASK-D): ringkasan + outstanding + AI scoring +
        riwayat pembayaran (12 terakhir) + status restrukturisasi, digabung
        1 payload (lihat catatan penutup frontend-layout-upgrade-tasks.md)."""
        ...

    @abstractmethod
    def get_activity_log(self, contract_no: str) -> List[ActivityLogEntry]:
        """1 endpoint dipakai 2 tempat: Contract Detail timeline & expand
        per-kontrak di Customer Detail (TASK-C/D) — supaya datanya konsisten."""
        ...


class IDashboardRepository(ABC):
    """Domain baru (TASK-B) — agregat lintas tabel murni untuk 1 endpoint
    laporan, dipisah dari repository lain (ISP) karena tidak ada satupun
    service lain yang butuh method-method ini."""

    @abstractmethod
    def get_summary(self) -> DashboardSummary:
        ...


class IRestructuringOfferRepository(ABC):
    """Akses ke restructuring_recommendation_output — dipisah dari
    IContractRepository (ISP) karena siklus hidupnya beda: offer dibuat oleh
    batch ML (restructuring_runner.py), backend cuma baca + update status
    saat customer merespons, tidak pernah membuat/menghitung offer sendiri."""

    @abstractmethod
    def get_offer(self, restructure_group_id: str) -> Optional[RestructuringOfferRecord]:
        ...

    @abstractmethod
    def find_latest_for_customer(self, cust_id: str) -> Optional[RestructuringOfferRecord]:
        """Baris restructuring_recommendation_output TERBARU (by generated_date)
        untuk 1 customer, kalau ada — dipakai GET .../restructuring-options
        (on-demand) untuk tahu apakah sudah ada group persisted yang bisa
        direspons customer, atau ini murni preview tanpa group_id."""
        ...

    @abstractmethod
    def record_customer_response(
        self, restructure_group_id: str, response: str, response_date: date
    ) -> bool:
        """Update offer_status -> ACCEPTED/REJECTED + response_date.
        Return False kalau restructure_group_id tidak ditemukan."""
        ...

    @abstractmethod
    def list_offers(
        self,
        statuses: List[str],
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RestructuringGroupSummary], int]:
        """Queue approval (TASK-E) — restructuring_recommendation_output JOIN
        restructuring_group_map (agregat contract_no jadi array). `search`
        (opsional) — substring match ke `restructure_group_id` ATAU `cust_id`.
        Return (items halaman ini, total_groups keseluruhan filter/search ini)."""
        ...

    @abstractmethod
    def get_offer_summary(self, restructure_group_id: str) -> Optional[RestructuringGroupSummary]:
        """Detail 1 grup (bentuk sama dengan item list_offers()) — query
        single-row tersendiri (bukan filter list_offers() di Python), None
        kalau restructure_group_id tidak ditemukan."""
        ...

    @abstractmethod
    def update_offer_status(
        self, restructure_group_id: str, new_status: str, action: str, performed_by: Optional[str]
    ) -> bool:
        """Transisi GENERATED->OFFERED/REJECTED (TASK-E) + insert 1 baris audit
        ke restructuring_approval_log, dalam 1 transaksi. Guard WHERE
        offer_status='GENERATED' di UPDATE-nya sendiri (bukan cek-lalu-update
        terpisah) supaya aman dari race condition sekaligus jadi satu-satunya
        sumber kebenaran soal 'apakah transisi ini berhasil'. Return False
        kalau row tidak ada ATAU status saat ini bukan GENERATED lagi — service
        yang membedakan 404 vs 409 (service sudah panggil get_offer() duluan)."""
        ...


class IGovernanceConfigRepository(ABC):
    """Akses model_governance_config + model_governance_audit_log (TASK-F,
    fase 1: Bobot CBS) — domain baru, dipisah dari repository lain (ISP)
    karena tabelnya genuinely baru, tidak overlap dengan scoring/restructuring."""

    @abstractmethod
    def get_cbs_weights(self) -> List[CbsWeight]:
        """Baca dari model_governance_config; kalau baris belum ada sama
        sekali, seed dari app/machine-learning/config/settings.py
        (WEIGHT_PAYMENT_RATE dkk) sebagai default pertama kali dipanggil."""
        ...

    @abstractmethod
    def save_cbs_weights(self, weights: List[CbsWeight], performed_by: Optional[str]) -> List[CbsWeight]:
        """Simpan array bobot baru + insert audit row 'WEIGHTING_UPDATE'."""
        ...

    @abstractmethod
    def get_model_health(self) -> Optional[ModelHealthSnapshot]:
        """Baris model_monitoring_log paling baru (run_date DESC)."""
        ...

    @abstractmethod
    def list_operational_log(self) -> List[GovernanceAuditEntry]:
        """model_governance_audit_log, terbaru dulu."""
        ...


class IAiIntelligenceSyncRepository(ABC):
    """Akses DB untuk fitur Sync AI Intelligence (training-if-missing +
    scoring, dipicu tombol di frontend AI Intelligence). Job-state yang sedang
    berjalan (langkah mana selesai, dst) MURNI in-memory di
    AiIntelligenceSyncService — TIDAK lewat repository ini. Yang lewat sini
    hanya 2 hal: `last_scored_at` (harus real-time, dihitung ulang tiap
    panggilan GET status, independen dari status job) dan jejak permanen tiap
    job yang selesai/gagal ke audit log (state in-memory hilang saat backend
    restart, sedangkan Operational Log harus tetap punya riwayatnya)."""

    @abstractmethod
    def get_last_scored_at(self) -> Optional[datetime]:
        """MAX(updated_at) ai_intelligence_output — None kalau tabel masih
        kosong sama sekali (belum pernah ada scoring run apapun)."""
        ...

    @abstractmethod
    def log_sync_event(self, action: str, status: str, detail: dict) -> None:
        """Insert 1 baris model_governance_audit_log — dipakai supaya job Sync
        muncul di Operational Log. TIDAK boleh melempar exception ke caller:
        gagal mencatat audit tidak boleh menggagalkan job Sync yang sebenarnya
        sudah sukses."""
        ...


class IUserRepository(ABC):
    """Akses ke tabel users (login/identity) — bukan bagian dari data
    customer/kontrak, jadi sengaja dipisah interface-nya (ISP)."""

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        ...

    @abstractmethod
    def create(self, *, username: str, password_hash: str, name: str, role: str) -> User:
        """Dipakai oleh scripts/seed_dev_user.py (provisioning), bukan oleh
        endpoint login/me manapun — tidak ada endpoint register publik."""
        ...

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
from datetime import date
from typing import List, Optional

from domain.models import Contract, Customer, RestructuringOfferRecord, User


class ICustomerRepository(ABC):
    @abstractmethod
    def list_customers(self) -> List[Customer]:
        ...

    @abstractmethod
    def get_customer(self, cust_id: str) -> Optional[Customer]:
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


class IRestructuringOfferRepository(ABC):
    """Akses ke restructuring_recommendation_output — dipisah dari
    IContractRepository (ISP) karena siklus hidupnya beda: offer dibuat oleh
    batch ML (restructuring_runner.py), backend cuma baca + update status
    saat customer merespons, tidak pernah membuat/menghitung offer sendiri."""

    @abstractmethod
    def get_offer(self, restructure_group_id: str) -> Optional[RestructuringOfferRecord]:
        ...

    @abstractmethod
    def record_customer_response(
        self, restructure_group_id: str, response: str, response_date: date
    ) -> bool:
        """Update offer_status -> ACCEPTED/REJECTED + response_date.
        Return False kalau restructure_group_id tidak ditemukan."""
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

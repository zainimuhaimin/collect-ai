from typing import List, Optional, Tuple

from domain.models import ContractListRow, CustomerListRow, CustomerProfile, PageInfo
from repositories.interfaces import IContractRepository, ICustomerRepository
from services.pagination import build_page_info

VALID_CUSTOMER_FILTERS = ("all", "dpd_30_plus", "high_priority", "broken_ptp", "high_ambc")


class CustomerService:
    """Business logic layer. Router TIDAK BOLEH memanggil repository
    langsung — semua akses data lewat service ini (SRP: router cuma
    urusan HTTP, service urusan logika, repository urusan data).

    NOTE: list_customers()/get_customer() polos (dataclass Customer lama)
    SENGAJA tidak diekspos ulang di sini — endpoint TASK-C sudah reshape
    total ke list_customers_page()/get_customer_profile(). ICustomerRepository
    tetap punya method itu karena masih dipakai RestructuringService."""

    def __init__(self, customer_repository: ICustomerRepository, contract_repository: IContractRepository):
        self._repo = customer_repository
        self._contracts = contract_repository

    def list_customers_page(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[CustomerListRow], PageInfo]:
        filter_key = filter_key if filter_key in VALID_CUSTOMER_FILTERS else "all"
        page = max(1, page)
        page_size = max(1, page_size)
        rows, total = self._repo.list_customers_page(filter_key, search, page, page_size)
        return rows, build_page_info(total, page, page_size, len(rows))

    def get_customer_profile(self, cust_id: str) -> Optional[CustomerProfile]:
        return self._repo.get_customer_profile(cust_id)

    def list_contracts_for_customer(self, cust_id: str) -> Optional[List[ContractListRow]]:
        """None kalau cust_id tidak ada sama sekali di customer_master (-> 404
        di router); list kosong tetap valid kalau customer ada tapi kontraknya
        nol (bukan error)."""
        if not self._repo.exists(cust_id):
            return None
        return self._contracts.list_for_customer(cust_id)

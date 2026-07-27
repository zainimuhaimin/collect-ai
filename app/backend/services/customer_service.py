from typing import List, Optional

from domain.models import Customer
from repositories.interfaces import ICustomerRepository


class CustomerService:
    """Business logic layer. Router TIDAK BOLEH memanggil repository
    langsung — semua akses data lewat service ini (SRP: router cuma
    urusan HTTP, service urusan logika, repository urusan data)."""

    def __init__(self, customer_repository: ICustomerRepository):
        self._repo = customer_repository

    def list_customers(self) -> List[Customer]:
        return self._repo.list_customers()

    def get_customer_detail(self, cust_id: str) -> Optional[Customer]:
        return self._repo.get_customer(cust_id)

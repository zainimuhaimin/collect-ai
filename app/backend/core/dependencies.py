"""
Wiring dependency injection — SATU-SATUNYA tempat yang tahu implementasi
konkret repository mana yang dipakai (semua Postgres, DB yang sama dipakai
app/machine-learning/). Kalau provider datanya berubah nanti, cukup ganti
kelas yang di-instansiasi di sini — router dan service tidak pernah
disentuh (DIP, lihat backend-architecture-tasks.md Catatan #2).
"""

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from core.config import settings
from domain.models import User
from repositories.interfaces import (
    IContractRepository,
    ICustomerRepository,
    IRestructuringOfferRepository,
    IUserRepository,
)
from repositories.contract_repository import ContractRepository
from repositories.customer_repository import CustomerRepository
from repositories.restructuring_offer_repository import RestructuringOfferRepository
from repositories.user_repository import UserRepository
from services.auth_service import AuthService
from services.customer_service import CustomerService
from services.restructuring_service import RestructuringService


@lru_cache
def get_engine() -> Engine:
    return create_engine(settings.database_url)


@lru_cache
def get_customer_repository() -> ICustomerRepository:
    return CustomerRepository(get_engine())


@lru_cache
def get_contract_repository() -> IContractRepository:
    return ContractRepository(get_engine())


@lru_cache
def get_restructuring_offer_repository() -> IRestructuringOfferRepository:
    return RestructuringOfferRepository(get_engine())


@lru_cache
def get_user_repository() -> IUserRepository:
    return UserRepository(get_engine())


# NOTE: repository di-inject lewat Depends() di sini (bukan dipanggil
# langsung sebagai fungsi Python biasa) supaya masuk ke dependency graph
# FastAPI yang sesungguhnya — ini yang membuat app.dependency_overrides di
# test bisa menembus sampai ke repository level, bukan cuma stuck di service.
def get_customer_service(
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
) -> CustomerService:
    return CustomerService(customer_repo)


def get_restructuring_service(
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
    contract_repo: IContractRepository = Depends(get_contract_repository),
    offer_repo: IRestructuringOfferRepository = Depends(get_restructuring_offer_repository),
) -> RestructuringService:
    return RestructuringService(customer_repo, contract_repo, offer_repo)


def get_auth_service(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(user_repo)


# auto_error=False WAJIB: default HTTPBearer() (auto_error=True) melempar 403
# kalau header Authorization tidak ada, padahal frontend cuma treat 401 sebagai
# sinyal "logout" (lihat client.ts di app/frontend). 403 di sini akan membuat
# alur logout-otomatis frontend diam-diam tidak jalan.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = auth_service.get_user_from_token(credentials.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user

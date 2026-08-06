"""
Wiring dependency injection — SATU-SATUNYA tempat yang tahu implementasi
konkret repository mana yang dipakai (semua Postgres, DB yang sama dipakai
app/machine-learning/). Kalau provider datanya berubah nanti, cukup ganti
kelas yang di-instansiasi di sini — router dan service tidak pernah
disentuh (DIP, lihat backend-architecture-tasks.md Catatan #2).
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from core.config import settings
from domain.models import User
from repositories.interfaces import (
    IAiIntelligenceSyncRepository,
    IAiReasoningRepository,
    IContractRepository,
    ICustomerRepository,
    IDashboardRepository,
    IGovernanceConfigRepository,
    IRestructuringOfferRepository,
    IUserRepository,
)
from repositories.ai_intelligence_sync_repository import AiIntelligenceSyncRepository
from repositories.ai_reasoning_repository import AiReasoningRepository
from repositories.contract_repository import ContractRepository
from repositories.customer_repository import CustomerRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.governance_repository import GovernanceConfigRepository
from repositories.restructuring_offer_repository import RestructuringOfferRepository
from repositories.user_repository import UserRepository
from services.ai_intelligence_sync_service import AiIntelligenceSyncService
from services.ai_reasoning_service import AiReasoningService, build_gemini_client
from services.auth_service import AuthService
from services.customer_service import CustomerService
from services.contract_service import ContractService
from services.dashboard_service import DashboardService
from services.governance_service import GovernanceService
from services.restructuring_service import RestructuringService
from services.restructuring_group_service import RestructuringGroupService


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


@lru_cache
def get_dashboard_repository() -> IDashboardRepository:
    return DashboardRepository(get_engine())


@lru_cache
def get_governance_repository() -> IGovernanceConfigRepository:
    return GovernanceConfigRepository(get_engine())


@lru_cache
def get_ai_intelligence_sync_repository() -> IAiIntelligenceSyncRepository:
    return AiIntelligenceSyncRepository(get_engine())


@lru_cache
def get_ai_reasoning_repository() -> IAiReasoningRepository:
    return AiReasoningRepository(get_engine())


# NOTE: repository di-inject lewat Depends() di sini (bukan dipanggil
# langsung sebagai fungsi Python biasa) supaya masuk ke dependency graph
# FastAPI yang sesungguhnya — ini yang membuat app.dependency_overrides di
# test bisa menembus sampai ke repository level, bukan cuma stuck di service.
def get_customer_service(
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
    contract_repo: IContractRepository = Depends(get_contract_repository),
) -> CustomerService:
    return CustomerService(customer_repo, contract_repo)


def get_contract_service(
    contract_repo: IContractRepository = Depends(get_contract_repository),
) -> ContractService:
    return ContractService(contract_repo)


def get_restructuring_service(
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
    contract_repo: IContractRepository = Depends(get_contract_repository),
    offer_repo: IRestructuringOfferRepository = Depends(get_restructuring_offer_repository),
) -> RestructuringService:
    return RestructuringService(customer_repo, contract_repo, offer_repo)


def get_restructuring_group_service(
    offer_repo: IRestructuringOfferRepository = Depends(get_restructuring_offer_repository),
) -> RestructuringGroupService:
    return RestructuringGroupService(offer_repo)


def get_dashboard_service(
    dashboard_repo: IDashboardRepository = Depends(get_dashboard_repository),
) -> DashboardService:
    return DashboardService(dashboard_repo)


def get_governance_service(
    governance_repo: IGovernanceConfigRepository = Depends(get_governance_repository),
) -> GovernanceService:
    return GovernanceService(governance_repo)


# NOTE: SENGAJA tidak di-@lru_cache seperti service lain — tidak masalah,
# state job Sync sendiri hidup di module-level singleton di
# services/ai_intelligence_sync_service.py (bukan di instance service ini),
# jadi tetap 1 job untuk seluruh proses biarpun instance service-nya dibuat
# ulang tiap request.
def get_ai_intelligence_sync_service(
    sync_repo: IAiIntelligenceSyncRepository = Depends(get_ai_intelligence_sync_repository),
) -> AiIntelligenceSyncService:
    return AiIntelligenceSyncService(sync_repo)


def get_auth_service(
    user_repo: IUserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(user_repo)


# NOTE: SENGAJA tidak di-@lru_cache — GeminiClient dibuat baru tiap request
# (murah, tidak ada I/O di constructor-nya) supaya perubahan
# GOOGLE_AI_STUDIO_API_KEYS/AI_REASONING_ENABLED di .env langsung berlaku
# tanpa perlu restart proses backend untuk membersihkan cache lru_cache.
def get_ai_reasoning_service(
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
    contract_repo: IContractRepository = Depends(get_contract_repository),
    ai_reasoning_repo: IAiReasoningRepository = Depends(get_ai_reasoning_repository),
) -> AiReasoningService:
    return AiReasoningService(customer_repo, contract_repo, ai_reasoning_repo, build_gemini_client())


# auto_error=False WAJIB: default HTTPBearer() (auto_error=True) melempar 403
# kalau header Authorization tidak ada, padahal frontend cuma treat 401 sebagai
# sinyal "logout" (lihat client.ts di app/frontend). 403 di sini akan membuat
# alur logout-otomatis frontend diam-diam tidak jalan.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = auth_service.get_user_from_token(credentials.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user

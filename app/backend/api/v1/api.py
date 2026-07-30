from fastapi import APIRouter

from api.v1.routers import (
    ai_intelligence,
    auth,
    contracts,
    customers,
    dashboard,
    restructuring,
    restructuring_groups,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(contracts.router)
api_router.include_router(restructuring.router)
api_router.include_router(restructuring_groups.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai_intelligence.router)

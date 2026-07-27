from fastapi import APIRouter

from api.v1.routers import auth, customers, health, restructuring

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(restructuring.router)

from fastapi import APIRouter, Depends, HTTPException, status

from core.dependencies import get_auth_service, get_current_user
from core.text_utils import compute_initials
from domain.models import User
from schemas.auth import LoginRequest, LoginResponse, UserOut
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(name=user.name, role=user.role, initials=compute_initials(user.name))


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Tukar username/password dengan bearer token. Tidak ada endpoint register "
    "publik — user diprovisioning lewat scripts/seed_dev_user.py atau operasi admin internal.",
    responses={401: {"description": "Username atau password salah"}},
)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    user = auth_service.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah")
    token = auth_service.issue_token(user)
    return LoginResponse(token=token, user=_to_user_out(user))


@router.get(
    "/me",
    response_model=UserOut,
    summary="Profil user yang sedang login",
    description="Butuh header `Authorization: Bearer <token>`. Token dianggap opaque oleh "
    "frontend — expiry hanya diketahui lewat response 401 di sini.",
    responses={401: {"description": "Token tidak ada, tidak valid, atau sudah kedaluwarsa"}},
)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _to_user_out(current_user)

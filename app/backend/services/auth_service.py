"""Business logic login/identity. Sama seperti CustomerService/RestructuringService:
hanya menerima repository lewat interface (constructor injection), TIDAK pernah
import implementasi konkret ataupun FastAPI (grep -r "fastapi" services/ dan
grep -r "UserRepository" services/auth_service.py harus tidak menemukan apapun)."""
from typing import Optional

import jwt as pyjwt

from core.security import create_access_token, decode_access_token, verify_password
from domain.models import User
from repositories.interfaces import IUserRepository


class AuthService:
    def __init__(self, user_repository: IUserRepository):
        self._repo = user_repository

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self._repo.get_by_username(username)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))

    def get_user_from_token(self, token: str) -> Optional[User]:
        try:
            payload = decode_access_token(token)
        except pyjwt.PyJWTError:
            return None
        user = self._repo.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active:
            return None
        return user

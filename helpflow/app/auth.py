"""Local JWT authentication and role-based authorization."""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import SessionLocal, UserRow

password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)
_development_secret = secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def _secret() -> str:
    if settings.jwt_secret_key:
        return settings.jwt_secret_key
    if settings.app_env.lower() in {"production", "prod"}:
        raise RuntimeError("JWT_SECRET_KEY must be configured outside development")
    return _development_secret


def create_access_token(user: UserRow) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256"), expires_in


def _decode(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        return jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserRow:
    claims = _decode(credentials)
    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token subject") from exc
    with SessionLocal() as db:
        user = db.get(UserRow, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User is inactive or unavailable")
        # Return a detached snapshot; endpoints use the id/role and do not mutate this object.
        db.expunge(user)
        return user


def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserRow | None:
    if credentials is None:
        return None
    return get_current_user(credentials)


def require_roles(*roles: str):
    def dependency(user: Annotated[UserRow, Depends(get_current_user)]) -> UserRow:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role for this operation")
        return user
    return dependency

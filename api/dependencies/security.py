"""Password hashing + JWT auth for per-user accounts."""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from config.settings import settings
from models.database.models import UserDB

bearer_scheme = HTTPBearer(auto_error=False)

# Using the `bcrypt` package directly (rather than passlib's bcrypt wrapper,
# which has known incompatibilities with recent bcrypt releases) for hashing.
_BCRYPT_MAX_BYTES = 72  # bcrypt's hard input limit


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        truncated = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(truncated, hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Please log in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserDB:
    if credentials is None or not credentials.credentials:
        raise AUTH_ERROR
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise AUTH_ERROR
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise AUTH_ERROR
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user is None:
        raise AUTH_ERROR
    return user

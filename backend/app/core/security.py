"""
Security utilities for password hashing, JWT encoding, decoding, and verification.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import bcrypt
import jwt
from backend.app.config import settings
from backend.app.models.schemas import AuthTokenPayload, UserRole, ROLE_PERMISSIONS


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generate a signed JWT token containing user ID, email, role, and permissions."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRES_IN_MINUTES)

    permissions = ROLE_PERMISSIONS.get(role, [])

    payload: Dict[str, Any] = {
        "sub": user_id,
        "user_id": user_id,
        "email": email,
        "role": role.value if isinstance(role, UserRole) else role,
        "permissions": permissions,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[AuthTokenPayload]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")
        role_str = payload.get("role")
        permissions = payload.get("permissions", [])

        if not user_id or not email or not role_str:
            return None

        role = UserRole(role_str)
        return AuthTokenPayload(
            user_id=user_id,
            email=email,
            role=role,
            permissions=permissions
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None

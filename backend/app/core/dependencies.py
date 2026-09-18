"""
FastAPI route dependencies for authentication, authorization, and permission checking.
"""

from typing import List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from backend.app.core.security import decode_access_token
from backend.app.db.session import get_db
from backend.app.models.schemas import AuthTokenPayload, UserOut, UserRole
from backend.app.services.auth_service import AuthService

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db),
) -> UserOut:
    """Validate bearer token and return active user profile."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload: Optional[AuthTokenPayload] = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthService.get_user_by_id(db, payload.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found.",
        )

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserOut]:
    """Extract authenticated user if token present, otherwise None for anonymous visitors."""
    if not credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        if not payload:
            return None
        return AuthService.get_user_by_id(db, payload.user_id)
    except Exception:
        return None


def require_roles(allowed_roles: List[UserRole]):
    """Enforce role-based access control."""
    def role_checker(current_user: UserOut = Depends(get_current_user)) -> UserOut:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {[r.value for r in allowed_roles]}.",
            )
        return current_user

    return role_checker


def require_permissions(required_perms: List[str]):
    """Enforce granular permission-based access control."""
    def permission_checker(current_user: UserOut = Depends(get_current_user)) -> UserOut:
        user_perms = set(current_user.permissions)
        # SYSTEM_ADMIN with admin:all bypasses
        if "admin:all" in user_perms:
            return current_user

        missing = [p for p in required_perms if p not in user_perms]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Missing required permissions {missing}.",
            )
        return current_user

    return permission_checker

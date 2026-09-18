"""
Authentication and User Access Endpoints.
Preserves Prompt 05 RBAC roles and registration/login behaviors.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.app.core.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.schemas import (
    AuthSessionResponse,
    CreateStaffRequest,
    LoginRequest,
    RegisterCitizenRequest,
    UserOut,
    UserRole,
)
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=AuthSessionResponse)
def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    """Authenticate user with email and password, returning JWT access token."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return AuthService.login(
        db=db,
        email=request.email,
        password=request.password,
        ip_address=client_ip,
    )


@router.post("/register", response_model=AuthSessionResponse)
def register_citizen(
    request: RegisterCitizenRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    """Public citizen account registration."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return AuthService.register_citizen(
        db=db,
        request=request,
        ip_address=client_ip,
    )


@router.post("/staff", response_model=UserOut)
def create_staff_account(
    request: CreateStaffRequest,
    req: Request,
    current_user: UserOut = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    db: Session = Depends(get_db),
) -> UserOut:
    """Create a new staff or scheme admin account (System Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return AuthService.create_staff_account(
        db=db,
        admin_user_id=current_user.id,
        request=request,
        ip_address=client_ip,
    )


@router.get("/me", response_model=UserOut)
def get_current_user_profile(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """Retrieve current authenticated user profile and permissions."""
    return current_user

"""
Authentication and Role-Based Access Control (RBAC) Service.
Preserves Prompt 05 user management, roles matrix, token issuance, and audit tracking.
"""

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.config import settings
from backend.app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.app.models.db_models import User
from backend.app.models.schemas import (
    AuthSessionResponse,
    CreateStaffRequest,
    RegisterCitizenRequest,
    ROLE_PERMISSIONS,
    UserOut,
    UserRole,
)
from backend.app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    def register_citizen(
        db: Session,
        request: RegisterCitizenRequest,
        ip_address: Optional[str] = None
    ) -> AuthSessionResponse:
        """Register a new public citizen account."""
        normalized_email = request.email.lower().strip()
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists."
            )

        hashed_pwd = hash_password(request.password)
        new_user = User(
            email=normalized_email,
            password_hash=hashed_pwd,
            full_name=request.full_name,
            role=UserRole.CITIZEN.value,
            department="Public Citizen",
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        AuditService.log_event(
            db=db,
            action="CITIZEN_REGISTERED",
            entity_type="users",
            user_id=new_user.id,
            entity_id=new_user.id,
            details={"email": new_user.email},
            ip_address=ip_address,
        )

        role = UserRole(new_user.role)
        permissions = ROLE_PERMISSIONS.get(role, [])
        token = create_access_token(user_id=new_user.id, email=new_user.email, role=role)

        user_out = UserOut(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            role=role,
            department=new_user.department,
            permissions=permissions,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
        )

        return AuthSessionResponse(
            user=user_out,
            token=token,
            expires_in_minutes=settings.JWT_EXPIRES_IN_MINUTES,
        )

    @staticmethod
    def create_staff_account(
        db: Session,
        admin_user_id: str,
        request: CreateStaffRequest,
        ip_address: Optional[str] = None
    ) -> UserOut:
        """Create a new staff or scheme admin account (Authorized Admin only)."""
        normalized_email = request.email.lower().strip()
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists."
            )

        hashed_pwd = hash_password(request.password)
        new_user = User(
            email=normalized_email,
            password_hash=hashed_pwd,
            full_name=request.full_name,
            role=request.role.value,
            department=request.department or "General Administration",
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        AuditService.log_event(
            db=db,
            action="STAFF_ACCOUNT_CREATED",
            entity_type="users",
            user_id=admin_user_id,
            entity_id=new_user.id,
            details={"email": new_user.email, "role": new_user.role},
            ip_address=ip_address,
        )

        role = UserRole(new_user.role)
        permissions = ROLE_PERMISSIONS.get(role, [])

        return UserOut(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            role=role,
            department=new_user.department,
            permissions=permissions,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
        )

    @staticmethod
    def login(
        db: Session,
        email: str,
        password: str,
        ip_address: Optional[str] = "127.0.0.1"
    ) -> AuthSessionResponse:
        """Authenticate user credentials and return signed JWT."""
        normalized_email = email.lower().strip()
        user = db.query(User).filter(User.email == normalized_email).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        role = UserRole(user.role)
        permissions = ROLE_PERMISSIONS.get(role, [])
        token = create_access_token(user_id=user.id, email=user.email, role=role)

        AuditService.log_event(
            db=db,
            action="USER_LOGIN",
            entity_type="users",
            user_id=user.id,
            entity_id=user.id,
            details={"login_success": True, "role": role.value},
            ip_address=ip_address,
        )

        user_out = UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role,
            department=user.department,
            permissions=permissions,
            is_active=user.is_active,
            created_at=user.created_at,
        )

        return AuthSessionResponse(
            user=user_out,
            token=token,
            expires_in_minutes=settings.JWT_EXPIRES_IN_MINUTES,
        )

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[UserOut]:
        """Fetch user by primary ID."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None

        role = UserRole(user.role)
        permissions = ROLE_PERMISSIONS.get(role, [])

        return UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role,
            department=user.department,
            permissions=permissions,
            is_active=user.is_active,
            created_at=user.created_at,
        )

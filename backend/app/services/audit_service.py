"""
Audit logging service for tracking administrative events and data access.
"""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.app.models.db_models import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        action: str,
        entity_type: str,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create and persist an immutable audit record."""
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(audit_entry)
        try:
            db.commit()
            db.refresh(audit_entry)
        except Exception:
            db.rollback()
        return audit_entry

"""
Audit Log Inspection Endpoints (Admin only).
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.dependencies import require_permissions
from backend.app.db.session import get_db
from backend.app.models.db_models import AuditLog
from backend.app.models.schemas import UserOut

router = APIRouter(prefix="/admin/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=List[Dict[str, Any]])
def get_audit_logs(
    current_user: UserOut = Depends(require_permissions(["audit:read"])),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve system administrative audit logs (Authorized admin only)."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]

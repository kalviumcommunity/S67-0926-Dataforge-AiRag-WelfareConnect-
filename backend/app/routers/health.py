"""
Health check endpoints for system monitoring, load balancers, and container probes.
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.schemas import HealthComponentStatus, HealthResponse
from backend.app.services.pinecone_service import pinecone_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health_status(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint returning the status of database, vector store, and services.
    """
    components = {}

    # 1. Database Check
    try:
        db.execute(text("SELECT 1"))
        components["database"] = HealthComponentStatus(
            status="healthy",
            message="Database connection active and responsive."
        )
    except Exception as e:
        components["database"] = HealthComponentStatus(
            status="degraded",
            message=f"Database check failed: {str(e)}"
        )

    # 2. Vector DB (Pinecone) Check
    pinecone_status = pinecone_service.health_check()
    components["vector_store"] = HealthComponentStatus(
        status="healthy" if pinecone_status["status"] in ["connected", "configured_placeholder"] else "unhealthy",
        message=f"Pinecone index: {pinecone_status['index_name']} ({pinecone_status['status']})"
    )

    # 3. Storage Engine
    components["storage"] = HealthComponentStatus(
        status="healthy",
        message=f"Storage type: {settings.STORAGE_TYPE}"
    )

    overall_status = "healthy"
    if any(c.status == "unhealthy" for c in components.values()):
        overall_status = "unhealthy"
    elif any(c.status == "degraded" for c in components.values()):
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        environment=settings.ENV,
        components=components,
        timestamp=datetime.utcnow(),
    )

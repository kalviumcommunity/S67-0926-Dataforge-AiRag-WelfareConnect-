"""
Search and Query Execution Endpoints.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.schemas import QueryRequest, QueryResponse
from backend.app.services.search_service import SearchService

router = APIRouter(prefix="/query", tags=["Search & RAG"])


@router.post("/search", response_model=QueryResponse)
def execute_search_query(
    request: QueryRequest,
    x_session_id: str = Header("session-anonymous", alias="X-Session-ID"),
    db: Session = Depends(get_db),
) -> QueryResponse:
    """
    Execute natural language scheme question answering.
    Returns grounded answers with document name and exact page number citations.
    """
    return SearchService.execute_query(db, request, session_id=x_session_id)

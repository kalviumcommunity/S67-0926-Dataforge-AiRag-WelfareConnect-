"""
Search, Query Execution, Eligibility Evaluation, and History Endpoints.
Enforces role-based permissions for eligibility calculations and operator session history.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from backend.app.core.dependencies import get_optional_user, require_permissions
from backend.app.db.session import get_db
from backend.app.models.db_models import QuestionAnswer
from backend.app.models.schemas import (
    CitationOut,
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    QueryHistoryItem,
    QueryRequest,
    QueryResponse,
    QueryUnderstandingResult,
    UserOut,
)
from backend.app.services.query_understanding import query_understanding_service
from backend.app.services.search_service import SearchService

router = APIRouter(prefix="/query", tags=["Search & RAG"])


@router.post("/understand", response_model=QueryUnderstandingResult)
def understand_query(
    request: QueryRequest,
) -> QueryUnderstandingResult:
    """
    Perform pre-retrieval query understanding, entity extraction, schema validation,
    and follow-up question generation for missing safety fields.
    Open to Public, Citizens, Helpdesk, and Administrators.
    """
    return query_understanding_service.understand_query(request.query)


@router.post("/search", response_model=QueryResponse)
def execute_search_query(
    request: QueryRequest,
    x_session_id: str = Header("session-anonymous", alias="X-Session-ID"),
    current_user: Optional[UserOut] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> QueryResponse:
    """
    Execute natural language scheme question answering.
    Open to Public, Citizens, Helpdesk, and Administrators.
    Returns grounded answers with document name and exact page number citations.
    """
    session_id = x_session_id
    if current_user:
        session_id = f"user-{current_user.id}"

    return SearchService.execute_query(db, request, session_id=session_id, current_user=current_user)


@router.post("/eligibility", response_model=EligibilityCheckResponse)
def check_scheme_eligibility(
    request: EligibilityCheckRequest,
    current_user: UserOut = Depends(require_permissions(["eligibility:check"])),
    db: Session = Depends(get_db),
) -> EligibilityCheckResponse:
    """
    Algorithmic eligibility screening based on official scheme parameters (Helpdesk staff and authorized roles).
    """
    eligible = []
    ineligible = []
    citations = []

    # Evaluate against PMAY-U income threshold (Rs. 3,00,000 for EWS)
    if request.annual_income is not None:
        if request.annual_income <= 300000:
            eligible.append({
                "scheme_name": "Pradhan Mantri Awas Yojana - Urban (PMAY-U) - CLSS EWS",
                "department": "Ministry of Housing and Urban Affairs",
                "benefit": "6.5% interest subsidy on home loans up to Rs. 6,00,000",
                "qualifying_criteria": f"Annual income Rs. {request.annual_income:,.2f} <= Rs. 3,00,000 limit",
                "citation": "PMAY-U Guidelines 2024, Page 14",
            })
            citations.append(
                CitationOut(
                    document_id="doc-pmay-001",
                    document_title="PMAY-U Operational Guidelines 2024",
                    page_number=14,
                    excerpt="EWS households having an annual income up to Rs. 3,00,000 are eligible for interest subsidy.",
                    score=0.95,
                )
            )
        else:
            ineligible.append({
                "scheme_name": "Pradhan Mantri Awas Yojana - Urban (PMAY-U) - CLSS EWS",
                "reason": f"Annual income Rs. {request.annual_income:,.2f} exceeds Rs. 3,00,000 limit for EWS.",
            })

    # Evaluate against PM-Kisan landholding criteria
    if request.landholding_hectares is not None:
        if request.landholding_hectares > 0:
            eligible.append({
                "scheme_name": "PM-Kisan Samman Nidhi",
                "department": "Ministry of Agriculture & Farmers Welfare",
                "benefit": "Rs. 6,000 per year in 3 equal installments of Rs. 2,000",
                "qualifying_criteria": f"Cultivable landholding of {request.landholding_hectares} hectares",
                "citation": "PM-Kisan Guidelines 2024, Page 4",
            })
            citations.append(
                CitationOut(
                    document_id="doc-pmkisan-001",
                    document_title="PM-Kisan Scheme Guidelines 2024",
                    page_number=4,
                    excerpt="All landholding farmer families having cultivable landholding are eligible.",
                    score=0.92,
                )
            )

    summary = (
        f"Evaluated criteria: {len(eligible)} potentially applicable schemes found, "
        f"{len(ineligible)} schemes ineligible based on stated parameters."
    )

    return EligibilityCheckResponse(
        eligible_schemes=eligible,
        ineligible_schemes=ineligible,
        evaluation_summary=summary,
        citations=citations,
    )


@router.get("/history", response_model=List[QueryHistoryItem])
def get_query_history(
    current_user: UserOut = Depends(require_permissions(["history:read"])),
    db: Session = Depends(get_db),
) -> List[QueryHistoryItem]:
    """Retrieve recent query history (Helpdesk Operator & Administrator only)."""
    records = db.query(QuestionAnswer).order_by(QuestionAnswer.created_at.desc()).limit(50).all()
    return [
        QueryHistoryItem(
            id=r.id,
            session_id=r.session_id,
            question=r.question,
            answer=r.answer,
            is_refusal=r.is_refusal,
            latency_ms=r.latency_ms,
            created_at=r.created_at,
        )
        for r in records
    ]

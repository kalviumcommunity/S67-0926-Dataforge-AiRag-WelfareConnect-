"""
User Feedback Submission Endpoints.
Allows Citizens and Helpdesk staff to submit feedback on answer accuracy.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from backend.app.core.dependencies import get_optional_user, require_permissions
from backend.app.db.session import get_db
from backend.app.models.db_models import QuestionAnswer, UserFeedback
from backend.app.models.schemas import FeedbackCreateRequest, FeedbackResponse, UserOut
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", response_model=FeedbackResponse)
def submit_feedback(
    request: FeedbackCreateRequest,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["feedback:submit"])),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Submit rating and feedback for a generated answer."""
    qa = db.query(QuestionAnswer).filter(QuestionAnswer.id == request.qa_id).first()
    if not qa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question-Answer record not found."
        )

    feedback_rec = UserFeedback(
        qa_id=qa.id,
        user_id=current_user.id,
        rating=request.rating,
        feedback_text=request.feedback_text,
    )
    db.add(feedback_rec)
    db.commit()
    db.refresh(feedback_rec)

    client_ip = req.client.host if req.client else "127.0.0.1"
    AuditService.log_event(
        db=db,
        action="FEEDBACK_SUBMITTED",
        entity_type="user_feedback",
        user_id=current_user.id,
        entity_id=feedback_rec.id,
        details={"qa_id": qa.id, "rating": request.rating},
        ip_address=client_ip,
    )

    return FeedbackResponse(
        success=True,
        feedback_id=feedback_rec.id,
        message="Thank you for submitting feedback on answer quality.",
    )

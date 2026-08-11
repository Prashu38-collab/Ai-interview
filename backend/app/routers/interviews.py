from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.interview import Interview
from app.models.user import User
from app.routers.deps import get_ai_service, get_current_user
from app.schemas.interview import (
    CandidateAnalysisOut,
    InterviewCreate,
    InterviewListItem,
    InterviewOut,
)
from app.services.ai.base import AIService
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Interview:
    """Create a new interview for the authenticated user."""
    return InterviewService(db).create(payload, user_id=current_user.id)


@router.get("", response_model=list[InterviewListItem])
def list_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List the current user's interviews, newest first."""
    service = InterviewService(db)
    return [service.list_item(i) for i in service.list_for_user(current_user.id)]


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Interview:
    """Fetch a single interview (owner only)."""
    return InterviewService(db).get_owned(interview_id, current_user.id)


@router.post("/{interview_id}/analyze", response_model=CandidateAnalysisOut)
def analyze_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai: AIService = Depends(get_ai_service),
) -> CandidateAnalysisOut:
    """Run AI analysis on the interview's resume + job description."""
    service = InterviewService(db)
    interview = service.get_owned(interview_id, current_user.id)
    interview = service.run_analysis(interview, ai)
    return CandidateAnalysisOut.model_validate(interview.analysis)

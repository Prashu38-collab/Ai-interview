from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.routers.deps import get_ai_service, get_current_user
from app.schemas.report import InterviewReportOut
from app.services.ai.base import AIService
from app.services.interview_service import InterviewService
from app.services.report_service import ReportService

router = APIRouter(prefix="/interviews", tags=["reports"])


@router.post("/{interview_id}/complete", response_model=InterviewReportOut)
def complete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai: AIService = Depends(get_ai_service),
) -> InterviewReportOut:
    """Finalize the interview and build the report."""
    interview = InterviewService(db).get_owned(interview_id, current_user.id)
    report = ReportService(db).complete(interview, ai)
    return InterviewReportOut.model_validate(report)


@router.get("/{interview_id}/report", response_model=InterviewReportOut)
def get_report(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewReportOut:
    """Fetch the final report for a completed interview."""
    interview = InterviewService(db).get_owned(interview_id, current_user.id)
    report = ReportService(db).get_report(interview)
    return InterviewReportOut.model_validate(report)

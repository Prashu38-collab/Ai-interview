"""Interview business logic: create, list, ownership checks, AI analysis."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.question import Question
from app.schemas.interview import InterviewCreate
from app.services.ai.base import AIService


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_owned(self, interview_id: int, user_id: int) -> Interview:
        """Return an interview owned by the user, or raise 404/403."""
        interview = self.db.get(Interview, interview_id)
        if interview is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found."
            )
        if interview.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this interview.",
            )
        return interview

    def list_for_user(self, user_id: int) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.user_id == user_id)
            .order_by(Interview.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def list_item(self, interview: Interview) -> dict:
        """Shape an interview into a dashboard list item with counts + score."""
        q_count = self.db.scalar(
            select(func.count(Question.id)).where(Question.interview_id == interview.id)
        )
        answered_count = self.db.scalar(
            select(func.count(Question.id)).where(
                Question.interview_id == interview.id, Question.status == "answered"
            )
        )
        report = interview.report
        return {
            "id": interview.id,
            "target_role": interview.target_role,
            "experience_level": interview.experience_level,
            "status": interview.status,
            "created_at": interview.created_at,
            "question_count": q_count or 0,
            "answered_count": answered_count or 0,
            "report_overall_score": report.overall_score if report else None,
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def create(self, payload: InterviewCreate, user_id: int) -> Interview:
        interview = Interview(
            user_id=user_id,
            target_role=payload.target_role,
            experience_level=payload.experience_level,
            job_description=payload.job_description,
            resume_text=payload.resume_text,
            number_of_questions=payload.number_of_questions,
            duration_minutes=payload.duration_minutes,
            status="created",
        )
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def run_analysis(self, interview: Interview, ai: AIService) -> Interview:
        """Analyze resume + job description with the AI and store the result."""
        analysis = ai.analyze_candidate(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            job_description=interview.job_description,
            resume_text=interview.resume_text,
        )
        interview.analysis = analysis.model_dump()
        interview.status = "ready"
        self.db.commit()
        self.db.refresh(interview)
        return interview

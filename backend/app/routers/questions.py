from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.question import Question
from app.models.user import User
from app.routers.deps import get_ai_service, get_current_user
from app.schemas.question import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    QuestionOut,
)
from app.services.ai.base import AIService
from app.services.interview_service import InterviewService
from app.services.question_service import QuestionService

router = APIRouter(prefix="/interviews", tags=["questions"])


@router.post("/{interview_id}/generate-questions", response_model=GenerateQuestionsResponse)
def generate_questions(
    interview_id: int,
    payload: GenerateQuestionsRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai: AIService = Depends(get_ai_service),
) -> GenerateQuestionsResponse:
    """Generate interview questions for the given interview (deduplicated)."""
    interview = InterviewService(db).get_owned(interview_id, current_user.id)
    difficulty = (payload.difficulty if payload else None) or interview.current_difficulty
    questions = QuestionService(db).generate(interview, ai, difficulty=difficulty)
    return GenerateQuestionsResponse(
        generated=len(questions),
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.get("/{interview_id}/questions", response_model=list[QuestionOut])
def list_questions(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Question]:
    """List all questions for an interview, in order."""
    interview = InterviewService(db).get_owned(interview_id, current_user.id)
    return QuestionService(db).list_for_interview(interview.id)

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.routers.deps import get_ai_service, get_current_user
from app.schemas.answer import AnswerCreate, AnswerSubmissionResponse
from app.schemas.evaluation import EvaluationOut
from app.services.ai.base import AIService
from app.services.evaluation_service import EvaluationService
from app.services.question_service import QuestionService

router = APIRouter(prefix="/questions", tags=["answers"])


@router.post("/{question_id}/answer", response_model=AnswerSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_answer(
    question_id: int,
    payload: AnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai: AIService = Depends(get_ai_service),
) -> AnswerSubmissionResponse:
    """Submit an answer to a question; store it and evaluate it with the AI."""
    question = QuestionService(db).get_owned(question_id, current_user.id)
    _, evaluation, next_difficulty, duplicate_of, duplicate_warning = EvaluationService(db).submit_answer(
        question, payload.text, ai, model_used=ai.name
    )
    return AnswerSubmissionResponse(
        question_id=question.id,
        evaluation=EvaluationOut.model_validate(evaluation),
        next_difficulty=next_difficulty,
        duplicate_of=duplicate_of,
        duplicate_warning=duplicate_warning,
    )

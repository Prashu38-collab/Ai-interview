"""Answer + evaluation business logic, including adaptive difficulty.

Adaptive difficulty (documented design decision, see README §"Adaptive
Difficulty"): a simple, deterministic rule — no ML.
    score >= 8 : move difficulty up one step
    5 <= score < 8 : keep difficulty
    score < 5 : move difficulty down one step

The new target difficulty is stored on the interview and used when the next
question is picked (see ``QuestionService.next_pending``) and when further
questions are generated.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import AIService

DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def adapt_difficulty(score: float, current: str) -> str:
    """Apply the rule-based adaptive difficulty to the next question."""
    idx = DIFFICULTY_ORDER.index(current) if current in DIFFICULTY_ORDER else 1
    if score >= 8:
        idx = min(idx + 1, len(DIFFICULTY_ORDER) - 1)
    elif score < 5:
        idx = max(idx - 1, 0)
    return DIFFICULTY_ORDER[idx]


class EvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_answer(
        self,
        question: Question,
        answer_text: str,
        ai: AIService,
        model_used: str | None = None,
    ) -> tuple[Answer, Evaluation, str | None]:
        """Store the answer, evaluate it with the AI, adapt difficulty.

        Returns (answer, evaluation, next_difficulty).
        Raises 400 if the question was already answered.
        """
        if question.status == "answered" or question.answer is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This question has already been answered.",
            )

        answer = Answer(question_id=question.id, text=answer_text)
        self.db.add(answer)

        evaluation_data = ai.evaluate_answer(
            question_text=question.text,
            skill=question.skill,
            difficulty=question.difficulty,
            question_type=question.question_type,
            expected_concepts=question.expected_concepts,
            answer_text=answer_text,
        )
        evaluation = Evaluation(
            answer_id=0,  # set after flush
            score=evaluation_data.score,
            strengths=evaluation_data.strengths,
            weaknesses=evaluation_data.weaknesses,
            feedback=evaluation_data.feedback,
            missing_concepts=evaluation_data.missing_concepts,
            model_used=model_used,
        )
        self.db.add(evaluation)

        question.status = "answered"
        interview = self.db.get(Interview, question.interview_id)
        next_difficulty = adapt_difficulty(evaluation_data.score, interview.current_difficulty)
        interview.current_difficulty = next_difficulty
        if interview.status in {"ready", "created"}:
            interview.status = "in_progress"

        self.db.flush()  # assign answer.id so evaluation FK can reference it
        evaluation.answer_id = answer.id
        self.db.commit()
        self.db.refresh(answer)
        self.db.refresh(evaluation)
        return answer, evaluation, next_difficulty

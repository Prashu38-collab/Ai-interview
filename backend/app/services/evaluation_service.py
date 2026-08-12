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

import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import AIService

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# Jaccard similarity at or above this marks an answer as a duplicate of an
# earlier one (e.g. the same text pasted for every question).
DUPLICATE_SIMILARITY = 0.8


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _jaccard(a: str, b: str) -> float:
    ta = set(_normalize(a).split())
    tb = set(_normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


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

    def _previous_answers(self, interview_id: int, exclude_answer_id: int) -> list[Answer]:
        stmt = (
            select(Answer)
            .join(Question, Question.id == Answer.question_id)
            .where(
                Question.interview_id == interview_id,
                Answer.id != exclude_answer_id,
            )
        )
        return list(self.db.scalars(stmt))

    def submit_answer(
        self,
        question: Question,
        answer_text: str,
        ai: AIService,
        model_used: str | None = None,
    ) -> tuple[Answer, Evaluation, str | None, int | None, str | None]:
        """Store the answer, evaluate it with the AI, adapt difficulty.

        Returns (answer, evaluation, next_difficulty, duplicate_of, warning).
        Raises 400 if the question was already answered.
        """
        if question.status == "answered" or question.answer is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This question has already been answered.",
            )

        answer = Answer(question_id=question.id, text=answer_text)
        self.db.add(answer)
        self.db.flush()  # assign answer.id before creating the evaluation

        duplicate_of: int | None = None
        duplicate_warning: str | None = None
        for prior in self._previous_answers(question.interview_id, exclude_answer_id=answer.id):
            if _jaccard(answer_text, prior.text) >= DUPLICATE_SIMILARITY:
                duplicate_of = prior.id
                duplicate_warning = (
                    "This answer is very similar to an earlier answer in this "
                    "interview. Copying the same text across questions won't "
                    "reflect how well you know each topic — try to give a "
                    "fresh, specific answer."
                )
                answer.duplicate_of = prior.id
                break

        evaluation_data = ai.evaluate_answer(
            question_text=question.text,
            skill=question.skill,
            difficulty=question.difficulty,
            question_type=question.question_type,
            expected_concepts=question.expected_concepts,
            answer_text=answer_text,
        )
        evaluation = Evaluation(
            answer_id=answer.id,
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

        self.db.commit()
        self.db.refresh(answer)
        self.db.refresh(evaluation)
        return answer, evaluation, next_difficulty, duplicate_of, duplicate_warning

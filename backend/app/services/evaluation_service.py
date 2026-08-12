"""Answer + evaluation business logic.

Pipeline for every submitted answer:
    AI analysis (structured dimensions, never a score)
        -> score engine (deterministic score + hard gates)
        -> feedback service (candidate-facing text)
        -> persist the full structured evaluation
        -> plan + generate a targeted coaching follow-up (if warranted)
        -> adapt difficulty for the next question

The LLM never decides the final score; the app does. See README §"Scoring".
"""

import logging
import re
import time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import AIService
from app.services.feedback_service import FeedbackService
from app.services.question_planner import QuestionPlanner
from app.services.question_validator import QuestionValidator
from app.services.score_engine import ScoreEngine

logger = logging.getLogger(__name__)

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
        self.score_engine = ScoreEngine()
        self.feedback = FeedbackService()
        self.planner = QuestionPlanner()
        self.validator = QuestionValidator()

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
    ) -> tuple[Answer, Evaluation, str | None, int | None, str | None, Question | None]:
        """Store the answer, evaluate it, adapt difficulty, plan a follow-up.

        Returns ``(answer, evaluation, next_difficulty, duplicate_of, warning,
        follow_up_question)``. Raises 400 if the question was already answered.
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

        # --- Evaluate through the structured pipeline ----------------------
        started = time.perf_counter()
        dims = ai.evaluate_answer(
            question_text=question.text,
            skill=question.skill,
            concept=question.concept,
            difficulty=question.difficulty,
            question_type=question.question_type,
            intent=question.intent,
            expected_concepts=question.expected_concepts,
            core_requirements=question.core_requirements or [],
            optional_depth_points=question.optional_depth_points or [],
            common_misconceptions=question.common_misconceptions or [],
            answer_text=answer_text,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        score = self.score_engine.score(dims)
        fb = self.feedback.build(
            dims,
            skill=question.skill,
            concept=question.concept,
            question_type=question.question_type,
        )

        evaluation = Evaluation(
            answer_id=answer.id,
            score=score,
            answer_status=dims.answer_status,
            relevance_score=dims.relevance_score,
            understanding_score=dims.understanding_score,
            correctness_score=dims.correctness_score,
            completeness_score=dims.completeness_score,
            reasoning_score=dims.reasoning_score,
            satisfied_requirements=dims.satisfied_requirements,
            partial_requirements=dims.partial_requirements,
            missing_requirements=dims.missing_requirements,
            technical_errors=dims.technical_errors,
            misconceptions=dims.misconceptions,
            contradictions=dims.contradictions,
            recommended_topics=dims.recommended_topics,
            follow_up_question=dims.follow_up_question,
            follow_up_concept=dims.follow_up_concept,
            confidence=dims.confidence,
            evaluator_version=self.score_engine.settings.evaluator_version,
            prompt_version=self.score_engine.settings.prompt_version,
            model_version=model_used or ai.name,
            evaluation_latency_ms=latency_ms,
            strengths=fb["strengths"],
            weaknesses=fb["weaknesses"],
            feedback=fb["feedback"],
            missing_concepts=dims.missing_requirements,
            model_used=model_used or ai.name,
        )
        self.db.add(evaluation)

        question.status = "answered"
        interview = self.db.get(Interview, question.interview_id)
        next_difficulty = adapt_difficulty(score, interview.current_difficulty)
        interview.current_difficulty = next_difficulty
        if interview.status in {"ready", "created"}:
            interview.status = "in_progress"

        follow_up = self._plan_follow_up(interview, question, dims, ai)

        self.db.commit()
        self.db.refresh(answer)
        self.db.refresh(evaluation)
        return answer, evaluation, next_difficulty, duplicate_of, duplicate_warning, follow_up

    # ------------------------------------------------------------------
    def _plan_follow_up(
        self,
        interview: Interview,
        question: Question,
        dims,
        ai: AIService,
    ) -> Question | None:
        """Generate a targeted coaching follow-up when a gap is detected."""
        questions = self.planner_questions(interview.id)
        slot = self.planner.plan_follow_up(interview, question, dims, questions)
        if slot is None:
            return None

        qdata = None
        try:
            pool = ai.generate_questions(
                target_role=interview.target_role,
                experience_level=interview.experience_level,
                analysis=None if not interview.analysis else _analysis_model(interview),
                number=1,
                difficulty=slot.difficulty,
                previous_questions=[q.text for q in questions],
                previous_concepts=[q.concept or q.skill for q in questions],
                plan=[slot],
            )
            if pool:
                qdata = pool[0]
        except Exception:  # provider failure must not break answer submission
            logger.exception("Follow-up generation failed; using concept-bank seed.")
            qdata = None

        if qdata is None:
            qdata = self.validator.build_from_slot(slot)
        if qdata.question in {q.text for q in questions}:
            return None

        follow_up = Question(
            interview_id=interview.id,
            text=qdata.question,
            skill=slot.skill,
            concept=qdata.concept or slot.concept,
            intent=qdata.intent or slot.intent,
            difficulty=qdata.difficulty,
            question_type=qdata.question_type,
            expected_concepts=qdata.expected_concepts,
            core_requirements=qdata.core_requirements,
            optional_depth_points=qdata.optional_depth_points,
            common_misconceptions=qdata.common_misconceptions,
            follow_up_of=question.id,
            order_index=max((q.order_index for q in questions), default=-1) + 1,
            status="pending",
        )
        self.db.add(follow_up)
        return follow_up

    def planner_questions(self, interview_id: int) -> list[Question]:
        stmt = select(Question).where(Question.interview_id == interview_id).order_by(Question.order_index)
        return list(self.db.scalars(stmt))


def _analysis_model(interview: Interview):
    from app.services.ai.base import CandidateAnalysis

    return CandidateAnalysis.model_validate(interview.analysis) if interview.analysis else CandidateAnalysis()

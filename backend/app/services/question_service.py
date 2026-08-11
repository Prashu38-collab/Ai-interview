"""Question business logic: generation (with dedup), retrieval, ordering."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import AIService, CandidateAnalysis


class QuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(self, interview: Interview, ai: AIService, difficulty: str = "medium") -> list[Question]:
        """Generate questions for an interview, filling up to its target count.

        - Auto-runs analysis first if missing (smoother client flow).
        - Passes existing question texts to the AI so it avoids repeats.
        - Skips any returned duplicate at the DB level too.
        """
        if not interview.analysis:
            analysis = ai.analyze_candidate(
                target_role=interview.target_role,
                experience_level=interview.experience_level,
                job_description=interview.job_description,
                resume_text=interview.resume_text,
            )
            interview.analysis = analysis.model_dump()
        else:
            analysis = CandidateAnalysis.model_validate(interview.analysis)

        existing = list(self._questions_for(interview.id))
        existing_texts = [q.text for q in existing]

        number_needed = max(0, interview.number_of_questions - len(existing))
        if number_needed == 0:
            return existing

        generated = ai.generate_questions(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            analysis=analysis,
            number=number_needed,
            difficulty=difficulty,
            previous_questions=existing_texts,
        )

        created: list[Question] = []
        for i, q in enumerate(generated):
            if q.question in existing_texts:
                continue  # duplicate prevention
            question = Question(
                interview_id=interview.id,
                text=q.question,
                skill=q.skill,
                difficulty=q.difficulty,
                question_type=q.question_type,
                expected_concepts=q.expected_concepts,
                order_index=len(existing) + len(created),
                status="pending",
            )
            self.db.add(question)
            existing_texts.append(q.question)
            created.append(question)

        interview.status = "ready"
        self.db.commit()
        for q in created:
            self.db.refresh(q)
        return existing + created

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def list_for_interview(self, interview_id: int) -> list[Question]:
        stmt = select(Question).where(Question.interview_id == interview_id).order_by(Question.order_index)
        return list(self.db.scalars(stmt))

    def get_owned(self, question_id: int, user_id: int) -> Question:
        """Fetch a question and verify the user owns the parent interview."""
        question = self.db.get(Question, question_id)
        if question is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
        interview = self.db.get(Interview, question.interview_id)
        if interview is None or interview.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this question.",
            )
        return question

    def next_pending(self, interview: Interview) -> Question | None:
        """Return the next unanswered question, preferring the adaptive
        difficulty target so the interview actually adjusts to performance."""
        pending = [
            q
            for q in self._questions_for(interview.id)
            if q.status == "pending"
        ]
        if not pending:
            return None
        for q in pending:
            if q.difficulty == interview.current_difficulty:
                return q
        return pending[0]

    def _questions_for(self, interview_id: int) -> list[Question]:
        stmt = select(Question).where(Question.interview_id == interview_id).order_by(Question.order_index)
        return list(self.db.scalars(stmt))

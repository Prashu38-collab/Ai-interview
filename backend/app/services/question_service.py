"""Question business logic: planning, generation (with validation + dedup),
retrieval, ordering."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import AIService, CandidateAnalysis, QuestionData, QuestionPlanSlot
from app.services.question_planner import QuestionPlanner
from app.services.question_validator import QuestionValidator


class QuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.planner = QuestionPlanner()
        self.validator = QuestionValidator()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(
        self,
        interview: Interview,
        ai: AIService,
        difficulty: str = "medium",
        replace_pending: bool = False,
    ) -> list[Question]:
        """Plan + generate questions for an interview, up to its target count.

        Flow: ensure analysis -> plan slots (concept/difficulty/type per
        question) -> ask the AI to fill each slot -> validate each result
        (falling back to a curated concept-bank seed) -> persist with its
        evaluation rubric. Duplicate/overlapping questions are dropped.
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
        if replace_pending:
            for q in existing:
                if q.status == "pending":
                    self.db.delete(q)
            self.db.flush()
            existing = [q for q in existing if q.status != "pending"]

        number_needed = max(0, interview.number_of_questions - len(existing))
        if number_needed == 0:
            return existing

        existing_texts = [q.text for q in existing]
        existing_concepts = [q.concept or q.skill for q in existing]
        slots = self.planner.plan_initial(
            interview, analysis.topics, existing, number_needed
        )
        if not slots:
            return existing

        generated = ai.generate_questions(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            analysis=analysis,
            number=len(slots),
            difficulty=difficulty,
            previous_questions=existing_texts,
            previous_concepts=existing_concepts,
            plan=slots,
        )

        created: list[Question] = []
        used_texts = set(existing_texts)
        for idx, slot in enumerate(slots):
            qdata = generated[idx] if idx < len(generated) else None
            qdata = self._fit_slot(qdata, slot, used_texts, existing_concepts)
            if qdata is None or qdata.question in used_texts:
                continue
            question = Question(
                interview_id=interview.id,
                text=qdata.question,
                skill=qdata.skill or slot.skill,
                concept=qdata.concept or slot.concept,
                intent=qdata.intent or slot.intent,
                difficulty=qdata.difficulty,
                question_type=qdata.question_type,
                expected_concepts=qdata.expected_concepts,
                core_requirements=qdata.core_requirements,
                optional_depth_points=qdata.optional_depth_points,
                common_misconceptions=qdata.common_misconceptions,
                order_index=len(existing) + len(created),
                status="pending",
            )
            self.db.add(question)
            used_texts.add(qdata.question)
            created.append(question)

        interview.status = "ready"
        self.db.commit()
        for q in created:
            self.db.refresh(q)
        return existing + created

    def _fit_slot(
        self,
        qdata,
        slot: QuestionPlanSlot,
        used_texts: set[str],
        existing_concepts: list[str],
    ) -> QuestionData | None:
        """Validate a generated question for a slot; fall back to a seed.

        If the generated question is unusable we fall back to a curated
        concept-bank question so generation can never stall.
        """
        fallback = self.validator.build_from_slot(slot)
        if qdata is None:
            return fallback if fallback.question not in used_texts else None

        result = self.validator.validate(
            qdata,
            previous_texts=sorted(used_texts),
            previous_concepts=existing_concepts,
        )
        if not result.valid:
            return fallback if fallback.question not in used_texts else None

        # Repair any missing metadata from the authoritative plan slot.
        if not qdata.concept:
            qdata.concept = slot.concept
        if not qdata.intent:
            qdata.intent = slot.intent
        if not qdata.core_requirements:
            qdata.core_requirements = fallback.core_requirements
            qdata.optional_depth_points = fallback.optional_depth_points
            qdata.common_misconceptions = fallback.common_misconceptions
        return qdata

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
        """Return the next unanswered question.

        Follow-up questions are asked immediately after the question they
        deepen; otherwise prefer the adaptive difficulty target so the
        interview actually adjusts to performance.
        """
        pending = [
            q for q in self._questions_for(interview.id) if q.status == "pending"
        ]
        if not pending:
            return None
        # Prioritise any queued follow-up whose parent was already answered.
        for q in pending:
            if q.follow_up_of is not None and self.db.get(Question, q.follow_up_of) is not None:
                parent = self.db.get(Question, q.follow_up_of)
                if parent is not None and parent.status == "answered":
                    return q
        for q in pending:
            if q.difficulty == interview.current_difficulty and q.follow_up_of is None:
                return q
        return pending[0]

    def _questions_for(self, interview_id: int) -> list[Question]:
        stmt = select(Question).where(Question.interview_id == interview_id).order_by(Question.order_index)
        return list(self.db.scalars(stmt))

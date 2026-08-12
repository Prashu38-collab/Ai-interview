"""Question planner: decides *what to ask next*.

Responsibilities:
- plan the initial batch of questions across the interview's topics,
  spreading across concepts and rotating question types;
- plan a targeted coaching follow-up when an answer shows a specific gap.

It considers interview configuration, difficulty target, covered concepts,
demonstrated weak/strong concepts, and the previous question type — never a
random pick. Follow-ups are only planned when they have a clear coaching
purpose (deepening a partial answer), and never repeat an already-asked
concept unless deepening it deliberately.
"""

from app.models.interview import Interview
from app.models.question import Question
from app.services.ai.base import EvaluationDimensions, QuestionPlanSlot
from app.services.ai.concept_bank import ConceptSpec, concepts_for_skill

DIFFICULTY_RANKS = {"easy": 0, "medium": 1, "hard": 2}
RANK_DIFFICULTIES = ["easy", "medium", "hard"]

# Type rotation when a concept does not list supported types explicitly.
GENERIC_TYPE_CYCLE = [
    "explanation",
    "scenario",
    "coding",
    "tradeoff",
    "debugging",
]

# intent per question type, so every question carries a purpose.
INTENT_BY_TYPE: dict[str, str] = {
    "definition": "verify precise understanding of a concept",
    "explanation": "check understanding of a concept and its importance",
    "comparison": "assess ability to compare alternatives and trade-offs",
    "scenario": "evaluate applying the concept in a real situation",
    "debugging": "evaluate diagnostic reasoning under failure",
    "coding": "evaluate ability to translate understanding into code",
    "system_design": "evaluate design reasoning and scalability thinking",
    "behavioral": "evaluate real-world experience and behaviour",
    "architecture": "evaluate structural design reasoning",
    "tradeoff": "evaluate awareness of costs and trade-offs",
}

# Follow-up planning caps: never generate more than this many questions per
# interview, and never stack follow-ups on the same concept back to back.
MAX_FOLLOWUP_DEPTH = 2
MAX_FOLLOWUP_TOTAL = 3


class QuestionPlanner:
    # ------------------------------------------------------------------
    # Initial batch planning
    # ------------------------------------------------------------------
    def plan_initial(
        self,
        interview: Interview,
        topics: list[str],
        questions: list[Question],
        number: int,
    ) -> list[QuestionPlanSlot]:
        """Plan ``number`` slots for the initial question batch."""
        if number <= 0:
            return []

        asked_concepts = {
            (q.skill, q.concept or q.skill) for q in questions if q.status == "pending"
        }
        target_rank = DIFFICULTY_RANKS.get(interview.current_difficulty or "medium", 1)

        # Candidates: one entry per concept, spread across topics.
        candidates: list[tuple[str, ConceptSpec | None]] = []
        for topic in topics or ["Core Programming"]:
            specs = concepts_for_skill(topic)
            if specs:
                for spec in specs:
                    if (topic, spec.name) not in asked_concepts:
                        candidates.append((topic, spec))
            else:
                # Unknown skill: still ask about it, generic phrasings apply.
                candidates.append((topic, None))

        slots: list[QuestionPlanSlot] = []
        used_skills: dict[str, int] = {}
        used_types: dict[str, int] = {}
        idx = 0
        while len(slots) < number and candidates:
            skill, spec = candidates[idx % len(candidates)]
            slot = self._slot_for(
                skill=skill,
                spec=spec,
                target_rank=target_rank,
                round_index=used_skills.get(skill, 0),
                type_offset=used_types.get(skill, 0),
            )
            if not any(s.skill == skill and s.concept == slot.concept for s in slots):
                slots.append(slot)
                used_skills[skill] = used_skills.get(skill, 0) + 1
                used_types[skill] = used_types.get(skill, 0) + 1
            idx += 1
        return slots[:number]

    # ------------------------------------------------------------------
    # Follow-up planning (called after an answer is evaluated)
    # ------------------------------------------------------------------
    def plan_follow_up(
        self,
        interview: Interview,
        question: Question,
        dims: EvaluationDimensions,
        questions: list[Question],
    ) -> QuestionPlanSlot | None:
        """Plan a coaching follow-up for a partial/weak answer, or None."""
        if dims.answer_status in {"irrelevant", "knowledge_gap", "nonsense"}:
            # These states are coaching moments, not follow-up moments.
            return None
        if _is_strong(dims):
            return None  # strong answers don't need a follow-up
        if self._followup_depth(question, questions) >= MAX_FOLLOWUP_DEPTH:
            return None
        if sum(1 for q in questions if q.follow_up_of is not None) >= MAX_FOLLOWUP_TOTAL:
            # A small number of coaching follow-ups keeps the interview focused;
            # depth and per-concept caps already bound the chains.
            return None
        if any(
            q.follow_up_of is not None and q.status == "pending"
            for q in questions
            if q.skill == question.skill and (q.concept or q.skill) == (question.concept or question.skill)
        ):
            return None  # a follow-up is already queued for this concept

        concept = question.concept or question.skill
        spec = concepts_for_skill(question.skill)
        concept_spec = next((s for s in spec if s.name == concept), None)

        # Target the most specific gap first.
        gap = self._pick_gap(dims, concept)
        new_type = self._next_type(question.question_type, concept_spec)
        difficulty = self._followup_difficulty(interview.current_difficulty, dims)

        intent = (
            f"deepen understanding of '{gap}' after a "
            f"{'partial' if dims.answer_status == 'partial' else 'weak'} answer on {concept}"
        )
        return QuestionPlanSlot(
            skill=question.skill,
            concept=concept,
            difficulty=difficulty,
            question_type=new_type,
            intent=intent,
            follow_up_of=question.id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slot_for(
        self,
        *,
        skill: str,
        spec: ConceptSpec | None,
        target_rank: int,
        round_index: int,
        type_offset: int,
    ) -> QuestionPlanSlot:
        if spec is None:
            concept = skill
            difficulty = RANK_DIFFICULTIES[target_rank]
            q_type = GENERIC_TYPE_CYCLE[type_offset % len(GENERIC_TYPE_CYCLE)]
        else:
            concept = spec.name
            concept_rank = DIFFICULTY_RANKS.get(spec.difficulty, target_rank)
            # Keep near the interview's target but respect concept difficulty.
            rank = min(2, max(0, concept_rank + (0 if round_index % 2 == 0 else -1 if target_rank < concept_rank else 1)))
            difficulty = RANK_DIFFICULTIES[rank]
            supported = spec.question_types or GENERIC_TYPE_CYCLE
            q_type = supported[type_offset % len(supported)]
        return QuestionPlanSlot(
            skill=skill,
            concept=concept,
            difficulty=difficulty,
            question_type=q_type,
            intent=INTENT_BY_TYPE.get(q_type, "explore the concept"),
        )

    @staticmethod
    def _next_type(current_type: str, spec: ConceptSpec | None) -> str:
        supported = (spec.question_types if spec and spec.question_types else GENERIC_TYPE_CYCLE)
        if current_type in supported:
            idx = supported.index(current_type)
            return supported[(idx + 1) % len(supported)]
        return supported[0]

    @staticmethod
    def _followup_difficulty(current: str, dims: EvaluationDimensions) -> str:
        # Keep it approachable: a weak answer gets the same or one step easier.
        rank = DIFFICULTY_RANKS.get(current, 1)
        if dims.correctness_score < 5 or dims.understanding_score < 5:
            rank = max(0, rank - 1)
        return RANK_DIFFICULTIES[rank]

    @staticmethod
    def _pick_gap(dims: EvaluationDimensions, concept: str) -> str:
        for req in dims.missing_requirements:
            if req.strip():
                return req.strip()
        for req in dims.partial_requirements:
            if req.strip():
                return req.strip()
        return concept

    @staticmethod
    def _followup_depth(question: Question, questions: list[Question]) -> int:
        depth = 0
        node = question
        while node is not None:
            depth += 1
            node = next((q for q in questions if q.id == node.follow_up_of), None)
        return depth


def _is_strong(dims: EvaluationDimensions) -> bool:
    """A strong answer needs no follow-up: correct, complete and on topic."""
    return (
        dims.answer_status in {"on_topic", "partial"}
        and dims.correctness_score >= 7
        and dims.completeness_score >= 7
        and not dims.missing_requirements
    )

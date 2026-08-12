"""Interview practice profile.

Tracks, per (skill, concept), how the candidate performed across answered
questions: ``strong``, ``needs_refinement`` or ``weak``. This is an interview
*practice* profile, not a verdict on real-world ability. It is computed
deterministically from stored evaluations (no new tables, fully auditable) and
drives the question planner's topic selection.
"""

from dataclasses import dataclass, field

from app.models.question import Question

WEAK_BELOW = 5.0
REFINEMENT_BELOW = 7.5


@dataclass
class ConceptRecord:
    skill: str
    concept: str
    score: float = 0.0
    count: int = 0
    latest_status: str = "pending"

    @property
    def status(self) -> str:
        if self.count == 0:
            return "unseen"
        if self.score >= REFINEMENT_BELOW:
            return "strong"
        if self.score >= WEAK_BELOW:
            return "needs_refinement"
        return "weak"

    def update(self, score: float, answer_status: str) -> None:
        total = self.score * self.count + score
        self.count += 1
        self.score = round(total / self.count, 2)
        self.latest_status = answer_status


@dataclass
class LearningProfile:
    concepts: dict[tuple[str, str], ConceptRecord] = field(default_factory=dict)

    def concept_key(self, skill: str, concept: str | None) -> str:
        return concept or skill

    def record(self, skill: str, concept: str | None, score: float, answer_status: str) -> None:
        key = self.concept_key(skill, concept)
        rec = self.concepts.setdefault((skill, key), ConceptRecord(skill=skill, concept=key))
        rec.update(score, answer_status)

    def status_for(self, skill: str, concept: str | None) -> str:
        rec = self.concepts.get((skill, self.concept_key(skill, concept)))
        return rec.status if rec else "unseen"

    def score_for(self, skill: str, concept: str | None) -> float | None:
        rec = self.concepts.get((skill, self.concept_key(skill, concept)))
        return rec.score if rec else None

    @property
    def covered(self) -> list[tuple[str, str]]:
        return sorted((s, c) for (s, c), _ in self.concepts.items())

    def weak_ordered(self) -> list[tuple[str, str, float]]:
        """(skill, concept, avg score) sorted weakest first."""
        items = [
            (s, c, rec.score)
            for (s, c), rec in self.concepts.items()
            if rec.status in {"weak", "needs_refinement"}
        ]
        return sorted(items, key=lambda item: item[2])


class LearningProfileService:
    """Build a :class:`LearningProfile` from an interview's questions."""

    def build(self, questions: list[Question]) -> LearningProfile:
        profile = LearningProfile()
        for q in questions:
            if q.answer is None or q.answer.evaluation is None:
                continue
            ev = q.answer.evaluation
            profile.record(
                skill=q.skill,
                concept=q.concept,
                score=ev.score,
                answer_status=ev.answer_status,
            )
        return profile

"""Validation of generated questions + guaranteed-valid fallback seeds.

The LLM is never trusted blindly: every question must be coherent, answerable,
target a known concept, and carry a non-empty rubric. If it fails validation it
is rejected (the caller may retry); the guaranteed fallback is a curated seed
question from the concept bank, so the interview never stalls on bad LLM output.
"""

import re

from app.services.ai.base import QuestionData, QuestionPlanSlot
from app.services.ai.concept_bank import (
    QUESTION_TYPE_TEMPLATES,
    ConceptSpec,
    concept_for,
)

# Question phrasing is answerable if it ends with a question mark or starts
# with an imperative / prompt word common to interview questions.
_ANSWERABLE_STARTS = (
    "what", "how", "why", "when", "where", "which", "who", "explain", "describe",
    "compare", "define", "write", "sketch", "design", "tell", "walk", "debug",
    "investigate", "outline", "discuss", "identify", "summarize", "give",
)
_ANSWERABLE_PATTERN = re.compile(
    r"\?$|^(?:" + "|".join(_ANSWERABLE_STARTS) + r")\b", re.IGNORECASE
)


class QuestionValidationResult:
    def __init__(self, question: QuestionData | None, reason: str = "") -> None:
        self.question = question
        self.reason = reason

    @property
    def valid(self) -> bool:
        return self.question is not None


class QuestionValidator:
    def __init__(self, similarity_threshold: float = 0.6) -> None:
        self.similarity_threshold = similarity_threshold

    def validate(
        self,
        qdata: QuestionData,
        *,
        previous_texts: list[str] | None = None,
        previous_concepts: list[str] | None = None,
    ) -> QuestionValidationResult:
        """Validate a generated question + rubric."""
        reason = self._failure_reason(qdata, previous_texts or [], previous_concepts or [])
        if reason:
            return QuestionValidationResult(None, reason)
        return QuestionValidationResult(qdata)

    def _failure_reason(
        self,
        q: QuestionData,
        previous_texts: list[str],
        previous_concepts: list[str],
    ) -> str:
        text = q.question.strip()
        if len(text) < 10:
            return "question too short"
        if not _ANSWERABLE_PATTERN.search(text):
            return "question is not answerable (missing ? or directive verb)"
        if not q.core_requirements:
            return "rubric is empty (no core requirements)"
        if q.skill in concept_bank_keys() and not concept_for(q.skill, q.concept or ""):
            return f"concept '{q.concept}' is not in the bank for '{q.skill}'"
        prev_conc = {c.lower() for c in previous_concepts}
        if q.concept and q.concept.lower() in prev_conc and not q.follow_up_of:
            return f"concept '{q.concept}' was already asked"
        for prev in previous_texts:
            if self._overlap(text, prev) >= self.similarity_threshold:
                return "too similar to an existing question"
        return ""

    @staticmethod
    def _overlap(a: str, b: str) -> float:
        wa = set(re.findall(r"[a-z']+", a.lower()))
        wb = set(re.findall(r"[a-z']+", b.lower()))
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    # ------------------------------------------------------------------
    def build_from_slot(self, slot: QuestionPlanSlot) -> QuestionData:
        """Guaranteed-valid question + rubric from the concept bank.

        Used by the mock provider and as the LLM fallback, so the interview
        can never stall on malformed generation.
        """
        spec = concept_for(slot.skill, slot.concept)
        seed = self._seed_for(spec, slot)
        rubric = self._rubric_for(spec, slot.concept)
        return QuestionData(
            question=seed,
            skill=slot.skill,
            concept=slot.concept,
            intent=slot.intent,
            difficulty=slot.difficulty,
            question_type=slot.question_type,
            expected_concepts=[slot.skill] + rubric["core_requirements"][:3],
            core_requirements=rubric["core_requirements"],
            optional_depth_points=rubric["optional_depth"],
            common_misconceptions=rubric["misconceptions"],
        )

    @staticmethod
    def _seed_for(spec: ConceptSpec | None, slot: QuestionPlanSlot) -> str:
        if spec and slot.question_type in spec.seeds:
            template = spec.seeds[slot.question_type]
        else:
            template = QUESTION_TYPE_TEMPLATES.get(
                slot.question_type, QUESTION_TYPE_TEMPLATES["explanation"]
            )
        return template.format(concept=slot.concept, skill=slot.skill)

    @staticmethod
    def _rubric_for(spec: ConceptSpec | None, concept: str) -> dict:
        if spec is None:
            return {
                "core_requirements": [f"Explain what {concept} is"],
                "optional_depth": ["Give a concrete example"],
                "misconceptions": [],
            }
        core = list(spec.key_points[:4]) or [f"Explain what {concept} is"]
        depth = list(spec.key_points[4:8]) or [
            "Give a concrete example",
            "Mention when not to use it",
        ]
        return {
            "core_requirements": core,
            "optional_depth": depth,
            "misconceptions": list(spec.misconceptions),
        }


def concept_bank_keys() -> set[str]:
    from app.services.ai.concept_bank import CONCEPT_BANK

    return set(CONCEPT_BANK.keys())

"""Candidate-facing feedback, built from structured evaluation dimensions.

Feedback is more important than the score: the candidate should leave knowing
exactly what they demonstrated, what is missing, what is incorrect, and what to
study next. No generic "good answer, could improve" without evidence.
"""

from app.services.ai.base import EvaluationDimensions

STATUS_LABELS: dict[str, str] = {
    "on_topic": "On topic",
    "partial": "Partially answered",
    "incorrect": "Incorrect",
    "irrelevant": "Off topic",
    "knowledge_gap": "Knowledge gap",
    "contradictory": "Contradictory reasoning",
    "nonsense": "Did not demonstrate understanding",
}

# Phrase used for concepts the candidate should go study.
REFINE_LEAD = "Refine these topics"


class FeedbackService:
    def build(
        self,
        dims: EvaluationDimensions,
        *,
        skill: str,
        concept: str | None,
        question_type: str,
    ) -> dict:
        """Return ``{feedback, strengths, weaknesses}`` for the candidate."""
        status = dims.answer_status
        concept_name = concept or skill

        strengths: list[str] = []
        weaknesses: list[str] = []
        parts: list[str] = []

        # --- What was demonstrated -----------------------------------------
        if dims.satisfied_requirements:
            strengths.append(
                "What you demonstrated: " + self._list_joined(dims.satisfied_requirements)
            )
        strengths.extend(dims.strengths)
        if status == "on_topic" and not dims.missing_requirements and not dims.satisfied_requirements:
            strengths.append("You directly answered the question.")
        if dims.missing_requirements and not dims.satisfied_requirements:
            strengths.append("You attempted the question and covered the basics.")

        # --- What is incorrect ---------------------------------------------
        if dims.technical_errors or dims.misconceptions:
            mistakes = list(dims.misconceptions) + list(dims.technical_errors)
            weaknesses.append("✗ Technical corrections: " + self._list_joined(mistakes))
            parts.append(self._correction_sentence(concept_name, mistakes))

        # --- Contradictions ------------------------------------------------
        if dims.contradictions:
            weaknesses.append(
                "Your reasoning contradicts itself: " + self._list_joined(dims.contradictions)
            )
            parts.append("Your answer contains contradictory reasoning that you should reconcile.")

        # --- Status-specific coaching --------------------------------------
        if status == "irrelevant":
            weaknesses.append(
                "Your answer does not address the question about " f"{concept_name}. "
                "The information you provided may be technically correct, but it does not "
                "answer the question that was asked."
            )
            parts.append(
                "That answer is about something else — it doesn't respond to the question "
                f"about {concept_name}. Re-read the question and answer it directly."
            )
        elif status == "knowledge_gap":
            weaknesses.append(
                f"You haven't demonstrated the concept '{concept_name}' yet. "
                "That's fine — interviews are also about finding what to study."
            )
            parts.append(
                f"You said you don't know '{concept_name}' — no problem. "
                "A short, honest answer like that is a clear signal of where to focus."
            )
        elif status == "nonsense":
            weaknesses.append(
                "The answer lists related terms but does not explain them. "
                "Listing keywords is not the same as demonstrating understanding."
            )
            parts.append(
                "The answer strings keywords together without explaining how they relate. "
                "A useful answer explains the 'what' and the 'why' in plain sentences."
            )
        elif status == "incorrect":
            weaknesses.append(
                "The core claim is not correct. Explain the mechanism instead of asserting it."
            )
            if not parts:
                parts.append(
                    "One of your statements is technically wrong. "
                    "Review the fundamentals of this concept and correct the claim."
                )
        elif status == "contradictory" and not parts:
            parts.append("Your answer makes statements that contradict each other.")

        # --- What is missing / partial -------------------------------------
        if dims.partial_requirements:
            weaknesses.append(
                "Only partially covered: " + self._list_joined(dims.partial_requirements)
            )
            parts.append(
                "Some parts of your answer were only sketched: "
                + self._list_joined(dims.partial_requirements)
                + "."
            )
        if dims.missing_requirements:
            weaknesses.append(
                "Did not cover: " + self._list_joined(dims.missing_requirements)
            )
            parts.append(
                "You left out: " + self._list_joined(dims.missing_requirements) + "."
            )

        if status in {"partial", "on_topic"} and not parts and dims.completeness_score < 6:
            parts.append("Your answer is on the right track but could be more complete.")

        # --- Refine topics --------------------------------------------------
        topics = dims.recommended_topics or self._topics_from_missing(dims, concept_name)
        if topics:
            weaknesses.append(REFINE_LEAD + ": " + self._list_joined(topics))
            parts.append(
                "Refine these topics: " + self._list_joined(topics) + "."
            )

        if not strengths:
            strengths.append("Attempted the question.")
        if not parts:
            parts.append("Solid, on-topic coverage. Keep this level of precision.")

        feedback = " ".join(parts)
        return {"feedback": feedback, "strengths": strengths, "weaknesses": weaknesses}

    # ------------------------------------------------------------------
    @staticmethod
    def _list_joined(items: list[str]) -> str:
        return ", ".join(str(i).strip() for i in items if str(i).strip())

    @staticmethod
    def _topics_from_missing(dims: EvaluationDimensions, concept_name: str) -> list[str]:
        """If no explicit topics came back, derive study targets from gaps."""
        topics = list(dims.missing_requirements)
        if dims.answer_status in {"irrelevant", "knowledge_gap", "nonsense"}:
            topics = [concept_name] + topics
        return topics[:4]

    @staticmethod
    def _correction_sentence(concept_name: str, mistakes: list[str]) -> str:
        sample = " · ".join(str(m) for m in mistakes[:2])
        return (
            f"One of your statements about {concept_name} is not accurate: {sample}. "
            "Check the mechanism before moving on."
        )

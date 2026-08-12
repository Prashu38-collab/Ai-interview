"""Deterministic score engine.

The LLM never produces the final score. It returns structured dimensions; this
engine combines them with configurable weights and applies hard gates so that:

- fundamentally irrelevant answers stay low,
- technically incorrect / nonsense answers cannot be high,
- concise but fully correct answers get full credit.

The exact weighting is configurable via settings (``SCORE_WEIGHT_*`` and
``STATUS_SCORE_CAPS``), so evaluator behaviour can be tuned without code edits.
"""

from app.core.config import Settings, get_settings
from app.services.ai.base import EvaluationDimensions


class ScoreEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def score(self, dims: EvaluationDimensions) -> float:
        weights = self.settings.score_weights
        weighted = (
            dims.relevance_score * weights["relevance"]
            + dims.correctness_score * weights["correctness"]
            + dims.completeness_score * weights["completeness"]
            + dims.understanding_score * weights["understanding"]
            + dims.reasoning_score * weights["reasoning"]
        )

        # Hard gates: the answer's fundamental state bounds its score.
        cap = self.settings.status_caps.get(dims.answer_status, 10.0)
        score = min(weighted, cap)

        # Extra safeguards independent of status: gibberish and prompt-injection
        # attempts never pass even if dimensions were optimistic.
        if dims.relevance_score < 2.0:
            score = min(score, 2.5)
        if dims.correctness_score < 2.0:
            score = min(score, 4.0)

        return round(min(10.0, max(0.0, score)), 1)

    @staticmethod
    def grade(score: float) -> str:
        if score >= 8.5:
            return "strong"
        if score >= 7.0:
            return "good"
        if score >= 5.0:
            return "developing"
        if score >= 3.0:
            return "weak"
        return "needs_work"

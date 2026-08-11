"""Real (LLM-backed) implementation of :class:`AIService`.

Flow for every task: build messages (PromptService) -> send (LLMService) ->
parse JSON -> validate with Pydantic. Any provider or validation failure
surfaces as ``AIProviderError`` / ``AIResponseError`` for the caller to handle.
"""

import logging

from pydantic import ValidationError

from app.services.ai.base import (
    AIService,
    AnswerEvaluation,
    CandidateAnalysis,
    GeneratedQuestions,
    ReportSummary,
)
from app.services.ai.llm_service import (
    AIProviderError,
    AIResponseError,
    LLMService,
)
from app.services.ai.prompt_service import PromptService

logger = logging.getLogger(__name__)


class LLMAIService(AIService):
    """Production implementation backed by an OpenAI-compatible API."""

    name = "llm"

    def __init__(
        self,
        llm: LLMService | None = None,
        prompts: PromptService | None = None,
    ) -> None:
        self.llm = llm or LLMService()
        self.prompts = prompts or PromptService()

    def analyze_candidate(
        self,
        *,
        target_role: str,
        experience_level: str,
        job_description: str,
        resume_text: str,
    ) -> CandidateAnalysis:
        messages = self.prompts.candidate_analysis(
            target_role=target_role,
            experience_level=experience_level,
            job_description=job_description,
            resume_text=resume_text,
        )
        return self._call(
            messages, lambda data: CandidateAnalysis.model_validate(data), "candidate analysis"
        )

    def generate_questions(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis: CandidateAnalysis,
        number: int,
        difficulty: str,
        previous_questions: list[str],
    ) -> list:
        messages = self.prompts.questions(
            target_role=target_role,
            experience_level=experience_level,
            difficulty=difficulty,
            analysis_json=analysis.model_dump_json(),
            number=number,
            previous_questions=previous_questions,
        )

        def parse(data: dict) -> list:
            return GeneratedQuestions.model_validate(data).questions

        return self._call(messages, parse, "question generation")

    def evaluate_answer(
        self,
        *,
        question_text: str,
        skill: str,
        difficulty: str,
        question_type: str,
        expected_concepts: list[str],
        answer_text: str,
    ) -> AnswerEvaluation:
        messages = self.prompts.answer_evaluation(
            question_text=question_text,
            skill=skill,
            difficulty=difficulty,
            question_type=question_type,
            expected_concepts=expected_concepts,
            answer_text=answer_text,
        )
        return self._call(
            messages, lambda data: AnswerEvaluation.model_validate(data), "answer evaluation"
        )

    def generate_report(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis: CandidateAnalysis,
        skill_scores: list[dict],
        evaluations: list[dict],
    ) -> ReportSummary:
        overall = round(sum(e["score"] for e in evaluations) / len(evaluations), 2) if evaluations else 0.0
        messages = self.prompts.report(
            target_role=target_role,
            experience_level=experience_level,
            analysis_json=analysis.model_dump_json(),
            skill_scores_json=str(skill_scores),
            overall_score=overall,
        )
        return self._call(
            messages, lambda data: ReportSummary.model_validate(data), "report generation"
        )

    # ------------------------------------------------------------------
    def _call(self, messages: list[dict], parse, task: str):
        try:
            raw = self.llm.chat_json(messages)
        except (AIProviderError, AIResponseError) as exc:
            logger.error("LLM task '%s' failed: %s", task, exc)
            raise AIProviderError(f"AI task '{task}' failed: {exc}") from exc
        try:
            return parse(raw)
        except ValidationError as exc:
            logger.error("LLM task '%s' returned invalid data: %s", task, exc)
            raise AIResponseError(f"AI task '{task}' returned invalid data: {exc}") from exc

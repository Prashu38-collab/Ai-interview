"""Real (LLM-backed) implementation of :class:`AIService`.

Flow for every task: build messages (PromptService) -> send (LLMService) ->
parse JSON -> validate with Pydantic. Any provider or validation failure
surfaces as ``AIProviderError`` / ``AIResponseError`` for the caller to handle.
"""

import logging

from pydantic import ValidationError

from app.services.ai.base import (
    AIService,
    CandidateAnalysis,
    EvaluationDimensions,
    GeneratedQuestions,
    QuestionPlanSlot,
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
        previous_concepts: list[str],
        plan: list[QuestionPlanSlot] | None = None,
    ) -> list:
        slots = plan or []
        plan_lines = "\n".join(
            f"- slot {i + 1}: skill={s.skill}, concept={s.concept}, "
            f"difficulty={s.difficulty}, type={s.question_type}"
            for i, s in enumerate(slots)
        ) or "none"
        messages = self.prompts.questions(
            target_role=target_role,
            experience_level=experience_level,
            difficulty=difficulty,
            analysis_json=analysis.model_dump_json(),
            number=number,
            previous_questions=previous_questions,
            previous_concepts=previous_concepts,
            plan=plan_lines,
        )

        def parse(data: dict) -> list:
            return GeneratedQuestions.model_validate(data).questions

        return self._call(messages, parse, "question generation")

    def evaluate_answer(
        self,
        *,
        question_text: str,
        skill: str,
        concept: str | None,
        difficulty: str,
        question_type: str,
        intent: str | None,
        expected_concepts: list[str],
        core_requirements: list[str],
        optional_depth_points: list[str],
        common_misconceptions: list[str],
        answer_text: str,
    ) -> EvaluationDimensions:
        messages = self.prompts.answer_evaluation(
            question_text=question_text,
            skill=skill,
            concept=concept or skill,
            difficulty=difficulty,
            question_type=question_type,
            intent=intent or "",
            expected_concepts=expected_concepts,
            core_requirements=core_requirements,
            optional_depth_points=optional_depth_points,
            common_misconceptions=common_misconceptions,
            answer_text=answer_text,
        )
        return self._call(
            messages,
            lambda data: EvaluationDimensions.model_validate(data),
            "answer evaluation",
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

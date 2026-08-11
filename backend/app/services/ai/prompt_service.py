"""Builds the messages sent to the LLM from the prompt templates."""

from app.prompts import interview_prompts


class PromptService:
    """Thin wrapper around the prompt templates, so the AI service never
    builds strings itself. Makes prompts easy to test and swap."""

    def candidate_analysis(
        self, *, target_role: str, experience_level: str, job_description: str, resume_text: str
    ) -> list[dict]:
        system, user = interview_prompts.candidate_analysis_prompt(
            target_role, experience_level, job_description, resume_text
        )
        return self._messages(system, user)

    def questions(
        self,
        *,
        target_role: str,
        experience_level: str,
        difficulty: str,
        analysis_json: str,
        number: int,
        previous_questions: list[str],
    ) -> list[dict]:
        system, user = interview_prompts.question_generation_prompt(
            target_role, experience_level, difficulty, analysis_json, number, previous_questions
        )
        return self._messages(system, user)

    def answer_evaluation(
        self,
        *,
        question_text: str,
        skill: str,
        difficulty: str,
        question_type: str,
        expected_concepts: list[str],
        answer_text: str,
    ) -> list[dict]:
        system, user = interview_prompts.answer_evaluation_prompt(
            question_text, skill, difficulty, question_type, expected_concepts, answer_text
        )
        return self._messages(system, user)

    def report(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis_json: str,
        skill_scores_json: str,
        overall_score: float,
    ) -> list[dict]:
        system, user = interview_prompts.report_generation_prompt(
            target_role, experience_level, analysis_json, skill_scores_json, overall_score
        )
        return self._messages(system, user)

    @staticmethod
    def _messages(system: str, user: str) -> list[dict]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

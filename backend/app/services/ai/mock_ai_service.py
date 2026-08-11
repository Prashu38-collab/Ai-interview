"""Deterministic, offline implementation of :class:`AIService`.

Purpose:
- Lets the whole app run and be demoed without any API key
  (set ``LLM_PROVIDER=mock``, which is the default).
- Makes automated tests fast and reliable: no network, no flakiness.

It intentionally uses simple heuristics (skill keyword scanning, question
templates, concept matching) rather than pretending to be a real LLM. Swap
``LLM_PROVIDER`` to ``openai`` (or any OpenAI-compatible endpoint) in
production.
"""

from app.services.ai.base import (
    AIService,
    AnswerEvaluation,
    CandidateAnalysis,
    QuestionData,
    ReportSummary,
)

# skill -> substrings that indicate the skill appears in a text (case-insensitive)
SKILL_KEYWORDS: dict[str, list[str]] = {
    "Python": ["python", "django", "flask", "fastapi", "pandas", "asyncio", "pytest"],
    "FastAPI": ["fastapi", "pydantic"],
    "PostgreSQL": ["postgres", "postgresql", "sql", "database", "alembic"],
    "Docker": ["docker", "container"],
    "REST APIs": ["rest", "api", "endpoint", "http"],
    "React": ["react", "javascript", "frontend"],
    "Testing": ["test", "pytest", "unittest", "jest"],
    "Git": ["git", "github"],
    "AWS": ["aws", "s3", "ec2", "lambda", "cloud"],
}

# Generic question templates by (difficulty, type). The mock fills in the skill.
QUESTION_TEMPLATES: dict[tuple[str, str], str] = {
    ("easy", "conceptual"): "Explain what {skill} is and give a simple example of where it is used.",
    ("easy", "behavioral"): "Describe a project where you used {skill} and what you learned.",
    ("medium", "conceptual"): "Explain how {skill} works under the hood and describe a real-world scenario where it is a good fit.",
    ("medium", "coding"): "Sketch the key pieces of a small program that uses {skill} to solve a practical problem.",
    ("medium", "scenario"): "You are debugging a production issue related to {skill}. Walk through your approach.",
    ("hard", "conceptual"): "Compare {skill} with its closest alternative and discuss the trade-offs in a production system.",
    ("hard", "scenario"): "Design a solution using {skill} for a high-scale system. Discuss bottlenecks and mitigations.",
    ("hard", "behavioral"): "Tell me about the most challenging problem you solved using {skill} and how you approached it.",
}


def _scan_skills(text: str) -> list[str]:
    lower = text.lower()
    return [skill for skill, keywords in SKILL_KEYWORDS.items() if any(k in lower for k in keywords)]


class MockAIService(AIService):
    name = "mock"

    def analyze_candidate(
        self,
        *,
        target_role: str,
        experience_level: str,
        job_description: str,
        resume_text: str,
    ) -> CandidateAnalysis:
        candidate_skills = _scan_skills(resume_text)
        required_skills = _scan_skills(job_description) or _scan_skills(target_role)
        skill_gaps = [s for s in required_skills if s not in candidate_skills]
        topics = (required_skills + [s for s in candidate_skills if s not in required_skills])[:6]
        return CandidateAnalysis(
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            skill_gaps=skill_gaps,
            topics=topics or ["Core Programming", "Problem Solving"],
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
    ) -> list[QuestionData]:
        skills = analysis.topics or analysis.required_skills or ["Core Programming"]
        difficulty_ranks = {"easy": 0, "medium": 1, "hard": 2}
        target = difficulty_ranks.get(difficulty, 1)
        type_cycle = ["conceptual", "scenario", "conceptual", "behavioral", "coding"]

        questions: list[QuestionData] = []
        seen: set[str] = set(previous_questions)
        i = 0
        while len(questions) < number and i < number * 4:
            skill = skills[i % len(skills)]
            q_type = type_cycle[i % len(type_cycle)]
            # Rotate difficulty around the target, staying inside [easy..hard].
            rank = max(0, min(2, target + (i // len(skills)) % 2 - (i // len(skills)) % 2))
            diff = ["easy", "medium", "hard"][rank]
            template = QUESTION_TEMPLATES.get((diff, q_type)) or QUESTION_TEMPLATES[("medium", "conceptual")]
            text = template.format(skill=skill)
            if text not in seen:
                seen.add(text)
                concepts = [skill, "best practices"]
                if diff == "hard":
                    concepts.append("trade-offs")
                questions.append(
                    QuestionData(
                        question=text,
                        skill=skill,
                        difficulty=diff,
                        question_type=q_type,
                        expected_concepts=concepts,
                    )
                )
            i += 1
        return questions[:number]

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
        answer_lower = answer_text.lower()
        word_count = len(answer_text.split())

        covered = [c for c in expected_concepts if c.lower() in answer_lower]
        missing = [c for c in expected_concepts if c not in covered]

        coverage = len(covered) / len(expected_concepts) if expected_concepts else 0.5
        length_score = min(word_count / 60.0, 1.0)
        score = round(min(10.0, coverage * 6.5 + length_score * 3.5), 1)

        strengths = []
        if covered:
            strengths.append(f"Mentioned key concepts: {', '.join(covered)}.")
        if word_count >= 40:
            strengths.append("Provided a reasonably detailed answer.")
        else:
            strengths.append("Answer is concise.")
        if not strengths:
            strengths = ["Attempted the question."]

        weaknesses = []
        if missing:
            weaknesses.append(f"Did not mention: {', '.join(missing)}.")
        if word_count < 25:
            weaknesses.append("Answer was quite short; more depth was expected.")

        feedback = (
            f"You covered {len(covered)} of {len(expected_concepts)} expected concepts "
            f"in a {word_count}-word answer. "
            + ("Keep expanding on real-world trade-offs." if missing else "Solid coverage.")
        )
        return AnswerEvaluation(
            score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            feedback=feedback,
            missing_concepts=missing,
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
        if not evaluations:
            return ReportSummary(
                summary="The interview had no evaluated answers.",
                strengths=[],
                weaknesses=[],
                recommendations=["Answer all questions to receive a full report."],
            )
        best = max(skill_scores, key=lambda s: s["score"]) if skill_scores else None
        worst = min(skill_scores, key=lambda s: s["score"]) if skill_scores else None
        strengths = [f"Strongest area: {best['skill']} ({best['score']}/10)"] if best else []
        weaknesses = [f"Area to improve: {worst['skill']} ({worst['score']}/10)"] if worst else []
        recommendations = [f"Review materials on {w['skill']} and practice hands-on." for w in skill_scores if w["score"] < 7]
        if not recommendations:
            recommendations = ["Keep practicing with real projects to deepen your knowledge."]
        summary = (
            f"Completed the {target_role} ({experience_level}) interview. "
            f"Strong performance overall; focus on the highlighted weaker areas to grow."
        )
        return ReportSummary(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )

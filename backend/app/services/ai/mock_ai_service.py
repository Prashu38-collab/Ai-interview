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

# Generic question templates by (difficulty, type). The mock fills in the
# skill. Several variants per slot give variety when the same (difficulty,
# type) repeats, so questions don't feel copy-pasted.
QUESTION_TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("easy", "conceptual"): [
        "Explain what {skill} is and give a simple example of where it is used.",
        "In your own words, what is {skill} and when would you reach for it?",
    ],
    ("easy", "behavioral"): [
        "Describe a project where you used {skill} and what you learned from it.",
        "Tell me about a time {skill} helped you solve a problem at work or school.",
    ],
    ("medium", "conceptual"): [
        "Explain how {skill} works under the hood and describe a real-world scenario where it is a good fit.",
        "Walk through the core ideas behind {skill} and what a team should understand before adopting it.",
    ],
    ("medium", "coding"): [
        "Sketch the key pieces of a small program that uses {skill} to solve a practical problem.",
        "Write pseudocode for a feature that relies on {skill}. What are the important decisions?",
    ],
    ("medium", "scenario"): [
        "You are debugging a production issue related to {skill}. Walk through your approach.",
        "A service built around {skill} is degrading in production. How do you investigate and fix it?",
    ],
    ("hard", "conceptual"): [
        "Compare {skill} with its closest alternative and discuss the trade-offs in a production system.",
        "What are the sharp edges of {skill} in a real system, and how do you mitigate them?",
    ],
    ("hard", "scenario"): [
        "Design a solution using {skill} for a high-scale system. Discuss bottlenecks and mitigations.",
        "Your team must scale a system that depends on {skill}. Present your architecture and its failure modes.",
    ],
    ("hard", "behavioral"): [
        "Tell me about the most challenging problem you solved using {skill} and how you approached it.",
        "Describe a disagreement about {skill} you had with a colleague and how you resolved it.",
    ],
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
        while len(questions) < number and i < number * 6:
            skill = skills[i % len(skills)]
            q_type = type_cycle[i % len(type_cycle)]
            # Alternate around the target difficulty (down -> same -> up) so a
            # batch mixes easy/medium/hard instead of all being the target.
            rank = max(0, min(2, target + (i // len(skills)) % 3 - 1))
            diff = ["easy", "medium", "hard"][rank]
            variants = QUESTION_TEMPLATES.get((diff, q_type)) or QUESTION_TEMPLATES[("medium", "conceptual")]
            template = variants[(i // len(skills)) % len(variants)]
            text = template.format(skill=skill)
            if text not in seen:
                seen.add(text)
                concepts = [skill]
                if diff in {"medium", "hard"}:
                    concepts.append("real-world usage")
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
        length_score = min(word_count / 80.0, 1.0)

        # Technical richness: distinct meaningful words the candidate used.
        # Real LLM answers score much higher; this keeps the offline demo fair.
        stopwords = {
            "this", "that", "with", "have", "from", "their", "they", "about",
            "which", "there", "when", "what", "where", "were", "been", "will",
            "into", "than", "then", "them", "over", "such", "these", "those",
            "used", "using", "thing", "stuff", "very", "just", "because",
        }
        terms = {
            w for w in answer_lower.replace(".", " ").replace(",", " ").split()
            if len(w) >= 4 and w not in stopwords
        }
        richness = min(len(terms) / 12.0, 1.0)

        score = round(min(10.0, 3.5 + coverage * 3.0 + length_score * 1.5 + richness * 2.0), 1)
        if word_count < 5:
            score = min(score, 2.0)

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

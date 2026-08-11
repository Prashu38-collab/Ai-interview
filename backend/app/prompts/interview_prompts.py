"""Prompt templates for each AI task.

Templates live here (separate from the services) so they can be tuned and
reviewed without touching code. Every prompt explicitly requests strict JSON
so the output can be validated with Pydantic.

Each template is a function returning a ``(system, user)`` message tuple.
"""

JSON_INSTRUCTION = (
    "Respond with STRICT JSON only. No markdown, no explanations, no trailing text. "
    "The JSON must match exactly this schema:"
)


def _truncate(text: str, limit: int = 4000) -> str:
    """Keep prompts bounded; LLMs degrade on very long inputs."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def candidate_analysis_prompt(
    target_role: str, experience_level: str, job_description: str, resume_text: str
) -> tuple[str, str]:
    system = (
        "You are an expert technical recruiter who analyzes resumes against job "
        "descriptions to plan technical interviews."
    )
    schema = """{
  "candidate_skills": ["skills present on the candidate's resume"],
  "required_skills": ["skills the role requires"],
  "skill_gaps": ["required skills missing or weak on the resume"],
  "topics": ["4-8 recommended interview topics derived from role + gaps"]
}"""
    user = (
        f"{JSON_INSTRUCTION}\n{schema}\n\n"
        f"Target role: {target_role}\n"
        f"Experience level: {experience_level}\n\n"
        f"JOB DESCRIPTION:\n{_truncate(job_description)}\n\n"
        f"RESUME:\n{_truncate(resume_text)}"
    )
    return system, user


def question_generation_prompt(
    target_role: str,
    experience_level: str,
    difficulty: str,
    analysis_json: str,
    number: int,
    previous_questions: list[str],
) -> tuple[str, str]:
    system = (
        "You are a senior technical interviewer who writes personalized, high-quality "
        "technical interview questions."
    )
    schema = """{
  "questions": [
    {
      "question": "the question text",
      "skill": "the skill this tests",
      "difficulty": "easy | medium | hard",
      "question_type": "conceptual | coding | scenario | behavioral",
      "expected_concepts": ["key concepts a great answer should mention"]
    }
  ]
}"""
    prev = "\n".join(f"- {q}" for q in previous_questions) or "none"
    user = (
        f"{JSON_INSTRUCTION}\n{schema}\n\n"
        f"Generate {number} interview questions for a candidate applying to "
        f"'{target_role}' at the '{experience_level}' level.\n"
        f"Difficulty target: {difficulty}.\n\n"
        f"RESUME/JOB ANALYSIS:\n{analysis_json}\n\n"
        f"PREVIOUSLY ASKED QUESTIONS (must not repeat these or their topics):\n{prev}"
    )
    return system, user


def answer_evaluation_prompt(
    question_text: str,
    skill: str,
    difficulty: str,
    question_type: str,
    expected_concepts: list[str],
    answer_text: str,
) -> tuple[str, str]:
    system = (
        "You are a fair and rigorous technical interviewer evaluating a candidate's "
        "written answer. Score based on correctness, completeness, technical depth, "
        "relevance and clarity. Be specific and constructive."
    )
    schema = """{
  "score": 8,
  "strengths": ["what the candidate did well"],
  "weaknesses": ["where the answer fell short"],
  "feedback": "a few sentences of constructive feedback",
  "missing_concepts": ["important concepts the answer omitted"]
}"""
    user = (
        f"{JSON_INSTRUCTION}\n{schema}\n\n"
        f"QUESTION: {question_text}\n"
        f"SKILL: {skill}\n"
        f"DIFFICULTY: {difficulty}\n"
        f"TYPE: {question_type}\n"
        f"EXPECTED CONCEPTS: {', '.join(expected_concepts)}\n\n"
        f"CANDIDATE ANSWER:\n{_truncate(answer_text)}\n\n"
        f"Score the answer 0-10."
    )
    return system, user


def report_generation_prompt(
    target_role: str,
    experience_level: str,
    analysis_json: str,
    skill_scores_json: str,
    overall_score: float,
) -> tuple[str, str]:
    system = (
        "You are a senior technical interviewer writing a final interview report "
        "for a candidate. Be constructive and specific."
    )
    schema = """{
  "summary": "2-4 sentence overall summary of the interview",
  "strengths": ["top strengths demonstrated"],
  "weaknesses": ["top weaknesses observed"],
  "recommendations": ["3-6 concrete learning recommendations"]
}"""
    user = (
        f"{JSON_INSTRUCTION}\n{schema}\n\n"
        f"Role: {target_role} ({experience_level})\n"
        f"Overall score: {overall_score}/10\n\n"
        f"SKILL SCORES:\n{skill_scores_json}\n\n"
        f"RESUME/JOB ANALYSIS:\n{analysis_json}"
    )
    return system, user

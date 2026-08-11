"""AI abstraction: output models + the AIService interface.

Every LLM interaction in the app goes through ``AIService``. The concrete
implementation (real provider or mock) is selected in ``__init__.py`` based on
``settings.llm_provider``. This keeps the rest of the app decoupled from any
specific LLM vendor and makes testing trivial (the mock never calls the network).

All AI outputs are validated with Pydantic so malformed LLM responses are
caught early instead of silently corrupting the database.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Pydantic models for validated AI output
# ---------------------------------------------------------------------------
class CandidateAnalysis(BaseModel):
    """Structured result of resume + job description analysis."""

    candidate_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class QuestionData(BaseModel):
    """A single generated interview question."""

    question: str = Field(min_length=5)
    skill: str = Field(min_length=1)
    difficulty: str = "medium"
    question_type: str = "conceptual"
    expected_concepts: list[str] = Field(default_factory=list)

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium or hard")
        return v

    @field_validator("question_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"conceptual", "coding", "scenario", "behavioral"}:
            raise ValueError("question_type must be conceptual, coding, scenario or behavioral")
        return v


class GeneratedQuestions(BaseModel):
    """The LLM returns a list of questions under a ``questions`` key."""

    questions: list[QuestionData]


class AnswerEvaluation(BaseModel):
    """Structured evaluation of a single candidate answer."""

    score: float = Field(ge=0, le=10)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    feedback: str = ""
    missing_concepts: list[str] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(float(v), 2)


class ReportSummary(BaseModel):
    """Qualitative parts of the final report produced by the AI.

    Numeric scores (overall + skill-wise) are computed deterministically from
    the stored evaluations; only the qualitative narrative comes from the LLM.
    """

    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Service interface
# ---------------------------------------------------------------------------
class AIService(ABC):
    """Abstract contract every LLM-backed service must implement."""

    name: str = "abstract"

    @abstractmethod
    def analyze_candidate(
        self,
        *,
        target_role: str,
        experience_level: str,
        job_description: str,
        resume_text: str,
    ) -> CandidateAnalysis:
        """Analyze a resume against a job description for a target role."""

    @abstractmethod
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
        """Generate a set of unique, personalized interview questions."""

    @abstractmethod
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
        """Score a candidate answer from 0-10 with qualitative feedback."""

    @abstractmethod
    def generate_report(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis: CandidateAnalysis,
        skill_scores: list[dict],
        evaluations: list[dict],
    ) -> ReportSummary:
        """Produce the qualitative summary of the completed interview."""

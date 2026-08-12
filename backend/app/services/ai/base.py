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

from app.services.ai.concept_bank import QUESTION_TYPES, normalize_type


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
    """A single generated interview question plus its evaluation rubric.

    The rubric is generated *with* the question: it describes the concepts a
    strong answer demonstrates, optional depth, and common misconceptions —
    not an expected reference sentence.
    """

    question: str = Field(min_length=5)
    skill: str = Field(min_length=1)
    # Concept within the skill this question targets (e.g. "decorators").
    concept: str | None = None
    # What the question is probing (e.g. "check basic understanding").
    intent: str | None = None
    difficulty: str = "medium"
    question_type: str = "explanation"
    expected_concepts: list[str] = Field(default_factory=list)
    # Evaluation rubric (mandatory; validated by the QuestionValidator).
    core_requirements: list[str] = Field(default_factory=list)
    optional_depth_points: list[str] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)

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
        v = normalize_type(v)
        if v not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of: {', '.join(QUESTION_TYPES)}")
        return v

    @field_validator("concept")
    @classmethod
    def clean_concept(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        return v or None


class GeneratedQuestions(BaseModel):
    """The LLM returns a list of questions under a ``questions`` key."""

    questions: list[QuestionData]


class QuestionPlanSlot(BaseModel):
    """A slot the planner wants filled: which concept, how, and why.

    The generator receives these and produces a validated question + rubric
    for each. ``follow_up_of`` is the DB id of the question this slot deepens.
    """

    skill: str
    concept: str
    difficulty: str = "medium"
    question_type: str = "explanation"
    intent: str = "explore the concept"
    follow_up_of: int | None = None


# The possible statuses of an evaluated answer. "knowledge_gap" covers
# "I don't know"; "nonsense" covers keyword stuffing and word salads;
# "echo" covers answers that just repeat the question back.
ANSWER_STATUSES: tuple[str, ...] = (
    "on_topic",
    "partial",
    "incorrect",
    "irrelevant",
    "knowledge_gap",
    "contradictory",
    "nonsense",
    "echo",
)


class EvaluationDimensions(BaseModel):
    """Structured evaluation of an answer — the AI's analysis, not a score.

    The final 0-10 score is computed deterministically by the app's score
    engine from these dimensions and its gates. The AI must never produce the
    final score itself.
    """

    answer_status: str = "on_topic"
    relevance_score: float = Field(default=0, ge=0, le=10)
    understanding_score: float = Field(default=0, ge=0, le=10)
    correctness_score: float = Field(default=0, ge=0, le=10)
    completeness_score: float = Field(default=0, ge=0, le=10)
    reasoning_score: float = Field(default=0, ge=0, le=10)
    satisfied_requirements: list[str] = Field(default_factory=list)
    partial_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    technical_errors: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    follow_up_question: str = ""
    follow_up_concept: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)

    @field_validator("answer_status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ANSWER_STATUSES:
            raise ValueError(f"answer_status must be one of: {', '.join(ANSWER_STATUSES)}")
        return v

    @field_validator("relevance_score", "understanding_score", "correctness_score",
                     "completeness_score", "reasoning_score")
    @classmethod
    def round_dimension(cls, v: float) -> float:
        return round(float(v), 2)


class AnswerEvaluation(BaseModel):
    """The final, persisted evaluation of a single answer.

    This is the app-level result assembled by ``EvaluationService`` from the
    AI's :class:`EvaluationDimensions` plus the score engine's score and the
    feedback service's candidate-facing feedback.
    """

    score: float = Field(ge=0, le=10)
    answer_status: str = "on_topic"
    relevance_score: float = 0
    understanding_score: float = 0
    correctness_score: float = 0
    completeness_score: float = 0
    reasoning_score: float = 0
    satisfied_requirements: list[str] = Field(default_factory=list)
    partial_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    technical_errors: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    follow_up_question: str = ""
    follow_up_concept: str = ""
    confidence: float = 0.5
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    feedback: str = ""
    missing_concepts: list[str] = Field(default_factory=list)
    evaluator_version: str = ""
    prompt_version: str = ""
    model_version: str = ""

    @field_validator("score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(float(v), 2)

    @field_validator("answer_status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ANSWER_STATUSES:
            raise ValueError(f"answer_status must be one of: {', '.join(ANSWER_STATUSES)}")
        return v


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
        previous_concepts: list[str],
        plan: list[QuestionPlanSlot] | None = None,
    ) -> list[QuestionData]:
        """Generate unique, personalized questions with evaluation rubrics.

        ``plan`` (when provided) pins skill/concept/difficulty/type per slot;
        without it the service picks its own sensible distribution.
        """

    @abstractmethod
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
        """Analyze a candidate answer into structured evaluation dimensions.

        The AI returns dimensions only; the final score is computed by the app.
        """

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

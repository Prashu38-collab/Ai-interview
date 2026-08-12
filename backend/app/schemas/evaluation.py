from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    answer_id: int
    score: float
    answer_status: str = "strong"
    relevance_score: float = 0
    understanding_score: float = 0
    correctness_score: float = 0
    completeness_score: float = 0
    reasoning_score: float = 0
    satisfied_requirements: list[str] = Field(default_factory=list)
    partial_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    mentioned_concepts: list[str] | None = Field(default_factory=list)
    demonstrated_concepts: list[str] | None = Field(default_factory=list)
    technical_errors: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    follow_up_question: str = ""
    follow_up_concept: str = ""
    confidence: float = 0.5
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    missing_concepts: list[str]
    created_at: datetime

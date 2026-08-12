from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    text: str
    skill: str
    concept: str | None = None
    intent: str | None = None
    difficulty: str
    question_type: str
    expected_concepts: list[str]
    core_requirements: list[str] = Field(default_factory=list)
    optional_depth_points: list[str] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    follow_up_of: int | None = None
    order_index: int
    status: str
    created_at: datetime


class GenerateQuestionsRequest(BaseModel):
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    # When true, unanswered questions are replaced with a fresh set instead of
    # the previous ones being reused/ignored.
    replace_pending: bool = False


class GenerateQuestionsResponse(BaseModel):
    generated: int
    questions: list[QuestionOut]

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    text: str
    skill: str
    difficulty: str
    question_type: str
    expected_concepts: list[str]
    order_index: int
    status: str
    created_at: datetime


class GenerateQuestionsRequest(BaseModel):
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GenerateQuestionsResponse(BaseModel):
    generated: int
    questions: list[QuestionOut]

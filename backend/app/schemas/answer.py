from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.evaluation import EvaluationOut


class AnswerCreate(BaseModel):
    text: str = Field(min_length=1, max_length=8000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Answer must not be empty.")
        return v


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    text: str
    duplicate_of: int | None = None
    created_at: datetime
    evaluation: EvaluationOut | None = None


class AnswerSubmissionResponse(BaseModel):
    question_id: int
    evaluation: EvaluationOut
    next_difficulty: str | None = None
    duplicate_of: int | None = None
    duplicate_warning: str | None = None

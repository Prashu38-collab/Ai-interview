from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InterviewCreate(BaseModel):
    target_role: str = Field(min_length=2, max_length=255)
    experience_level: str = Field(min_length=1, max_length=50)
    job_description: str = Field(min_length=10)
    resume_text: str = Field(min_length=10)
    number_of_questions: int = Field(default=5, ge=1, le=20)
    duration_minutes: int | None = Field(default=None, ge=5, le=240)


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_role: str
    experience_level: str
    number_of_questions: int
    duration_minutes: int | None
    status: str
    analysis: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class InterviewListItem(BaseModel):
    id: int
    target_role: str
    experience_level: str
    status: str
    created_at: datetime
    question_count: int = 0
    answered_count: int = 0
    report_overall_score: float | None = None


class CandidateAnalysisOut(BaseModel):
    candidate_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)

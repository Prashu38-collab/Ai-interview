from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SkillScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: str
    score: float
    question_count: int


class InterviewReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    overall_score: float
    average_score: float
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    skill_scores: list[SkillScoreOut]
    created_at: datetime

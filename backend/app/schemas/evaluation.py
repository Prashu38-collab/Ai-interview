from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    answer_id: int
    score: float
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    missing_concepts: list[str]
    created_at: datetime

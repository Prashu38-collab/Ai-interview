from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.answer import Answer


class Evaluation(TimestampMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("answer_id", name="uq_evaluation_answer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), nullable=False
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    # Structured evaluation dimensions (computed by the app's score engine
    # from the AI's analysis, never a single number straight from the LLM).
    answer_status: Mapped[str] = mapped_column(String(30), default="strong", nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    understanding_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    correctness_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    reasoning_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    satisfied_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    partial_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    mentioned_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    demonstrated_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    technical_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    misconceptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    contradictions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recommended_topics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    follow_up_question: Mapped[str] = mapped_column(Text, default="", nullable=False)
    follow_up_concept: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    evaluation_latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    missing_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)

    answer: Mapped["Answer"] = relationship(back_populates="evaluation")

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} score={self.score}>"

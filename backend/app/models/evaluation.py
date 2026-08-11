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
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    missing_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)

    answer: Mapped["Answer"] = relationship(back_populates="evaluation")

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} score={self.score}>"

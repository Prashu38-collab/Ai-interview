from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.interview import Interview


class Question(TimestampMixin, Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True, nullable=False
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    # The concept this question targets (e.g. "decorators" under Python).
    concept: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # What the question wants to probe (e.g. "verify understanding of X").
    intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(20), default="conceptual", nullable=False
    )
    expected_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Evaluation rubric, generated alongside the question.
    core_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    optional_depth_points: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    common_misconceptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Set when this question is a coaching follow-up of another question.
    follow_up_of: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # pending | answered
    status: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} skill={self.skill} difficulty={self.difficulty}>"

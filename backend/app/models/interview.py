from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.question import Question
    from app.models.report import InterviewReport
    from app.models.user import User


class Interview(TimestampMixin, Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    number_of_questions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Adaptive difficulty: the target difficulty for the next question,
    # updated after each evaluation. easy | medium | hard
    current_difficulty: Mapped[str] = mapped_column(
        String(10), default="medium", nullable=False
    )

    # JSON analysis result from the AI (skills, gaps, topics)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # created | analyzing | ready | in_progress | completed
    status: Mapped[str] = mapped_column(
        String(20), default="created", nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="interviews")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    report: Mapped["InterviewReport | None"] = relationship(
        back_populates="interview", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Interview id={self.id} role={self.target_role} status={self.status}>"

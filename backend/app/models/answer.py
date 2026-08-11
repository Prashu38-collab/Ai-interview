from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, TimestampMixin


class Answer(TimestampMixin, Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("question_id", name="uq_answer_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="answer")
    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="answer", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Answer id={self.id} question_id={self.question_id}>"

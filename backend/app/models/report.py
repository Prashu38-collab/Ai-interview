from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.interview import Interview


class InterviewReport(TimestampMixin, Base):
    __tablename__ = "interview_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    average_score: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="report")
    skill_scores: Mapped[list["SkillScore"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="SkillScore.skill"
    )

    def __repr__(self) -> str:
        return f"<InterviewReport id={self.id} overall={self.overall_score}>"


class SkillScore(TimestampMixin, Base):
    __tablename__ = "skill_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("interview_reports.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    report: Mapped["InterviewReport"] = relationship(back_populates="skill_scores")

    def __repr__(self) -> str:
        return f"<SkillScore skill={self.skill} score={self.score}>"

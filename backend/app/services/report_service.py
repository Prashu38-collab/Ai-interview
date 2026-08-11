"""Interview completion + final report.

Numeric scores are computed deterministically from stored evaluations (no AI),
so they are auditable and reproducible. The AI only writes the qualitative
summary, strengths, weaknesses and recommendations.
"""

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.question import Question
from app.models.report import InterviewReport, SkillScore
from app.services.ai.base import AIService, CandidateAnalysis


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def complete(self, interview: Interview, ai: AIService) -> InterviewReport:
        """Finalize an interview and (re)build its report."""
        evaluations = self._collect_evaluations(interview)
        if not evaluations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot complete an interview with no answered questions.",
            )

        skill_scores = self._compute_skill_scores(interview)
        overall = round(sum(e["score"] for e in evaluations) / len(evaluations), 2)
        average = round(overall, 2)

        analysis = (
            CandidateAnalysis.model_validate(interview.analysis)
            if interview.analysis
            else CandidateAnalysis()
        )
        summary_data = ai.generate_report(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            analysis=analysis,
            skill_scores=skill_scores,
            evaluations=evaluations,
        )

        # Regeneration: drop any previous report (skill scores cascade).
        if interview.report is not None:
            self.db.delete(interview.report)
            self.db.flush()

        report = InterviewReport(
            interview_id=interview.id,
            overall_score=overall,
            average_score=average,
            summary=summary_data.summary,
            strengths=summary_data.strengths,
            weaknesses=summary_data.weaknesses,
            recommendations=summary_data.recommendations,
        )
        self.db.add(report)
        self.db.flush()

        for skill in skill_scores:
            self.db.add(
                SkillScore(
                    report_id=report.id,
                    skill=skill["skill"],
                    score=skill["score"],
                    question_count=skill["question_count"],
                )
            )

        interview.status = "completed"
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_report(self, interview: Interview) -> InterviewReport:
        if interview.report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No report yet. Complete the interview first.",
            )
        return interview.report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_evaluations(self, interview: Interview) -> list[dict]:
        """Gather every answered question's evaluation as a flat dict."""
        out: list[dict] = []
        for question in interview.questions:
            if question.answer is not None and question.answer.evaluation is not None:
                ev = question.answer.evaluation
                out.append(
                    {
                        "skill": question.skill,
                        "difficulty": question.difficulty,
                        "question": question.text,
                        "score": ev.score,
                        "strengths": ev.strengths,
                        "weaknesses": ev.weaknesses,
                    }
                )
        return out

    def _compute_skill_scores(self, interview: Interview) -> list[dict]:
        """Average evaluation score per skill, with question counts."""
        sums: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for question in interview.questions:
            if question.answer is not None and question.answer.evaluation is not None:
                sums[question.skill] += question.answer.evaluation.score
                counts[question.skill] += 1
        return [
            {
                "skill": skill,
                "score": round(sums[skill] / counts[skill], 2),
                "question_count": counts[skill],
            }
            for skill in sorted(sums)
        ]

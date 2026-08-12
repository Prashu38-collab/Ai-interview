"""Pytest fixtures: in-memory SQLite DB, TestClient, and helpers.

Env vars must be set before any app module is imported (config is cached),
so this file sets them at the top before importing from ``app``.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789abcdef")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CORS_ORIGINS", "http://testserver")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.routers.deps import get_ai_service
from app.services.ai.base import (
    AIService,
    CandidateAnalysis,
    EvaluationDimensions,
    QuestionData,
    ReportSummary,
)


def evaluation_dims(score: float = 7.0, **overrides) -> EvaluationDimensions:
    """Build EvaluationDimensions that the score engine maps to ``score``.

    Equal dimension scores + ``on_topic`` status yield exactly ``score`` with
    the default (equal-ish) weights, keeping legacy tests predictable.
    """
    defaults = {
        "answer_status": "on_topic",
        "relevance_score": score,
        "understanding_score": score,
        "correctness_score": score,
        "completeness_score": score,
        "reasoning_score": score,
        "strengths": ["Good structure"],
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return EvaluationDimensions(**defaults)


def question_data(text: str, skill: str = "Python", **overrides) -> QuestionData:
    """Build a valid, rubric-carrying QuestionData for tests."""
    from app.services.ai.concept_bank import CONCEPT_BANK

    specs = CONCEPT_BANK.get(skill)
    default_concept = specs[0].name if specs else "git"
    defaults = {
        "question": text,
        "skill": skill,
        "concept": default_concept,
        "intent": "check understanding",
        "difficulty": "medium",
        "question_type": "explanation",
        "expected_concepts": ["GIL"],
        "core_requirements": ["Explain what the GIL is"],
        "optional_depth_points": ["Give an example"],
        "common_misconceptions": [],
    }
    defaults.update(overrides)
    return QuestionData(**defaults)


class ControllableAIService(AIService):
    """Test double: deterministic outputs, or a configurable failure.

    Lets tests exercise validation, duplicate prevention, adaptive
    difficulty and error paths without any real LLM call.
    """

    name = "test-fake"

    def __init__(
        self,
        analysis: CandidateAnalysis | None = None,
        questions: list[QuestionData] | None = None,
        evaluation: EvaluationDimensions | None = None,
        report: ReportSummary | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self._analysis = analysis or CandidateAnalysis(
            candidate_skills=["Python", "FastAPI"],
            required_skills=["Python", "FastAPI", "Docker"],
            skill_gaps=["Docker"],
            topics=["Python", "FastAPI"],
        )
        self._questions = questions or [
            question_data("Explain Python's Global Interpreter Lock.", skill="Python")
        ]
        self._evaluation = evaluation or evaluation_dims(7.0)
        self._report = report or ReportSummary(
            summary="Good performance overall.",
            strengths=["Python"],
            weaknesses=["Docker"],
            recommendations=["Study Docker."],
        )
        self._fail_with = fail_with

    def _maybe_fail(self) -> None:
        if self._fail_with is not None:
            raise self._fail_with

    def analyze_candidate(self, **kwargs) -> CandidateAnalysis:
        self._maybe_fail()
        return self._analysis

    def generate_questions(self, *, number: int = 10, previous_questions: list[str] | None = None, **kwargs) -> list[QuestionData]:
        self._maybe_fail()
        pool = [q for q in self._questions if q.question not in (previous_questions or [])]
        return pool[:number]

    def evaluate_answer(self, **kwargs) -> EvaluationDimensions:
        self._maybe_fail()
        return self._evaluation

    def generate_report(self, **kwargs) -> ReportSummary:
        self._maybe_fail()
        return self._report


@pytest.fixture()
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not enforce foreign keys by default; enable them so tests
    # catch the same constraint bugs PostgreSQL would catch in production.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the in-memory database via dependency override."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def override_ai(client):
    """Fixture factory: inject a ControllableAIService into the app."""

    def _override(fake: AIService) -> None:
        app.dependency_overrides[get_ai_service] = lambda: fake

    return _override


@pytest.fixture()
def auth_headers(client):
    """Register + login a user and return Authorization headers."""
    payload = {
        "email": "candidate@example.com",
        "full_name": "Test Candidate",
        "password": "supersecret123",
    }
    client.post("/auth/register", json=payload)
    res = client.post("/auth/login", json=payload)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_interview(client, auth_headers):
    """Fixture factory: create an interview through the API and return its id."""

    def _make(**overrides) -> int:
        payload = {
            "target_role": "Python Backend Developer",
            "experience_level": "Entry Level",
            "job_description": "Build REST APIs with Python, FastAPI and PostgreSQL.",
            "resume_text": "Built APIs with Python, FastAPI and PostgreSQL. Used Docker.",
            "number_of_questions": 3,
        }
        payload.update(overrides)
        res = client.post("/interviews", json=payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    return _make

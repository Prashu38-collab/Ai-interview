"""Unit tests for the mock AI service (no network involved)."""

from app.services.ai.mock_ai_service import MockAIService
from app.services.score_engine import ScoreEngine


def _score_of(ai, answer_text, *, concepts=("Python", "decorators"),
              requirements=("Explain what a decorator is", "Explain how decorators wrap callables"),
              misconceptions=("a decorator is a class",), question_type="explanation"):
    from app.services.ai.base import EvaluationDimensions

    dims = ai.evaluate_answer(
        question_text="What is a Python decorator?",
        skill="Python",
        concept="decorators",
        difficulty="medium",
        question_type=question_type,
        intent="check understanding",
        expected_concepts=list(concepts),
        core_requirements=list(requirements),
        optional_depth_points=["Give a use case"],
        common_misconceptions=list(misconceptions),
        answer_text=answer_text,
    )
    assert isinstance(dims, EvaluationDimensions)
    return dims


def test_mock_analysis_detects_skills_and_gaps():
    ai = MockAIService()
    analysis = ai.analyze_candidate(
        target_role="Python Backend Developer",
        experience_level="Entry",
        job_description="Python, FastAPI, PostgreSQL, Docker required",
        resume_text="Experienced with Python, FastAPI and PostgreSQL",
    )
    assert "Python" in analysis.candidate_skills
    assert "FastAPI" in analysis.required_skills
    assert "Docker" in analysis.skill_gaps
    assert analysis.topics


def test_mock_questions_are_unique_and_bounded():
    ai = MockAIService()
    analysis = ai.analyze_candidate(
        target_role="Python Backend Developer",
        experience_level="Entry",
        job_description="Python, FastAPI required",
        resume_text="Python and FastAPI",
    )
    questions = ai.generate_questions(
        target_role="Python Backend Developer",
        experience_level="Entry",
        analysis=analysis,
        number=5,
        difficulty="medium",
        previous_questions=[],
        previous_concepts=[],
    )
    texts = [q.question for q in questions]
    assert len(texts) == 5
    assert len(set(texts)) == 5


def test_mock_questions_respect_previous():
    ai = MockAIService()
    analysis = ai.analyze_candidate(
        target_role="Python Backend Developer",
        experience_level="Entry",
        job_description="Python required",
        resume_text="Python",
    )
    first = ai.generate_questions(
        target_role="Python Backend Developer",
        experience_level="Entry",
        analysis=analysis,
        number=2,
        difficulty="medium",
        previous_questions=[],
        previous_concepts=[],
    )
    second = ai.generate_questions(
        target_role="Python Backend Developer",
        experience_level="Entry",
        analysis=analysis,
        number=2,
        difficulty="medium",
        previous_questions=[q.question for q in first],
        previous_concepts=[],
    )
    overlap = {q.question for q in first} & {q.question for q in second}
    assert not overlap


def test_mock_generated_questions_carry_rubrics():
    ai = MockAIService()
    analysis = ai.analyze_candidate(
        target_role="Python Backend Developer",
        experience_level="Entry",
        job_description="Python, FastAPI required",
        resume_text="Python and FastAPI",
    )
    questions = ai.generate_questions(
        target_role="Python Backend Developer",
        experience_level="Entry",
        analysis=analysis,
        number=4,
        difficulty="medium",
        previous_questions=[],
        previous_concepts=[],
    )
    assert questions
    for q in questions:
        assert q.concept
        assert q.core_requirements  # rubric generated with the question
        assert q.question_type in {
            "definition", "explanation", "comparison", "scenario", "debugging",
            "coding", "system_design", "behavioral", "architecture", "tradeoff",
        }


def test_mock_evaluation_returns_validated_model():
    ai = MockAIService()
    dims = _score_of(
        ai,
        "A Python decorator is a function that takes another function and "
        "returns a wrapped version that extends its behaviour.",
    )
    assert 0 <= dims.relevance_score <= 10
    assert dims.answer_status in {
        "on_topic", "partial", "incorrect", "irrelevant", "knowledge_gap",
        "contradictory", "nonsense",
    }
    assert isinstance(dims.satisfied_requirements, list)
    assert isinstance(dims.strengths, list)
    score = ScoreEngine().score(dims)
    assert 0 <= score <= 10


def test_mock_evaluation_penalizes_short_answers():
    ai = MockAIService()
    engine = ScoreEngine()
    short = _score_of(ai, "idk")
    long = _score_of(
        ai,
        "A decorator wraps a function so the wrapper can run code before and "
        "after the call, for example logging, timing or caching. The original "
        "function is left unchanged, and functools.wraps preserves its metadata.",
    )
    assert engine.score(short) < engine.score(long)


def _evaluate(ai, answer_text, concepts=("Python",)):
    engine = ScoreEngine()
    dims = ai.evaluate_answer(
        question_text="Explain what Python is and give a simple example of where it is used.",
        skill="Python",
        concept="python basics",
        difficulty="easy",
        question_type="explanation",
        intent="check understanding",
        expected_concepts=list(concepts),
        core_requirements=["Explain what Python is", "Give a usage example"],
        optional_depth_points=["Mention a concrete tool"],
        common_misconceptions=["a snake"],
        answer_text=answer_text,
    )
    return dims, engine.score(dims)


def test_mock_evaluation_rewards_focused_technical_answers():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "Python is an interpreted, high-level programming language used for web "
        "development, automation and data science. I built REST APIs with FastAPI "
        "and automated data processing with pandas.",
    )
    assert score >= 7.0
    assert not dims.missing_requirements
    assert not dims.technical_errors


def test_mock_evaluation_punishes_offtopic_padding():
    ai = MockAIService()
    _, score = _evaluate(
        ai,
        "Python is a programming language and it is used everywhere. "
        "its a snake can eat any animals.",
    )
    assert score <= 4.5  # capped by the "incorrect" hard gate (snake misconception)


def test_mock_evaluation_rejects_generic_gibberish():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "I love my dog and the weather is nice today. It is very good and great "
        "and awesome and fantastic.",
    )
    assert score < 3.0
    assert any("python" in t.lower() for t in dims.recommended_topics)


def test_mock_evaluation_caps_very_short_answers():
    ai = MockAIService()
    _, score = _evaluate(ai, "Python is a programming language.")
    assert score <= 4.5

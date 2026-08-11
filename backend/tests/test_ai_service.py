"""Unit tests for the mock AI service (no network involved)."""

from app.services.ai.mock_ai_service import MockAIService


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
    )
    second = ai.generate_questions(
        target_role="Python Backend Developer",
        experience_level="Entry",
        analysis=analysis,
        number=2,
        difficulty="medium",
        previous_questions=[q.question for q in first],
    )
    overlap = {q.question for q in first} & {q.question for q in second}
    assert not overlap


def test_mock_evaluation_returns_validated_model():
    ai = MockAIService()
    ev = ai.evaluate_answer(
        question_text="Explain asyncio.",
        skill="Python",
        difficulty="medium",
        question_type="conceptual",
        expected_concepts=["asyncio", "event loop"],
        answer_text="asyncio relies on an event loop to schedule coroutines.",
    )
    assert 0 <= ev.score <= 10
    assert isinstance(ev.strengths, list)
    assert isinstance(ev.feedback, str)


def test_mock_evaluation_penalizes_short_answers():
    ai = MockAIService()
    short = ai.evaluate_answer(
        question_text="Explain asyncio.",
        skill="Python",
        difficulty="medium",
        question_type="conceptual",
        expected_concepts=["asyncio", "event loop"],
        answer_text="idk",
    )
    long = ai.evaluate_answer(
        question_text="Explain asyncio.",
        skill="Python",
        difficulty="medium",
        question_type="conceptual",
        expected_concepts=["asyncio", "event loop"],
        answer_text="asyncio uses an event loop to run coroutines concurrently. "
        "The event loop schedules and awaits tasks, enabling high concurrency.",
    )
    assert short.score < long.score


def _evaluate(ai, answer_text, concepts=("Python",)):
    return ai.evaluate_answer(
        question_text="Explain what Python is and give a simple example of where it is used.",
        skill="Python",
        difficulty="easy",
        question_type="conceptual",
        expected_concepts=list(concepts),
        answer_text=answer_text,
    )


def test_mock_evaluation_rewards_focused_technical_answers():
    ai = MockAIService()
    good = _evaluate(
        ai,
        "Python is an interpreted, high-level programming language used for web "
        "development, automation and data science. I built REST APIs with FastAPI "
        "and automated data processing with pandas.",
    )
    assert good.score >= 7.0
    assert not good.weaknesses


def test_mock_evaluation_punishes_offtopic_padding():
    ai = MockAIService()
    ev = _evaluate(
        ai,
        "Python is a programming language and it is used everywhere. "
        "its a snake can eat any animals.",
    )
    assert ev.score < 4.5
    assert any("off-topic" in w for w in ev.weaknesses)


def test_mock_evaluation_rejects_generic_gibberish():
    ai = MockAIService()
    ev = _evaluate(
        ai,
        "I love my dog and the weather is nice today. It is very good and great "
        "and awesome and fantastic.",
    )
    assert ev.score < 3.0
    assert "Python" in " ".join(ev.weaknesses)


def test_mock_evaluation_caps_very_short_answers():
    ai = MockAIService()
    ev = _evaluate(ai, "Python is a programming language.")
    assert ev.score <= 4.5

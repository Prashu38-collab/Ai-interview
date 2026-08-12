"""Behavior tests for the Part 40 scenarios.

These pin the *behaviour* the evaluator must guarantee, not its internals:

- concise but correct answers get full credit,
- keyword stuffing / nonsense / "I don't know" never score meaningfully,
- irrelevant-but-technical answers stay low,
- misconceptions and contradictions are flagged and capped,
- partial answers land mid-range and drive a targeted follow-up,
- the follow-up targets the specific weakness, not a random topic.
"""

from app.services.ai.mock_ai_service import MockAIService
from app.services.score_engine import ScoreEngine


def _evaluate(ai, answer_text, **overrides):
    rubric = {
        "question_text": "Explain how a Python decorator works.",
        "skill": "Python",
        "concept": "decorators",
        "difficulty": "medium",
        "question_type": "explanation",
        "intent": "check understanding",
        "expected_concepts": ["decorator", "wrapper", "callable", "functools"],
        "core_requirements": [
            "Explain what a decorator is",
            "Explain how decorators wrap a callable",
        ],
        "optional_depth_points": ["Give a real use case"],
        "common_misconceptions": ["a decorator is a class"],
    }
    rubric.update(overrides)
    dims = ai.evaluate_answer(**rubric, answer_text=answer_text)
    return dims, ScoreEngine().score(dims)


def test_concise_correct_answer_gets_full_credit():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "A decorator is a function that takes another function and returns a "
        "wrapper that adds behaviour before and after the call.",
    )
    assert dims.answer_status == "strong"
    assert not dims.missing_requirements
    assert score >= 7.0


def test_keyword_stuffing_is_capped():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "decorator wrapper functools wraps callable metaclass generator async closure lambda",
    )
    assert dims.answer_status == "keyword_stuffing"
    assert score <= 1.5


def test_irrelevant_but_technical_stays_low():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "PostgreSQL uses B-tree indexes and MVCC for transaction isolation, and "
        "a load balancer distributes requests across replicas.",
    )
    assert dims.answer_status == "irrelevant"
    assert score <= 2.5


def test_misconception_is_flagged_and_capped():
    ai = MockAIService()
    dims, score = _evaluate(
        ai, "A decorator is a class that you annotate methods with."
    )
    assert dims.answer_status == "incorrect"
    assert any("class" in e for e in dims.technical_errors)
    assert score <= 4.5


def test_partial_answer_scores_mid_range_and_identifies_gap():
    ai = MockAIService()
    dims, score = _evaluate(ai, "A decorator modifies a function.")
    assert dims.answer_status == "partial"
    assert 2.0 <= score < 7.0
    assert dims.missing_requirements or dims.partial_requirements
    assert dims.follow_up_question  # a partial answer always drives a follow-up


def test_alternative_valid_phrasing_scores_well():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "A Python decorator takes a callable and returns a new callable, letting "
        "you run setup or teardown logic around the original function, for "
        "example timing, logging or auth checks.",
    )
    assert dims.answer_status == "strong"
    assert not dims.missing_requirements
    assert score >= 7.0


def test_i_dont_know_is_a_low_knowledge_gap():
    ai = MockAIService()
    dims, score = _evaluate(
        ai, "I don't know, I haven't studied decorators yet."
    )
    assert dims.answer_status == "knowledge_gap"
    assert score <= 2.0


def test_contradictory_answer_is_capped():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "Decorators always modify the function in place, but they never change "
        "the original function.",
    )
    assert dims.answer_status == "contradictory"
    assert dims.contradictions
    assert score <= 4.0


def test_long_irrelevant_ramble_stays_low():
    ai = MockAIService()
    _, score = _evaluate(
        ai,
        "The weather today is great for a long walk in the park. I love coffee "
        "and the sky is blue and the birds are singing and the grass is green.",
    )
    assert score <= 2.5


def test_verbose_offtopic_padding_is_not_rewarded():
    ai = MockAIService()
    _, score = _evaluate(
        ai,
        "A decorator is used in Python everywhere and it is great and awesome "
        "and fantastic and wonderful and the best thing ever invented.",
    )
    assert score < 7.0


# ---------------------------------------------------------------------------
# Follow-up wiring through the real API (mock provider)
# ---------------------------------------------------------------------------


def test_follow_up_targets_weakness_after_partial_answer(
    client, auth_headers, make_interview
):
    interview_id = make_interview(number_of_questions=2)
    questions = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    ).json()["questions"]
    qid = questions[0]["id"]

    res = client.post(
        f"/questions/{qid}/answer",
        json={"text": "Python has data types like int, list and dict."},
        headers=auth_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["evaluation"]["answer_status"] == "partial"
    follow_up = body["follow_up"]
    assert follow_up is not None
    assert follow_up["follow_up_of"] == qid
    assert follow_up["concept"] == questions[0]["concept"]
    # The follow-up intent must reference the detected gap, not a random topic.
    assert questions[0]["concept"].lower() in follow_up["text"].lower()


def test_strong_answer_produces_no_follow_up(client, auth_headers, make_interview):
    interview_id = make_interview(number_of_questions=1)
    questions = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    ).json()["questions"]
    qid = questions[0]["id"]

    res = client.post(
        f"/questions/{qid}/answer",
        json={
            "text": "Python is dynamically typed, so a variable can rebind to "
            "different types at runtime. Values are mutable or immutable "
            "depending on their type, and the common built-ins are int, float, "
            "str, list, dict, tuple and set."
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["evaluation"]["score"] >= 7.0
    assert body["follow_up"] is None


def test_pasting_the_question_is_a_repetition_not_an_answer():
    ai = MockAIService()
    question = "Explain how a Python decorator works."
    dims, score = _evaluate(ai, question)
    assert dims.answer_status == "question_repetition"
    assert score <= 1.0
    assert not dims.satisfied_requirements
    assert not dims.demonstrated_concepts
    assert not dims.strengths


def test_reworded_question_is_still_flagged_as_repetition():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "So you want an explanation of how a Python decorator works, please.",
    )
    assert dims.answer_status == "question_repetition"
    assert score <= 1.0


def test_question_echo_with_a_real_explanation_is_not_flagged():
    ai = MockAIService()
    dims, score = _evaluate(
        ai,
        "Explain how a Python decorator works. A decorator is a function that "
        "takes another function and returns a wrapper that adds behaviour "
        "before and after the call.",
    )
    assert dims.answer_status == "strong"
    assert score >= 7.0

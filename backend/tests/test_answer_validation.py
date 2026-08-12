"""Acceptance tests for the answer-validation stage (the pasted-question bug).

These pin the behaviour the architectural fix must guarantee: a candidate who
pastes or lightly rephrases the question, copies keywords, or answers a
question type without the requested reasoning must never earn credit. They
mirror the benchmark acceptance cases as unit tests so the fix is verified
both in-process and end-to-end.

Cases (matching the product spec):
  1. pasting the question verbatim       -> question_repetition, score <= 1
  2. light paraphrase of the question    -> question_repetition, score <= 1
  3. keywords copied from the question   -> keyword_stuffing, score <= 1
  4. a single concept word               -> insufficient_evidence, score <= 2
  5. short but complete answer           -> strong, score >= 7
  6. off-topic but grammatical           -> irrelevant, score <= 2
  7. technically wrong but grammatical   -> incorrect, score <= 4.5
  8. same correct answer, other wording  -> strong, score >= 7
  9. partially correct with a clear gap  -> partial, 2 <= score < 7
  10. coding question, definitions only  -> incomplete, not strong
"""

from app.services.ai.mock_ai_service import MockAIService
from app.services.score_engine import ScoreEngine

RUBRIC = {
    "question_text": "Write a short snippet using data structures in Python. "
    "What are the key design decisions?",
    "skill": "Python",
    "concept": "data structures",
    "difficulty": "easy",
    "question_type": "coding",
    "intent": None,
    "expected_concepts": ["lists and tuples", "sets and dictionaries"],
    "core_requirements": [
        "list vs tuple vs set vs dict",
        "time complexity of common operations",
        "choosing the right structure for the problem",
    ],
    "optional_depth_points": [],
    "common_misconceptions": [
        "dict keys can be any object",
        "sets preserve insertion order",
    ],
}


def _evaluate(answer_text: str, **overrides):
    rubric = dict(RUBRIC)
    rubric.update(overrides)
    ai = MockAIService()
    dims = ai.evaluate_answer(**rubric, answer_text=answer_text)
    return dims, ScoreEngine().score(dims)


def test_pasting_the_question_verbatim_is_repetition():
    dims, score = _evaluate(RUBRIC["question_text"])
    assert dims.answer_status == "question_repetition"
    assert score <= 1.0
    assert dims.demonstrated_concepts == []
    assert dims.strengths == []


def test_light_paraphrase_without_new_info_is_repetition():
    dims, score = _evaluate(
        "So you want to write a short snippet using data structures in the "
        "Python programming language and then talk about the key design "
        "decisions you would make."
    )
    assert dims.answer_status == "question_repetition"
    assert score <= 1.0
    assert not dims.satisfied_requirements


def test_keyword_list_copied_from_question_is_stuffing():
    dims, score = _evaluate(
        "list tuple set dict time complexity indexing hashing iteration "
        "ordered mutable immutable"
    )
    assert dims.answer_status == "keyword_stuffing"
    assert score <= 1.0


def test_single_concept_word_is_insufficient_evidence():
    dims, score = _evaluate("dictionary")
    assert dims.answer_status == "insufficient_evidence"
    assert score <= 2.0


def test_short_but_complete_answer_is_strong():
    dims, score = _evaluate(
        "Lists are ordered and mutable, tuples are ordered but immutable, sets "
        "are unordered and unique. Pick a list for ordered data you change, a "
        "tuple for fixed data, a set for O(1) membership checks. The key is "
        "choosing the right structure for the operation.",
        question_type="comparison",
        question_text="Compare lists, tuples and sets in Python. When would "
        "you pick each one?",
    )
    assert dims.answer_status == "strong"
    assert score >= 7.0
    assert dims.demonstrated_concepts


def test_off_topic_but_grammatical_is_irrelevant():
    dims, score = _evaluate(
        "The best bread for breakfast is sourdough because of its crust."
    )
    assert dims.answer_status == "irrelevant"
    assert score <= 2.0


def test_technically_wrong_but_grammatical_is_incorrect():
    dims, score = _evaluate(
        "Sets preserve insertion order in Python, so you can rely on iteration "
        "matching the order items were added."
    )
    assert dims.answer_status == "incorrect"
    assert score <= 4.5
    assert dims.technical_errors


def test_synonymous_terminology_still_scores_strong():
    dims, score = _evaluate(
        "The key design decisions: an ordered resizable sequence for positional "
        "access, a hash map for fast key lookups, a hash set for uniqueness and "
        "membership tests. Choosing the right container for the problem is the "
        "whole point; hashed structures give constant-time average access, and "
        "the operations you need determine the choice."
    )
    assert dims.answer_status == "strong"
    assert score >= 7.0


def test_partial_answer_is_partial_with_gap_identified():
    dims, score = _evaluate(
        "I would use a set built from the names to remove duplicates, then a "
        "dict to count occurrences. That is a fast approach."
    )
    assert dims.answer_status == "partial"
    assert 2.0 <= score < 7.0
    assert dims.missing_requirements


def test_coding_question_answered_with_definitions_only_is_incomplete():
    dims, score = _evaluate(
        "Data structures in Python are things like lists, tuples, sets and "
        "dicts. They store collections of items."
    )
    assert dims.answer_status == "incomplete"
    assert score < 7.0
    assert dims.demonstrated_concepts == []

"""Run the evaluation benchmark against the mock evaluator.

Every case in ``tests/benchmark_cases.json`` is evaluated with the deterministic
``MockAIService`` + ``ScoreEngine`` and must land in its expected category
(status + score bounds). The exit code is non-zero when any case fails, so CI
can gate on the benchmark.

Usage:
    python scripts/run_benchmark.py [path/to/benchmark_cases.json]
"""

import json
import sys
from pathlib import Path

# Make the backend package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.concept_bank import (
    QUESTION_TYPE_TEMPLATES,
    concept_for,
    normalize_type,
)
from app.services.ai.mock_ai_service import MockAIService
from app.services.score_engine import ScoreEngine

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "tests" / "benchmark_cases.json"

# category -> expected outcome. "statuses" = allowed answer_status values,
# "min"/"max" = score bounds.
EXPECTATIONS: dict[str, dict] = {
    "correct": {"statuses": {"on_topic"}, "min": 7.0},
    "concise_correct": {"statuses": {"on_topic"}, "min": 7.0},
    "alternative_valid": {"statuses": {"on_topic"}, "min": 7.0},
    "partial": {"statuses": {"partial"}, "min": 2.0, "max": 7.0},
    "incorrect": {"statuses": {"incorrect"}, "max": 4.5},
    "irrelevant": {"statuses": {"irrelevant"}, "max": 2.5},
    "keyword_stuffing": {"statuses": {"nonsense"}, "max": 1.5},
    "verbose_irrelevant": {"statuses": {"partial", "irrelevant", "incorrect"}, "max": 7.0},
    "contradictory": {"statuses": {"contradictory"}, "max": 4.0},
    "unknown": {"statuses": {"knowledge_gap"}, "max": 2.0},
    "scenario": {"statuses": {"on_topic"}, "min": 7.0},
    "debugging": {"statuses": {"on_topic"}, "min": 7.0},
    "coding": {"statuses": {"on_topic"}, "min": 7.0},
    "system_design": {"statuses": {"on_topic"}, "min": 7.0},
}

# Rubric fields a case may override; anything else comes from the concept bank.
OVERRIDABLE = {
    "question_text",
    "expected_concepts",
    "core_requirements",
    "optional_depth_points",
    "common_misconceptions",
}


def default_context(skill: str, concept: str, question_type: str) -> dict:
    """Default question context resolved from the concept bank."""
    spec = concept_for(skill, concept)
    key_points = spec.key_points if spec else []
    core = list(key_points[:4]) or [f"Explain what {concept} is"]
    qtype = normalize_type(question_type)
    seed = spec.seeds.get(qtype) if spec else None
    question_text = seed or QUESTION_TYPE_TEMPLATES.get(
        qtype, QUESTION_TYPE_TEMPLATES["explanation"]
    ).format(concept=concept, skill=skill)
    return {
        "question_text": question_text,
        "expected_concepts": [skill] + core[:3],
        "core_requirements": core,
        "optional_depth_points": list(key_points[4:8]) or ["Give a concrete example"],
        "common_misconceptions": list(spec.misconceptions) if spec else [],
    }


def evaluate_case(case: dict, ai: MockAIService, engine: ScoreEngine) -> tuple[str, float]:
    ctx = default_context(case["skill"], case["concept"], case["question_type"])
    ctx.update({k: v for k, v in case.items() if k in OVERRIDABLE})
    dims = ai.evaluate_answer(
        question_text=ctx["question_text"],
        skill=case["skill"],
        concept=case["concept"],
        difficulty="medium",
        question_type=normalize_type(case["question_type"]),
        intent="check understanding",
        expected_concepts=ctx["expected_concepts"],
        core_requirements=ctx["core_requirements"],
        optional_depth_points=ctx["optional_depth_points"],
        common_misconceptions=ctx["common_misconceptions"],
        answer_text=case["answer"],
    )
    return dims.answer_status, engine.score(dims)


def main(path: Path = DEFAULT_CASES) -> int:
    data = json.loads(Path(path).read_text())
    cases = data["cases"]
    ai = MockAIService()
    engine = ScoreEngine()

    failures = 0
    rows: list[tuple[bool, str, str, str, str]] = []
    for case in cases:
        status, score = evaluate_case(case, ai, engine)
        exp = EXPECTATIONS[case["category"]]
        ok = status in exp["statuses"]
        ok = ok and score >= exp.get("min", -1.0)
        ok = ok and score <= exp.get("max", 11.0)
        if not ok:
            failures += 1
        expected = f"{sorted(exp['statuses'])} / {exp.get('min', 0)}-{exp.get('max', 10)}"
        rows.append((ok, case["id"], case["category"], f"{status} / {score}", expected))

    width_id = max(len(r[1]) for r in rows)
    width_cat = max(len(r[2]) for r in rows)
    print(f"{'OK?':<4} {'case':<{width_id}} {'category':<{width_cat}} {'actual':<16} expected")
    print("-" * (4 + width_id + width_cat + 16 + 22))
    for ok, cid, cat, actual, expected in rows:
        mark = "PASS" if ok else "FAIL"
        print(f"{mark:<4} {cid:<{width_id}} {cat:<{width_cat}} {actual:<16} {expected}")

    total = len(rows)
    print(f"\n{total - failures}/{total} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CASES
    raise SystemExit(main(path))

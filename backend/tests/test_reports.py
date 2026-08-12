"""Final report: score math, generation flow, and permissions."""

from tests.conftest import ControllableAIService, evaluation_dims, question_data


def _fully_answered_interview(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        evaluation=evaluation_dims(8.0),
        questions=[
            question_data(
                "Explain how Python's GIL affects threading.",
                skill="Python",
                expected_concepts=["GIL"],
                core_requirements=["Explain the GIL"],
            ),
            question_data(
                "Explain how Python function scoping works.",
                skill="Python",
                concept="functions and scoping",
                expected_concepts=["LEGB"],
                core_requirements=["Explain scoping"],
            ),
            question_data(
                "Explain how Docker containers isolate processes.",
                skill="Docker",
                expected_concepts=["namespaces"],
                core_requirements=["Explain isolation"],
            ),
        ],
    )
    override_ai(fake)
    interview_id = make_interview(number_of_questions=3)
    questions = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    ).json()["questions"]
    for q in questions:
        res = client.post(
            f"/questions/{q['id']}/answer",
            json={"text": "A solid answer covering the basics."},
            headers=auth_headers,
        )
        assert res.status_code == 201, res.text
    return interview_id


def test_complete_without_answers_rejected(client, auth_headers, make_interview):
    interview_id = make_interview()
    res = client.post(f"/interviews/{interview_id}/complete", headers=auth_headers)
    assert res.status_code == 400


def test_complete_generates_report(client, auth_headers, make_interview, override_ai):
    interview_id = _fully_answered_interview(client, auth_headers, make_interview, override_ai)
    res = client.post(f"/interviews/{interview_id}/complete", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()

    assert body["overall_score"] == 8.0
    assert body["average_score"] == 8.0
    assert body["summary"] == "Good performance overall."
    assert len(body["skill_scores"]) == 2  # Python + Docker
    by_skill = {s["skill"]: s for s in body["skill_scores"]}
    assert by_skill["Python"]["score"] == 8.0
    assert by_skill["Python"]["question_count"] == 2
    assert by_skill["Docker"]["question_count"] == 1


def test_report_404_before_completion(client, auth_headers, make_interview):
    interview_id = make_interview()
    res = client.get(f"/interviews/{interview_id}/report", headers=auth_headers)
    assert res.status_code == 404


def test_report_available_after_completion(client, auth_headers, make_interview, override_ai):
    interview_id = _fully_answered_interview(client, auth_headers, make_interview, override_ai)
    client.post(f"/interviews/{interview_id}/complete", headers=auth_headers)
    res = client.get(f"/interviews/{interview_id}/report", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["overall_score"] == 8.0


def test_interview_status_becomes_completed(client, auth_headers, make_interview, override_ai):
    interview_id = _fully_answered_interview(client, auth_headers, make_interview, override_ai)
    client.post(f"/interviews/{interview_id}/complete", headers=auth_headers)
    detail = client.get(f"/interviews/{interview_id}", headers=auth_headers).json()
    assert detail["status"] == "completed"


def test_skill_score_average_math(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        evaluation=evaluation_dims(6.0),
        questions=[
            question_data(
                f"Python question {i}.",
                skill="Python",
                expected_concepts=["x"],
                core_requirements=["Explain x"],
            )
            for i in range(2)
        ],
    )
    override_ai(fake)
    interview_id = make_interview(number_of_questions=2)
    questions = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    ).json()["questions"]
    # One strong answer (overridden score 9) + one weak (overridden 3)
    fake._evaluation = evaluation_dims(9.0)
    client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "strong"},
        headers=auth_headers,
    )
    fake._evaluation = evaluation_dims(3.0)
    client.post(
        f"/questions/{questions[1]['id']}/answer",
        json={"text": "weak"},
        headers=auth_headers,
    )
    res = client.post(f"/interviews/{interview_id}/complete", headers=auth_headers)
    body = res.json()
    assert body["overall_score"] == 6.0
    assert body["skill_scores"][0]["score"] == 6.0

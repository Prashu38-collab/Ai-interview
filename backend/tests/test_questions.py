from tests.conftest import ControllableAIService, QuestionData


def _answered_question_id(body) -> int:
    return body["questions"][0]["id"]


def test_generate_questions_requires_analysis_capability(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            QuestionData(
                question="What is Python's GIL?",
                skill="Python",
                difficulty="medium",
                question_type="conceptual",
                expected_concepts=["GIL"],
            )
        ]
    )
    override_ai(fake)
    interview_id = make_interview()

    res = client.post(
        f"/interviews/{interview_id}/generate-questions",
        json={"difficulty": "medium"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["generated"] == 1
    q = body["questions"][0]
    assert q["text"] == "What is Python's GIL?"
    assert q["difficulty"] == "medium"
    assert q["expected_concepts"] == ["GIL"]


def test_generate_questions_is_deduplicated(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            QuestionData(
                question="What is Python's GIL?",
                skill="Python",
                difficulty="medium",
                question_type="conceptual",
                expected_concepts=["GIL"],
            )
        ]
    )
    override_ai(fake)
    interview_id = make_interview()

    first = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    )
    second = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    )
    assert first.status_code == second.status_code == 200
    texts1 = [q["text"] for q in first.json()["questions"]]
    texts2 = [q["text"] for q in second.json()["questions"]]
    assert len(texts1) == len(set(texts1))
    assert len(texts2) == len(texts1)  # no growth on regenerate


def test_generate_questions_keeps_batch_under_target(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            QuestionData(
                question=f"Question number {i}.",
                skill="Python",
                difficulty="medium",
                question_type="conceptual",
                expected_concepts=["x"],
            )
            for i in range(10)
        ]
    )
    override_ai(fake)
    interview_id = make_interview(number_of_questions=3)

    res = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    )
    assert res.status_code == 200
    assert len(res.json()["questions"]) == 3


def test_generate_questions_other_user_forbidden(client, auth_headers, make_interview):
    interview_id = make_interview()
    client.post(
        "/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "supersecret123"},
    )
    token = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "supersecret123"}
    ).json()["access_token"]
    res = client.post(
        f"/interviews/{interview_id}/generate-questions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_list_questions_returns_ordered(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            QuestionData(
                question=f"Ordered question {i}.",
                skill="Python",
                difficulty="medium",
                question_type="conceptual",
                expected_concepts=["x"],
            )
            for i in range(3)
        ]
    )
    override_ai(fake)
    interview_id = make_interview(number_of_questions=3)
    client.post(f"/interviews/{interview_id}/generate-questions", headers=auth_headers)

    res = client.get(f"/interviews/{interview_id}/questions", headers=auth_headers)
    assert res.status_code == 200
    questions = res.json()
    assert len(questions) == 3
    assert all(q["status"] == "pending" for q in questions)

from tests.conftest import ControllableAIService, question_data


def _answered_question_id(body) -> int:
    return body["questions"][0]["id"]


def test_generate_questions_requires_analysis_capability(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            question_data(
                "What is Python's GIL?",
                skill="Python",
                expected_concepts=["GIL"],
                core_requirements=["Explain what the GIL is"],
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
    assert body["generated"] == 3
    q = body["questions"][0]
    assert q["text"] == "What is Python's GIL?"
    assert q["difficulty"] == "medium"
    assert q["expected_concepts"] == ["GIL"]


def test_generate_questions_is_deduplicated(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        questions=[
            question_data(
                "What is Python's GIL?",
                skill="Python",
                expected_concepts=["GIL"],
                core_requirements=["Explain what the GIL is"],
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
            question_data(
                f"Explain question number {i}.",
                skill="Python",
                expected_concepts=["x"],
                core_requirements=["Explain x"],
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
            question_data(
                f"Explain ordered question {i}.",
                skill="Python",
                expected_concepts=["x"],
                core_requirements=["Explain x"],
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


def test_regenerate_replaces_pending_questions(client, auth_headers, make_interview, override_ai):
    first_pool = [
        question_data(
            "Explain how Python stores variables and data types.",
            skill="Python",
            concept="variables and data types",
            expected_concepts=["x"],
            core_requirements=["Explain x"],
        ),
        question_data(
            "How do you deduplicate a list while preserving order in Python?",
            skill="Python",
            concept="data structures",
            expected_concepts=["y"],
            core_requirements=["Explain y"],
        ),
        question_data(
            "Explain Python's LEGB scoping rule.",
            skill="Python",
            concept="functions and scoping",
            expected_concepts=["z"],
            core_requirements=["Explain z"],
        ),
    ]
    second_pool = [
        question_data(
            "Compare sets and lists in Python for membership tests.",
            skill="Python",
            concept="data structures",
            expected_concepts=["a"],
            core_requirements=["Explain a"],
        ),
        question_data(
            "Explain how Python generators yield values lazily.",
            skill="Python",
            concept="generators and iterators",
            expected_concepts=["b"],
            core_requirements=["Explain b"],
        ),
    ]

    fake = ControllableAIService(questions=first_pool)
    override_ai(fake)
    interview_id = make_interview(number_of_questions=3)
    client.post(f"/interviews/{interview_id}/generate-questions", headers=auth_headers)

    # Answer the first question; it must survive regeneration.
    qs = client.get(f"/interviews/{interview_id}/questions", headers=auth_headers).json()
    client.post(
        f"/questions/{qs[0]['id']}/answer",
        json={"text": "A committed answer."},
        headers=auth_headers,
    )

    fake._questions = second_pool
    res = client.post(
        f"/interviews/{interview_id}/generate-questions",
        json={"difficulty": "medium", "replace_pending": True},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["generated"] == 3

    final = client.get(f"/interviews/{interview_id}/questions", headers=auth_headers).json()
    texts = {q["text"] for q in final}
    # The answered question survives; the two pending ones are replaced fresh.
    assert "Explain how Python stores variables and data types." in texts
    assert "How do you deduplicate a list while preserving order in Python?" not in texts
    assert "Compare sets and lists in Python for membership tests." in texts
    assert len([q for q in final if q["status"] == "answered"]) == 1
    assert len(final) == 3

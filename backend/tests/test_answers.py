from tests.conftest import ControllableAIService, evaluation_dims, question_data


def _make_questioned_interview(client, auth_headers, make_interview, override_ai, score=7.0):
    fake = ControllableAIService(
        evaluation=evaluation_dims(score),
        questions=[
            question_data(
                "Explain Python's GIL.",
                skill="Python",
                expected_concepts=["GIL", "threading"],
                core_requirements=["Explain what the GIL is", "Explain thread safety"],
            ),
            question_data(
                "How does PostgreSQL handle transactions?",
                skill="PostgreSQL",
                concept="transactions and ACID",
                expected_concepts=["ACID"],
                core_requirements=["Explain ACID properties"],
            ),
        ],
    )
    override_ai(fake)
    interview_id = make_interview(number_of_questions=2)
    res = client.post(
        f"/interviews/{interview_id}/generate-questions", headers=auth_headers
    )
    assert res.status_code == 200
    return fake, interview_id, res.json()["questions"]


def test_submit_answer_creates_evaluation(client, auth_headers, make_interview, override_ai):
    _, interview_id, questions = _make_questioned_interview(
        client, auth_headers, make_interview, override_ai, score=7.0
    )
    qid = questions[0]["id"]
    res = client.post(
        f"/questions/{qid}/answer",
        json={"text": "The GIL prevents multiple threads from running Python bytecode simultaneously."},
        headers=auth_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["question_id"] == qid
    assert body["evaluation"]["score"] == 7.0
    assert body["evaluation"]["answer_status"] == "on_topic"
    assert body["evaluation"]["feedback"]  # feedback is non-empty

    status = client.get(f"/interviews/{interview_id}/questions", headers=auth_headers).json()
    assert status[0]["status"] == "answered"


def test_submit_empty_answer_rejected(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(client, auth_headers, make_interview, override_ai)
    res = client.post(
        f"/questions/{questions[0]['id']}/answer", json={"text": "   "}, headers=auth_headers
    )
    assert res.status_code == 422


def test_answer_already_answered_rejected(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(client, auth_headers, make_interview, override_ai)
    qid = questions[0]["id"]
    payload = {"text": "A reasonable answer."}
    assert client.post(f"/questions/{qid}/answer", json=payload, headers=auth_headers).status_code == 201
    res = client.post(f"/questions/{qid}/answer", json=payload, headers=auth_headers)
    assert res.status_code == 400


def test_answer_other_user_forbidden(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(client, auth_headers, make_interview, override_ai)
    client.post(
        "/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "supersecret123"},
    )
    token = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "supersecret123"}
    ).json()["access_token"]
    res = client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "intrusion attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_adaptive_difficulty_increases_on_high_score(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(
        client, auth_headers, make_interview, override_ai, score=9.0
    )
    res = client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "An excellent, detailed answer."},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["next_difficulty"] == "hard"


def test_adaptive_difficulty_decreases_on_low_score(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(
        client, auth_headers, make_interview, override_ai, score=4.0
    )
    res = client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "vague"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["next_difficulty"] == "easy"


def test_adaptive_difficulty_stays_on_mid_score(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(
        client, auth_headers, make_interview, override_ai, score=6.0
    )
    res = client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "A decent middle-ground answer."},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["next_difficulty"] == "medium"


def test_adaptive_difficulty_clamps_at_bounds(client):
    from app.services.evaluation_service import adapt_difficulty

    assert adapt_difficulty(9.0, "hard") == "hard"
    assert adapt_difficulty(2.0, "easy") == "easy"


def test_same_answer_twice_flags_duplicate(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(client, auth_headers, make_interview, override_ai)
    text = "Python uses a global interpreter lock to keep memory safe across threads."
    first = client.post(
        f"/questions/{questions[0]['id']}/answer", json={"text": text}, headers=auth_headers
    )
    second = client.post(
        f"/questions/{questions[1]['id']}/answer", json={"text": text}, headers=auth_headers
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["duplicate_of"] is None
    assert first.json()["duplicate_warning"] is None
    assert second.json()["duplicate_of"] == questions[0]["id"]
    assert "similar" in second.json()["duplicate_warning"].lower()


def test_distinct_answers_not_flagged(client, auth_headers, make_interview, override_ai):
    _, _, questions = _make_questioned_interview(client, auth_headers, make_interview, override_ai)
    a = client.post(
        f"/questions/{questions[0]['id']}/answer",
        json={"text": "The GIL serializes bytecode execution between threads."},
        headers=auth_headers,
    )
    b = client.post(
        f"/questions/{questions[1]['id']}/answer",
        json={"text": "PostgreSQL uses MVCC and write-ahead logging to guarantee ACID transactions."},
        headers=auth_headers,
    )
    assert a.status_code == b.status_code == 201
    assert a.json()["duplicate_of"] is None
    assert b.json()["duplicate_of"] is None
    assert b.json()["duplicate_warning"] is None

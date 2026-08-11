from tests.conftest import CandidateAnalysis, ControllableAIService


def test_create_interview_requires_auth(client):
    res = client.post(
        "/interviews",
        json={
            "target_role": "Python Backend Developer",
            "experience_level": "Entry Level",
            "job_description": "jd",
            "resume_text": "resume",
        },
    )
    assert res.status_code == 401


def test_create_interview_success(client, auth_headers):
    res = client.post(
        "/interviews",
        json={
            "target_role": "Python Backend Developer",
            "experience_level": "Entry Level",
            "job_description": "Build REST APIs with Python, FastAPI and PostgreSQL.",
            "resume_text": "Built APIs with Python, FastAPI and PostgreSQL. Used Docker.",
            "number_of_questions": 5,
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["target_role"] == "Python Backend Developer"
    assert body["status"] == "created"
    assert body["analysis"] is None
    assert "user_id" not in body  # don't leak


def test_create_interview_validation_error(client, auth_headers):
    res = client.post(
        "/interviews",
        json={"target_role": "x", "experience_level": "", "job_description": "short"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_list_interviews_empty(client, auth_headers):
    res = client.get("/interviews", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_list_interviews_returns_created(client, auth_headers, make_interview):
    make_interview()
    res = client.get("/interviews", headers=auth_headers)
    body = res.json()
    assert len(body) == 1
    assert body[0]["target_role"] == "Python Backend Developer"
    assert body[0]["status"] == "created"


def test_get_interview_detail(client, auth_headers, make_interview):
    interview_id = make_interview()
    res = client.get(f"/interviews/{interview_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == interview_id


def test_get_interview_not_found(client, auth_headers):
    res = client.get("/interviews/999", headers=auth_headers)
    assert res.status_code == 404


def test_get_interview_other_user_forbidden(client, auth_headers, make_interview):
    interview_id = make_interview()
    other = {
        "email": "other@example.com",
        "full_name": "Other User",
        "password": "supersecret123",
    }
    client.post("/auth/register", json=other)
    token = client.post("/auth/login", json=other).json()["access_token"]
    res = client.get(f"/interviews/{interview_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_analyze_interview_stores_analysis(client, auth_headers, make_interview, override_ai):
    fake = ControllableAIService(
        analysis=CandidateAnalysis(
            candidate_skills=["Python"],
            required_skills=["Python", "Docker"],
            skill_gaps=["Docker"],
            topics=["Python"],
        )
    )
    override_ai(fake)
    interview_id = make_interview()

    res = client.post(f"/interviews/{interview_id}/analyze", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["skill_gaps"] == ["Docker"]

    detail = client.get(f"/interviews/{interview_id}", headers=auth_headers).json()
    assert detail["status"] == "ready"
    assert detail["analysis"]["required_skills"] == ["Python", "Docker"]

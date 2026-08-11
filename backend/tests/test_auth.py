def test_register_returns_token(client):
    res = client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "full_name": "New User",
            "password": "password123",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_register_duplicate_email_conflicts(client):
    payload = {
        "email": "dup@example.com",
        "full_name": "Dup User",
        "password": "password123",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    res = client.post("/auth/register", json=payload)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]


def test_register_rejects_weak_password(client):
    res = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "full_name": "Weak", "password": "short"},
    )
    assert res.status_code == 422


def test_login_returns_token(client):
    payload = {
        "email": "login@example.com",
        "full_name": "Login User",
        "password": "password123",
    }
    client.post("/auth/register", json=payload)
    res = client.post("/auth/login", json=payload)
    assert res.status_code == 200
    assert res.json()["token_type"] == "bearer"


def test_login_wrong_password_rejected(client):
    client.post(
        "/auth/register",
        json={"email": "bad@example.com", "full_name": "Bad", "password": "password123"},
    )
    res = client.post(
        "/auth/login",
        json={"email": "bad@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


def test_login_unknown_email_rejected(client):
    res = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_profile(client, auth_headers):
    res = client.get("/auth/me", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "candidate@example.com"
    assert body["full_name"] == "Test Candidate"
    assert "hashed_password" not in body

import uuid

import requests  # add to requirements.txt if not there

API = "http://localhost:8000"


def unique_email():
    return f"test-{uuid.uuid4()}@example.com"


def test_register_user():
    email = unique_email()
    resp = requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert "id" in data


def test_register_duplicate():
    email = unique_email()
    requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
    resp = requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
    assert resp.status_code == 400


def test_login_success():
    email = unique_email()
    requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
    resp = requests.post(f"{API}/auth/token", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    email = unique_email()
    requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
    resp = requests.post(f"{API}/auth/token", json={"email": email, "password": "wrongpass"})
    assert resp.status_code == 401

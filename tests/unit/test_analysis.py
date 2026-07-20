import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from api.core.security import get_password_hash
from api.main import app
from api.models.user import User


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def user_token(client, db_session):
    user = User(email="analyst@test.com", hashed_password=get_password_hash("test123"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    resp = await client.post(
        "/auth/token", json={"email": "analyst@test.com", "password": "test123"}
    )
    assert resp.status_code == 200, f"Token failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_submit_analysis(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    files = {"file": ("test.csv", "col1,col2\n1,2\n3,4\n", "text/csv")}
    data = {"question": "What is the correlation?"}
    response = await client.post("/v1/analyze", files=files, data=data, headers=headers)
    assert response.status_code == 201, f"Job submission failed: {response.text}"
    job = response.json()
    assert job["status"] == "completed", f"Expected 'completed', got '{job['status']}'"


@pytest.mark.asyncio
async def test_submit_analysis_unauthorized(client):
    files = {"file": ("test.csv", "a,b\n1,2\n", "text/csv")}
    data = {"question": "test"}
    response = await client.post("/v1/analyze", files=files, data=data)
    assert (
        response.status_code == 401
    ), f"Expected 401, got {response.status_code}: {response.text}"


def test_get_job_status_not_found_sync():
    with TestClient(app) as client:
        # Register and login via the API
        email = "notfound2@test.com"
        resp = client.post("/auth/register", json={"email": email, "password": "test"})
        assert resp.status_code == 201
        resp = client.post("/auth/token", json={"email": email, "password": "test"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Request a non‑existent job ID
        import uuid

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/v1/analyze/{fake_id}/status", headers=headers)
        assert resp.status_code == 404

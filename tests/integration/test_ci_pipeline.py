import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register
        r = await client.post(
            "/auth/register", json={"email": "ci@test.com", "password": "ci-pass"}
        )
        assert r.status_code == 201

        # Login
        r = await client.post("/auth/token", json={"email": "ci@test.com", "password": "ci-pass"})
        assert r.status_code == 200
        token = r.json()["access_token"]

        # Submit an analysis job
        files = {"file": ("test.csv", "a,b\n1,2\n3,4\n", "text/csv")}
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/v1/analyze", files=files, data={"question": "corr?"}, headers=headers
        )
        assert r.status_code == 201
        job = r.json()
        assert job["status"] == "completed"  # because Celery runs eagerly

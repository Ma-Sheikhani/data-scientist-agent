import pytest
from httpx import ASGITransport, AsyncClient

from api.core.database import async_session_maker
from api.core.security import get_password_hash
from api.main import app
from api.models.user import User


@pytest.fixture
async def user_token() -> str:
    # Use a unique email each time to avoid collisions
    import uuid

    unique_email = f"analyst_{uuid.uuid4().hex[:8]}@test.com"

    async with async_session_maker() as session:
        user = User(email=unique_email, hashed_password=get_password_hash("test123"))
        session.add(user)
        await session.commit()
        await session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/auth/token",
            json={"email": unique_email, "password": "test123"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        return token


@pytest.mark.asyncio
async def test_submit_analysis(user_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {user_token}"}
        files = {"file": ("test.csv", "col1,col2\n1,2\n3,4\n", "text/csv")}
        data = {"question": "What is the correlation?"}
        response = await client.post("/v1/analyze", files=files, data=data, headers=headers)
        assert response.status_code == 201
        job = response.json()
        assert job["status"] == "pending"
        assert "id" in job

        # Retrieve status
        job_id = job["id"]
        status_resp = await client.get(f"/v1/analyze/{job_id}/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_submit_analysis_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.csv", "a,b\n1,2\n", "text/csv")}
        data = {"question": "test"}
        response = await client.post("/v1/analyze", files=files, data=data)
        assert response.status_code == 401

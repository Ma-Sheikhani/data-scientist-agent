import pytest
from httpx import ASGITransport, AsyncClient

from api.core.database import get_db
from api.main import app


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_full_flow(client, db_session):
    # Register → login → upload → check status
    await client.post("/auth/register", json={"email": "flow@test.com", "password": "flowpass"})
    token_resp = await client.post(
        "/auth/token", json={"email": "flow@test.com", "password": "flowpass"}
    )
    token = token_resp.json()["access_token"]

    files = {"file": ("data.csv", "a,b\n1,2\n3,4\n", "text/csv")}
    resp = await client.post(
        "/v1/analyze",
        files=files,
        data={"question": "corr?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    job = resp.json()
    assert job["status"] == "completed"

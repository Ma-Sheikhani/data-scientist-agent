import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_upload_csv_and_get_result(client):
    # Register
    await client.post("/auth/register", json={"email": "fullflow@test.com", "password": "fullpass"})
    # Login
    token_resp = await client.post(
        "/auth/token", json={"email": "fullflow@test.com", "password": "fullpass"}
    )
    token = token_resp.json()["access_token"]

    # Upload CSV
    files = {"file": ("test.csv", "a,b\n1,2\n3,4\n", "text/csv")}
    data = {"question": "correlation?"}
    resp = await client.post(
        "/v1/analyze", files=files, data=data, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    job = resp.json()
    assert job["status"] == "completed"

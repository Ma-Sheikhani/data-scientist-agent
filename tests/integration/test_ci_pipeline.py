import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_and_login(client):
    await client.post(
        "/auth/register", json={"email": "ci@test.com", "password": "ci-pass"}
    )
    r = await client.post(
        "/auth/token", json={"email": "ci@test.com", "password": "ci-pass"}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()

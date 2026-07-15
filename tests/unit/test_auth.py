import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post(
        "/auth/register", json={"email": "test@example.com", "password": "secret123"}
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate(client):
    # First registration
    r1 = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert r1.status_code == 201, f"First registration failed: {r1.text}"
    # Duplicate
    r2 = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert r2.status_code == 400, f"Expected 400, got {r2.status_code}: {r2.text}"


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/auth/register", json={"email": "login@example.com", "password": "secret123"}
    )
    response = await client.post(
        "/auth/token", json={"email": "login@example.com", "password": "secret123"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register", json={"email": "wrong@example.com", "password": "secret123"}
    )
    response = await client.post(
        "/auth/token", json={"email": "wrong@example.com", "password": "badpass"}
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

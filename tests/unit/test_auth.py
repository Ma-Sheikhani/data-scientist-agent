import pytest
from httpx import ASGITransport, AsyncClient

from api.core.database import get_db
from api.main import app


@pytest.fixture
async def client(db_session):
    # Override FastAPI's get_db with our transactional session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


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
    # First registration should succeed
    response1 = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert response1.status_code == 201, f"First registration failed: {response1.text}"

    # Duplicate must fail
    response2 = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert (
        response2.status_code == 400
    ), f"Expected 400, got {response2.status_code}: {response2.text}"


@pytest.mark.asyncio
async def test_login_success(client):
    # Register a user
    await client.post(
        "/auth/register", json={"email": "login@example.com", "password": "secret123"}
    )
    # Login
    response = await client.post(
        "/auth/token", json={"email": "login@example.com", "password": "secret123"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    assert "access_token" in response.json(), "Token not in response"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    # Register a user
    await client.post(
        "/auth/register", json={"email": "wrong@example.com", "password": "secret123"}
    )
    # Attempt login with wrong password
    response = await client.post(
        "/auth/token", json={"email": "wrong@example.com", "password": "badpass"}
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

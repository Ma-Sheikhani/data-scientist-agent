import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from api.core.database import async_session_maker
from api.main import app
from api.models.user import User


# Use ASGI transport so we don't need a live server
@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Clean the users table before each test
@pytest.fixture(autouse=True)
async def clean_users():
    async with async_session_maker() as session:
        async with session.begin():
            await session.execute(delete(User))


@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post(
        "/auth/register", json={"email": "test-register@example.com", "password": "secret123"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test-register@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate(client):
    # First registration
    await client.post("/auth/register", json={"email": "dup@example.com", "password": "secret123"})
    # Duplicate
    response = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/auth/register", json={"email": "login@example.com", "password": "secret123"}
    )
    response = await client.post(
        "/auth/token", json={"email": "login@example.com", "password": "secret123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register", json={"email": "wrong@example.com", "password": "secret123"}
    )
    response = await client.post(
        "/auth/token", json={"email": "wrong@example.com", "password": "badpass"}
    )
    assert response.status_code == 401

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app

# Constants
TEST_EMAIL = "security-test@example.com"
TEST_PASSWORD = "testpassword123"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def _get_auth_headers(client: AsyncClient) -> dict:
    """Register the test user and return the Authorization header."""
    await client.post(
        "/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    resp = await client.post(
        "/auth/token", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Rate Limiting Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limit_on_analysis():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        csv_content = "a,b\n1,2\n"

        for i in range(6):
            resp = await client.post(
                "/v1/analyze",
                files={"file": ("test.csv", csv_content, "text/csv")},
                data={"question": "test"},
                headers=headers,
            )
            if i < 5:
                assert resp.status_code == 201, f"Request {i + 1} should succeed"
            else:
                assert (
                    resp.status_code == 429
                ), f"Request {i + 1} should be rate limited"


@pytest.mark.asyncio
async def test_rate_limit_on_login():
    """Login endpoint should block after 10 attempts per minute."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": "ratelimit-test@example.com", "password": "testpass"}
        await client.post("/auth/register", json=payload)

        for i in range(11):
            resp = await client.post("/auth/token", json=payload)
            if i < 10:
                assert resp.status_code == 200, f"Request {i + 1} should succeed"
            else:
                assert (
                    resp.status_code == 429
                ), f"Request {i + 1} should be rate limited"


# ---------------------------------------------------------------------------
# PII Redaction (unit test, no server needed)
# ---------------------------------------------------------------------------
def test_redact_pii_from_csv():
    import pandas as pd

    from api.services.pii_service import redact_pii_from_csv

    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob"],
            "contact": ["alice@example.com", "123-456-7890"],
        }
    )
    redacted_df = redact_pii_from_csv(df)
    assert "[REDACTED]" in str(redacted_df.at[0, "contact"])
    assert str(redacted_df.at[0, "contact"]) != "alice@example.com"


# ---------------------------------------------------------------------------
# Content Validation Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mime_validation_rejects_non_csv():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        resp = await client.post(
            "/v1/analyze",
            files={"file": ("fake.csv", png_bytes, "image/png")},
            data={"question": "what"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_file_size_limit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        big_content = "col1,col2\n" + "a,b\n" * (MAX_FILE_SIZE // 4)
        resp = await client.post(
            "/v1/analyze",
            files={"file": ("big.csv", big_content, "text/csv")},
            data={"question": "test"},
            headers=headers,
        )
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_question_injection_blocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        csv_content = "a,b\n1,2\n"
        malicious_questions = ["; DROP TABLE users;", "import os", "eval(1+1)"]
        for q in malicious_questions:
            resp = await client.post(
                "/v1/analyze",
                files={"file": ("test.csv", csv_content, "text/csv")},
                data={"question": q},
                headers=headers,
            )
            assert resp.status_code == 400, f"Question '{q}' should be blocked"
            assert "Invalid characters" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_valid_csv_accepted():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        csv_content = "name,age\nAlice,30\n"
        resp = await client.post(
            "/v1/analyze",
            files={"file": ("valid.csv", csv_content, "text/csv")},
            data={"question": "average age"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert "id" in resp.json()

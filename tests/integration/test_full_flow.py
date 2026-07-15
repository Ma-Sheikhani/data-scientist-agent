import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from workers.tasks import process_analysis  # <-- import the actual task


@pytest.mark.asyncio
async def test_upload_csv_and_get_result():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register
        reg_resp = await client.post(
            "/auth/register", json={"email": "flowtest@example.com", "password": "testpass123"}
        )
        assert reg_resp.status_code == 201

        # 2. Login
        login_resp = await client.post(
            "/auth/token", json={"email": "flowtest@example.com", "password": "testpass123"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload CSV (job created, status 'pending')
        csv_content = "col1,col2\n1,2\n3,4\n5,6\n"
        files = {"file": ("data.csv", csv_content, "text/csv")}
        data = {"question": "Correlate columns"}
        upload_resp = await client.post("/v1/analyze", files=files, data=data, headers=headers)
        assert upload_resp.status_code == 201
        job = upload_resp.json()
        job_id = job["id"]
        assert job["status"] == "pending"

        # 4. Manually run the task (since Celery async/eager doesn't work seamlessly)
        await process_analysis(job_id)

        # 5. Check final job status
        status_resp = await client.get(f"/v1/analyze/{job_id}/status", headers=headers)
        assert status_resp.status_code == 200
        final_job = status_resp.json()
        assert final_job["status"] == "completed"

        # 6. Validate result content
        result = final_job["result"]
        assert result is not None
        assert result["shape"] == [3, 2]
        assert result["columns"] == ["col1", "col2"]

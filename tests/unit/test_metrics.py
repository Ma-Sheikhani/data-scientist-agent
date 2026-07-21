from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text

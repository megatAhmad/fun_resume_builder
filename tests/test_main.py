from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_settings_endpoints():
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "llm_retry_max" in data

    new_config = {"llm_retry_max": 10, "llm_wait_time": 15}
    response = client.post("/api/settings", json=new_config)
    assert response.status_code == 200

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["llm_retry_max"] == 10

def test_list_experiences():
    response = client.get("/api/experiences")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

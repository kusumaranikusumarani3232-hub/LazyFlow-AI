import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "LazyFlow AI"
    assert "Open-Weight AI" in data["model_badge"]

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "LazyFlow AI"
    assert data["model"] == "meta-llama/llama-3.1-8b-instruct"
    assert data["provider"] == "openrouter"

def test_model_status_endpoint():
    response = client.get("/api/model-status")
    assert response.status_code == 200
    data = response.json()
    assert data["open_weight"] is True
    assert data["model_name"] == "meta-llama/llama-3.1-8b-instruct"
    assert "Zero file content transmission" in data["privacy_policy"]

def test_organize_empty_files_rejected():
    response = client.post("/api/organize-metadata", json={"files": []})
    assert response.status_code == 400
    assert "No files provided" in response.json()["detail"]

def test_organize_batch_size_limit():
    fake_files = [
        {"id": str(i), "filename": f"file_{i}.txt", "size": 100}
        for i in range(settings.MAX_BATCH_FILES + 5)
    ]
    response = client.post("/api/organize-metadata", json={"files": fake_files})
    assert response.status_code == 400
    assert "limit exceeded" in response.json()["detail"]

def test_download_zip_invalid_session():
    response = client.post(
        "/api/download-zip",
        json={
            "session_id": "non_existent_session_99999",
            "items": [
                {
                    "id": "1",
                    "original_filename": "test.txt",
                    "folder": "Documents",
                    "category": "Documents",
                    "suggested_filename": "test.txt",
                    "reason": "test",
                    "excluded": False,
                    "user_modified": False
                }
            ]
        }
    )
    assert response.status_code == 404

def test_sample_files_endpoints():
    response = client.get("/api/sample-files")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) > 0
    first_file = samples[0]["name"]
    file_response = client.get(f"/api/sample-files/{first_file}")
    assert file_response.status_code == 200
    assert len(file_response.content) > 0

def test_cors_configured_origin():
    # Test with origin that matches configured localhost origin
    origin = "http://localhost:5173"
    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


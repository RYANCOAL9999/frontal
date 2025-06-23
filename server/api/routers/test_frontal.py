import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from server.api.routers import frontal
from models.crop_model import SubmitPayload, Landmark, JobResponse, JobStatusResponse
from fastapi import FastAPI

# Patch dependencies and FastAPI app for testing
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(frontal.router)
    return TestClient(app)

@pytest.fixture
def mock_db():
    with patch("server.api.routers.frontal.get_db") as mock:
        yield mock

@pytest.fixture
def mock_sessionlocal():
    with patch("server.api.routers.frontal.SessionLocal") as mock:
        yield mock

@pytest.fixture
def sample_payload():
    return {
        "image": "base64image",
        "landmarks": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        "segmentation_map": "base64seg"
    }

@pytest.fixture
def sample_db_job():
    mock_job = MagicMock()
    mock_job.job_id = "test-job-id"
    mock_job.status = "completed"
    mock_job.svg_base64 = "svgdata"
    mock_job.mask_contours_json = "contours"
    mock_job.image_base64 = "base64image"
    mock_job.landmarks_json = [{"x": 1, "y": 2}]
    mock_job.segmentation_map_base64 = "base64seg"
    mock_job.created_at = datetime.utcnow()
    return mock_job

def test_submit_frontal_crop_new_job(client, mock_db, sample_payload):
    # Simulate no existing job
    db = MagicMock()
    db.query().filter().first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    mock_db.return_value = db

    # Patch job_queue to avoid actual async queue
    with patch("server.api.routers.frontal.job_queue.put", new_callable=AsyncMock):
        response = client.post("/crop/submit", json=sample_payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

def test_submit_frontal_crop_existing_job(client, mock_db, sample_payload, sample_db_job):
    # Simulate existing completed job
    db = MagicMock()
    db.query().filter().first.return_value = sample_db_job
    mock_db.return_value = db

    response = client.post("/crop/submit", json=sample_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-job-id"
    assert data["status"] == "completed"

def test_submit_frontal_crop_db_error(client, mock_db, sample_payload):
    db = MagicMock()
    db.query().filter.side_effect = Exception("DB error")
    db.rollback = MagicMock()
    mock_db.return_value = db

    response = client.post("/crop/submit", json=sample_payload)
    assert response.status_code == 500
    assert "error" in response.text or "An error occurred" in response.text

def test_get_crop_job_status_found(client, mock_db, mock_sessionlocal, sample_db_job):
    # Patch the LRU cache function to return a job dict
    job_dict = {
        "id": sample_db_job.job_id,
        "status": sample_db_job.status,
        "svg": sample_db_job.svg_base64,
        "mask_contours": sample_db_job.mask_contours_json,
        "error": None,
    }
    with patch("server.api.routers.frontal._get_job_data_from_db_cached", return_value=job_dict):
        response = client.get(f"/crop/status/{sample_db_job.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_db_job.job_id
        assert data["status"] == "completed"
        assert data["svg"] == "svgdata"
        assert data["mask_contours"] == "contours"
        assert data["error"] is None

def test_get_crop_job_status_not_found(client, mock_db, mock_sessionlocal):
    with patch("server.api.routers.frontal._get_job_data_from_db_cached", return_value=None):
        response = client.get("/crop/status/nonexistent-job")
        assert response.status_code == 404
        assert "not found" in response.text.lower()
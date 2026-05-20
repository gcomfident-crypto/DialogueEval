from __future__ import annotations

from threading import Event

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api import service
from apps.api.service import _format_display_time


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assets_endpoint_returns_list() -> None:
    client = TestClient(app)
    response = client.get("/assets")

    assert response.status_code == 200
    assert isinstance(response.json()["assets"], list)


def test_display_time_converts_utc_to_shanghai() -> None:
    assert _format_display_time("2026-05-17T11:57:11.788277+00:00") == "2026年05月17日 19:57:11"


def test_cancel_evaluation_job_marks_running_job_as_cancelling() -> None:
    client = TestClient(app)
    job_id = "test_cancel_job"
    with service._evaluation_jobs_lock:
        service._evaluation_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "stage": "生成测试设计",
            "message": "running",
            "percent": 10,
            "created_at": "",
            "updated_at": "",
            "started_at": "",
            "completed_at": "",
            "error": "",
            "result": None,
            "details": {},
            "steps": service._default_evaluation_steps(),
        }
        service._evaluation_cancel_events[job_id] = Event()
    try:
        response = client.post(f"/evaluations/jobs/{job_id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelling"
        assert data["details"]["cancel_requested"] is True
        assert service._evaluation_cancel_events[job_id].is_set()
    finally:
        with service._evaluation_jobs_lock:
            service._evaluation_jobs.pop(job_id, None)
            service._evaluation_cancel_events.pop(job_id, None)

"""End-to-end API tests: submit -> placeholder processing -> download.

TestClient runs background tasks synchronously, so a submitted job is fully
processed by the time the response returns.
"""

from __future__ import annotations

import io
from pathlib import Path

from app.schemas import OutputSize, UpscaleMode

from .conftest import auth, make_video_bytes, probe_bytes, requires_ffmpeg

pytestmark = requires_ffmpeg


def _submit(client, data: bytes, output: str = "2x", token: str = "approved", **form):
    return client.post(
        "/v1/jobs",
        files={"video": ("clip.mp4", data, "video/mp4")},
        data={"output": output, **form},
        headers=auth(token),
    )


def test_health_requires_no_auth(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_jobs_require_auth(client):
    assert client.get("/v1/jobs").status_code == 401
    assert client.get("/v1/jobs", headers=auth("bogus")).status_code == 401


def test_unapproved_account_rejected(client):
    resp = _submit(client, make_video_bytes(), token="other")
    assert resp.status_code == 403


def test_submit_processes_and_downloads(client):
    resp = _submit(client, make_video_bytes(duration=1.0, size=(64, 48), fps=10))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["frames_total"] == 10
    job_id = body["job_id"]

    status = client.get(f"/v1/jobs/{job_id}", headers=auth()).json()
    assert status["status"] == "completed", status
    assert status["result_available"] is True
    assert (status["width"], status["height"]) == (128, 96)
    assert status["frames_done"] == status["frames_total"] == 10
    assert status["progress"] == 100

    result = client.get(f"/v1/jobs/{job_id}/result", headers=auth())
    assert result.status_code == 200
    assert result.headers["content-type"] == "video/mp4"
    info = probe_bytes(result.content)
    assert (info.width, info.height) == (128, 96)
    assert info.codec == "h264"

    preview = client.get(f"/v1/jobs/{job_id}/preview", headers=auth())
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    from PIL import Image

    poster = Image.open(io.BytesIO(preview.content))
    assert poster.size == (128, 96)


def test_audio_is_preserved(client):
    resp = _submit(client, make_video_bytes(duration=1.0, audio=True))
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]
    result = client.get(f"/v1/jobs/{job_id}/result", headers=auth())
    info = probe_bytes(result.content)
    assert info.has_audio is True
    assert info.audio_codec == "aac"


def test_invalid_output_rejected(client):
    resp = _submit(client, make_video_bytes(), output="8k")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_mode_rejected(client):
    resp = _submit(client, make_video_bytes(), mode="ultra")
    assert resp.status_code == 400


def test_too_long_clip_rejected(client):
    # Suite settings cap duration at 10s.
    resp = _submit(client, make_video_bytes(duration=12.0))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VIDEO_TOO_LONG"


def test_idempotency_key_reuses_job(client):
    data = make_video_bytes()
    headers = {**auth(), "Idempotency-Key": "abc-123"}
    first = client.post(
        "/v1/jobs",
        files={"video": ("clip.mp4", data, "video/mp4")},
        data={"output": "2x"},
        headers=headers,
    )
    second = client.post(
        "/v1/jobs",
        files={"video": ("clip.mp4", data, "video/mp4")},
        data={"output": "2x"},
        headers=headers,
    )
    assert first.json()["job_id"] == second.json()["job_id"]


def test_listing_and_ownership(client):
    job_id = _submit(client, make_video_bytes()).json()["job_id"]

    listing = client.get("/v1/jobs", headers=auth()).json()["jobs"]
    assert any(j["job_id"] == job_id for j in listing)

    # Another (approved=False) account never gets in; but even a hypothetical
    # other owner must see 404, not 403, for someone else's job.
    assert client.get(f"/v1/jobs/{job_id}", headers=auth("other")).status_code in {403, 404}


def test_delete_removes_job_files(client, settings):
    job_id = _submit(client, make_video_bytes()).json()["job_id"]
    assert client.delete(f"/v1/jobs/{job_id}", headers=auth()).status_code == 204
    assert client.get(f"/v1/jobs/{job_id}/result", headers=auth()).status_code in {404, 410}
    data_dir = Path(settings.data_dir)
    leftovers = [p for p in data_dir.rglob(f"*{job_id}*")]
    assert leftovers == []


def test_failed_job_surfaces_error(app):
    """A corrupt stored source exercises the worker's failure path."""
    from app.storage import source_path

    st = app.state
    record = st.job_service.create_job(
        owner_sub="sub-approved-123",
        owner_email="approved@example.com",
        mode=UpscaleMode.NATURAL,
        output=OutputSize.X2,
        duration_seconds=1.0,
        fps=10.0,
        frames_total=10,
    )
    st.files.write(source_path(record.owner_sub, record.job_id), b"corrupt")
    st.processor.process(record.job_id)

    failed = st.job_service.get(record.job_id)
    assert failed.status.value == "failed"
    assert failed.error_code is not None


def test_result_before_completion_404s(settings, tmp_path):
    """A queued (never processed) job has no downloadable result."""

    class NoopProcessor:
        def process(self, job_id: str) -> None:
            return None

    from app.main import create_app
    from app.storage import InMemoryMetadataStore, LocalFileStore
    from fastapi.testclient import TestClient

    from .conftest import FakeVerifier

    noop_app = create_app(
        settings=settings,
        verifier=FakeVerifier(),
        files=LocalFileStore(str(tmp_path / "noop-data")),
        meta=InMemoryMetadataStore(),
        processor=NoopProcessor(),
    )
    noop_client = TestClient(noop_app)
    resp = _submit(noop_client, make_video_bytes())
    job_id = resp.json()["job_id"]
    status = noop_client.get(f"/v1/jobs/{job_id}", headers=auth()).json()
    assert status["status"] == "queued"
    assert noop_client.get(f"/v1/jobs/{job_id}/result", headers=auth()).status_code == 404

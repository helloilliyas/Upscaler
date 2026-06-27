"""End-to-end API tests against the assembled app (background tasks run inline)."""

from __future__ import annotations

from tests.conftest import auth, make_image_bytes, make_mask_bytes


def _submit(client, token="approved", mode="natural", output="2x", headers=None, **files_extra):
    files = {"photo": ("p.jpg", make_image_bytes((64, 48)), "image/jpeg")}
    files.update(files_extra)
    h = auth(token)
    if headers:
        h.update(headers)
    return client.post("/v1/jobs", headers=h, data={"mode": mode, "output": output}, files=files)


# --- health / me ---------------------------------------------------------


def test_health_needs_no_auth(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me_requires_token(client):
    assert client.get("/v1/me").status_code == 401


def test_me_rejects_unapproved_account(client):
    r = client.get("/v1/me", headers=auth("other"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_ALLOWED"


def test_me_rejects_unverified_email(client):
    assert client.get("/v1/me", headers=auth("unverified")).status_code == 403


def test_me_approved(client):
    r = client.get("/v1/me", headers=auth("approved"))
    assert r.status_code == 200 and r.json()["authorized"] is True


# --- submit / status / result -------------------------------------------


def test_submit_then_complete_then_download(client):
    r = _submit(client, output="2x")
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]
    assert r.json()["status"] == "queued"

    status = client.get(f"/v1/jobs/{job_id}", headers=auth()).json()
    assert status["status"] == "completed"
    assert (status["width"], status["height"]) == (128, 96)  # 64x48 at 2x
    assert status["result_available"] is True
    assert status["fidelity"] == "high"

    result = client.get(f"/v1/jobs/{job_id}/result", headers=auth())
    assert result.status_code == 200
    assert result.headers["content-type"] == "image/jpeg"
    assert "attachment" in result.headers["content-disposition"]
    assert len(result.content) > 0

    preview = client.get(f"/v1/jobs/{job_id}/preview", headers=auth())
    assert preview.status_code == 200


def test_submit_requires_auth(client):
    r = client.post(
        "/v1/jobs",
        data={"mode": "natural", "output": "2x"},
        files={"photo": ("p.jpg", make_image_bytes(), "image/jpeg")},
    )
    assert r.status_code == 401


def test_invalid_mode_and_output_rejected(client):
    assert _submit(client, mode="bogus").status_code == 400
    assert _submit(client, output="16k").status_code == 400


def test_unsupported_upload_rejected(client):
    import io

    from PIL import Image

    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    r = client.post(
        "/v1/jobs",
        headers=auth(),
        data={"mode": "natural", "output": "2x"},
        files={"photo": ("p.gif", gif.getvalue(), "image/gif")},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_submit_with_matching_mask(client):
    r = _submit(
        client,
        mode="restore",
        output="2x",
        repair_mask=("mask.png", make_mask_bytes((64, 48)), "image/png"),
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]
    assert client.get(f"/v1/jobs/{job_id}", headers=auth()).json()["status"] == "completed"


def test_submit_with_mismatched_mask_rejected(client):
    r = _submit(
        client,
        mode="restore",
        repair_mask=("mask.png", make_mask_bytes((10, 10)), "image/png"),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "MASK_SIZE_MISMATCH"


# --- ownership / listing / deletion -------------------------------------


def test_other_account_cannot_access_job(client):
    job_id = _submit(client, token="approved").json()["job_id"]
    # 'other' is a different, unapproved account -> 403 at the auth gate.
    assert client.get(f"/v1/jobs/{job_id}", headers=auth("other")).status_code == 403


def test_list_jobs_returns_owned(client):
    _submit(client)
    _submit(client)
    jobs = client.get("/v1/jobs", headers=auth()).json()["jobs"]
    assert len(jobs) == 2


def test_delete_job_removes_result(client):
    job_id = _submit(client).json()["job_id"]
    assert client.delete(f"/v1/jobs/{job_id}", headers=auth()).status_code == 204
    # Result blob is gone; downloading now 404s (job cancelled, no result).
    assert client.get(f"/v1/jobs/{job_id}/result", headers=auth()).status_code == 404


def test_unknown_job_is_404(client):
    assert client.get("/v1/jobs/job_does_not_exist", headers=auth()).status_code == 404

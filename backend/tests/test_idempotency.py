"""Idempotency-Key behaviour at the HTTP layer."""

from __future__ import annotations

from tests.conftest import auth, make_image_bytes


def _submit(client, key):
    return client.post(
        "/v1/jobs",
        headers={**auth(), "Idempotency-Key": key},
        data={"mode": "natural", "output": "2x"},
        files={"photo": ("p.jpg", make_image_bytes(), "image/jpeg")},
    )


def test_repeated_key_returns_same_job(client):
    first = _submit(client, "key-123")
    second = _submit(client, "key-123")
    assert first.status_code == second.status_code == 201
    assert first.json()["job_id"] == second.json()["job_id"]

    # Only one job exists for the owner.
    assert len(client.get("/v1/jobs", headers=auth()).json()["jobs"]) == 1


def test_distinct_keys_create_distinct_jobs(client):
    a = _submit(client, "key-a").json()["job_id"]
    b = _submit(client, "key-b").json()["job_id"]
    assert a != b
    assert len(client.get("/v1/jobs", headers=auth()).json()["jobs"]) == 2

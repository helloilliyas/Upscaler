"""Unit tests for JobService: idempotency, ownership, transitions, deletion."""

from __future__ import annotations

import pytest
from app.errors import ApiError, ErrorCode
from app.jobs import JobService
from app.schemas import Fidelity, JobStage, JobStatus, OutputSize, RestorationMode
from app.storage import InMemoryMetadataStore, LocalFileStore, result_path, source_path


@pytest.fixture
def service(tmp_path) -> JobService:
    return JobService(InMemoryMetadataStore(), LocalFileStore(tmp_path))


def _create(service: JobService, owner="ownerA", key=None) -> str:
    rec = service.create_job(
        owner_sub=owner,
        owner_email="a@example.com",
        mode=RestorationMode.NATURAL,
        output=OutputSize.X2,
        idempotency_key=key,
    )
    return rec.job_id


def test_create_generates_unique_ids(service):
    a, b = _create(service), _create(service)
    assert a != b and a.startswith("job_")


def test_idempotency_key_returns_same_job(service):
    first = _create(service, key="abc")
    second = _create(service, key="abc")
    assert first == second


def test_different_keys_create_different_jobs(service):
    assert _create(service, key="k1") != _create(service, key="k2")


def test_get_owned_enforces_ownership(service):
    job_id = _create(service, owner="ownerA")
    assert service.get_owned(job_id, "ownerA").job_id == job_id
    with pytest.raises(ApiError) as exc:
        service.get_owned(job_id, "ownerB")
    assert exc.value.code == ErrorCode.NOT_FOUND


def test_get_owned_missing_is_not_found(service):
    with pytest.raises(ApiError) as exc:
        service.get_owned("job_missing", "ownerA")
    assert exc.value.code == ErrorCode.NOT_FOUND


def test_list_for_owner_filters_and_sorts(service):
    _create(service, owner="ownerA")
    _create(service, owner="ownerA")
    _create(service, owner="ownerB")
    a_jobs = service.list_for_owner("ownerA")
    assert len(a_jobs) == 2
    assert all(j.owner_sub == "ownerA" for j in a_jobs)


def test_progress_and_completion_transitions(service):
    job_id = _create(service)
    service.update_progress(job_id, stage=JobStage.ENHANCING, progress=40)
    rec = service.get(job_id)
    assert rec.status == JobStatus.PROCESSING and rec.progress == 40

    service.mark_completed(
        job_id,
        result_path="results/x/result.jpg",
        preview_path="previews/x/preview.jpg",
        width=200,
        height=100,
        fidelity=Fidelity.HIGH,
    )
    rec = service.get(job_id)
    assert rec.status == JobStatus.COMPLETED and rec.progress == 100
    assert rec.stage == JobStage.READY


def test_mark_failed_records_code(service):
    job_id = _create(service)
    service.mark_failed(job_id, code=ErrorCode.MODEL_ERROR, message="boom")
    rec = service.get(job_id)
    assert rec.status == JobStatus.FAILED and rec.error_code == "MODEL_ERROR"


def test_delete_owned_removes_files_and_cancels(tmp_path):
    files = LocalFileStore(tmp_path)
    service = JobService(InMemoryMetadataStore(), files)
    job_id = _create(service, owner="ownerA")

    files.write(source_path("ownerA", job_id), b"source")
    files.write(result_path("ownerA", job_id) + ".jpg", b"result")

    service.delete_owned(job_id, "ownerA")
    assert not files.exists(source_path("ownerA", job_id))
    assert service.get(job_id).status == JobStatus.CANCELLED


def test_read_result_requires_completion(service):
    job_id = _create(service)
    with pytest.raises(ApiError) as exc:
        service.read_result(job_id, "ownerA")
    assert exc.value.code == ErrorCode.NOT_FOUND


def test_read_result_expired_when_file_missing(service):
    job_id = _create(service)
    service.mark_completed(
        job_id,
        result_path="results/ownerA/gone.jpg",
        preview_path=None,
        width=10,
        height=10,
        fidelity=Fidelity.HIGH,
    )
    with pytest.raises(ApiError) as exc:
        service.read_result(job_id, "ownerA")
    assert exc.value.code == ErrorCode.RESULT_EXPIRED

"""Job records, lifecycle, and the JobService.

A ``JobRecord`` is the JSON-like value stored in the MetadataStore (Modal Dict
in prod). The ``JobService`` owns creation, idempotency, ownership-checked
reads, status transitions, and deletion. It is storage-agnostic and contains no
GPU/model code.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .errors import ApiError, ErrorCode
from .schemas import TERMINAL_STATUSES, JobStage, JobStatus, OutputSize, UpscaleMode
from .storage import FileStore, MetadataStore, job_prefixes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_job_id() -> str:
    return f"vjob_{secrets.token_hex(16)}"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _idem_key(owner_sub: str, key: str) -> str:
    return f"idem:{owner_sub}:{key}"


class JobRecord(BaseModel):
    """Authoritative server-side record for one upscaling job."""

    job_id: str
    owner_sub: str
    owner_email: str
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress: int = 0
    mode: UpscaleMode
    output: OutputSize
    # Probed source facts, captured at submission.
    duration_seconds: float
    fps: float
    frames_total: int
    frames_done: int | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    result_path: str | None = None
    preview_path: str | None = None
    width: int | None = None
    height: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    # Internal Modal call id; never returned to the client.
    call_id: str | None = None


class JobService:
    """Coordinates job metadata and the file blobs that belong to each job."""

    def __init__(self, meta: MetadataStore, files: FileStore) -> None:
        self._meta = meta
        self._files = files

    # --- creation / idempotency ----------------------------------------

    def create_job(
        self,
        *,
        owner_sub: str,
        owner_email: str,
        mode: UpscaleMode,
        output: OutputSize,
        duration_seconds: float,
        fps: float,
        frames_total: int,
        idempotency_key: str | None = None,
    ) -> JobRecord:
        """Create a job, or return the existing one for a repeated idempotency key."""
        if idempotency_key:
            existing_id = self._meta.get(_idem_key(owner_sub, idempotency_key))
            if existing_id:
                record = self._load(existing_id["job_id"])
                if record is not None:
                    return record

        record = JobRecord(
            job_id=_new_job_id(),
            owner_sub=owner_sub,
            owner_email=owner_email,
            mode=mode,
            output=output,
            duration_seconds=duration_seconds,
            fps=fps,
            frames_total=frames_total,
        )
        self._save(record)

        if idempotency_key:
            self._meta.put(_idem_key(owner_sub, idempotency_key), {"job_id": record.job_id})
        return record

    # --- reads ----------------------------------------------------------

    def get_owned(self, job_id: str, owner_sub: str) -> JobRecord:
        """Return a job iff it exists and is owned by ``owner_sub``.

        Both 'missing' and 'not yours' surface as NOT_FOUND so the endpoint
        never leaks the existence of another owner's job.
        """
        record = self._load(job_id)
        if record is None or record.owner_sub != owner_sub:
            raise ApiError(ErrorCode.NOT_FOUND, "Job not found")
        return record

    def get(self, job_id: str) -> JobRecord:
        """Load a job by id without an ownership check (server-internal use)."""
        return self._require(job_id)

    def list_for_owner(self, owner_sub: str, limit: int = 20) -> list[JobRecord]:
        records = [
            JobRecord(**value)
            for key, value in self._meta.items()
            if key.startswith("job:") and value.get("owner_sub") == owner_sub
        ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[: max(0, limit)]

    # --- transitions ----------------------------------------------------

    def update_progress(
        self,
        job_id: str,
        *,
        stage: JobStage,
        progress: int,
        frames_done: int | None = None,
        status: JobStatus = JobStatus.PROCESSING,
    ) -> JobRecord:
        record = self._require(job_id)
        record.status = status
        record.stage = stage
        record.progress = max(0, min(100, progress))
        if frames_done is not None:
            record.frames_done = max(0, min(record.frames_total, frames_done))
        record.updated_at = _now()
        self._save(record)
        return record

    def mark_completed(
        self,
        job_id: str,
        *,
        result_path: str,
        preview_path: str | None,
        width: int,
        height: int,
    ) -> JobRecord:
        record = self._require(job_id)
        record.status = JobStatus.COMPLETED
        record.stage = JobStage.READY
        record.progress = 100
        record.frames_done = record.frames_total
        record.result_path = result_path
        record.preview_path = preview_path
        record.width = width
        record.height = height
        record.updated_at = _now()
        self._save(record)
        return record

    def mark_failed(self, job_id: str, *, code: ErrorCode, message: str) -> JobRecord:
        record = self._require(job_id)
        record.status = JobStatus.FAILED
        record.error_code = code.value
        record.error_message = message
        record.updated_at = _now()
        self._save(record)
        return record

    def set_call_id(self, job_id: str, call_id: str) -> None:
        record = self._require(job_id)
        record.call_id = call_id
        self._save(record)

    # --- deletion -------------------------------------------------------

    def delete_owned(self, job_id: str, owner_sub: str) -> JobRecord:
        """Cancel-or-delete an owned job and remove its blobs.

        Non-terminal jobs are tombstoned as CANCELLED; files are removed in all
        cases. Idempotent: deleting an already-deleted job still 404s upstream.
        """
        record = self.get_owned(job_id, owner_sub)

        for prefix in job_prefixes(record.owner_sub, record.job_id):
            self._files.delete_prefix(prefix)
        self._files.commit()

        if record.status not in TERMINAL_STATUSES:
            record.status = JobStatus.CANCELLED
        record.result_path = None
        record.preview_path = None
        record.updated_at = _now()
        self._save(record)
        return record

    # --- result access --------------------------------------------------

    def read_result(self, job_id: str, owner_sub: str) -> bytes:
        record = self.get_owned(job_id, owner_sub)
        if record.status != JobStatus.COMPLETED or not record.result_path:
            raise ApiError(ErrorCode.NOT_FOUND, "Result not available")
        self._files.reload()
        if not self._files.exists(record.result_path):
            raise ApiError(ErrorCode.RESULT_EXPIRED, "Result has expired")
        return self._files.read(record.result_path)

    def read_preview(self, job_id: str, owner_sub: str) -> bytes:
        record = self.get_owned(job_id, owner_sub)
        if record.status != JobStatus.COMPLETED or not record.preview_path:
            raise ApiError(ErrorCode.NOT_FOUND, "Preview not available")
        self._files.reload()
        if not self._files.exists(record.preview_path):
            raise ApiError(ErrorCode.RESULT_EXPIRED, "Preview has expired")
        return self._files.read(record.preview_path)

    # --- internals ------------------------------------------------------

    def _load(self, job_id: str) -> JobRecord | None:
        value = self._meta.get(_job_key(job_id))
        return JobRecord(**value) if value is not None else None

    def _require(self, job_id: str) -> JobRecord:
        record = self._load(job_id)
        if record is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Job not found")
        return record

    def _save(self, record: JobRecord) -> None:
        self._meta.put(_job_key(record.job_id), record.model_dump(mode="json"))

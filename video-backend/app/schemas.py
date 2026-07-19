"""Enums and Pydantic response models for the v1 API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class UpscaleMode(str, Enum):
    """Only NATURAL ships in v1; the enum keeps the wire format future-proof."""

    NATURAL = "natural"


class OutputSize(str, Enum):
    """2x / 4x are capped inside a 4K box; there is deliberately no 8K video."""

    X2 = "2x"
    X4 = "4x"
    K4 = "4k"


class JobStatus(str, Enum):
    """Coarse job status returned to the client."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class JobStage(str, Enum):
    """Fine-grained lifecycle stage (drives the processing screen copy)."""

    CREATED = "created"
    UPLOADING = "uploading"
    QUEUED = "queued"
    VALIDATING = "validating"
    DECODING = "decoding"
    ENHANCING = "enhancing"
    ENCODING = "encoding"
    READY = "ready"


TERMINAL_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}
)

# Human-readable copy for each stage, surfaced as the status "message".
STAGE_MESSAGES: dict[JobStage, str] = {
    JobStage.CREATED: "Created",
    JobStage.UPLOADING: "Uploading",
    JobStage.QUEUED: "Queued",
    JobStage.VALIDATING: "Validating",
    JobStage.DECODING: "Reading video",
    JobStage.ENHANCING: "Upscaling frames",
    JobStage.ENCODING: "Encoding video",
    JobStage.READY: "Ready",
}


# --- Response models -----------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class MeResponse(BaseModel):
    email: str
    authorized: bool


class SubmitJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    mode: UpscaleMode
    output: OutputSize
    duration_seconds: float
    frames_total: int
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: JobStage
    progress: int = Field(ge=0, le=100)
    message: str | None = None
    result_available: bool = False
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    fps: float | None = None
    frames_total: int | None = None
    frames_done: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class JobSummary(BaseModel):
    job_id: str
    status: JobStatus
    mode: UpscaleMode
    output: OutputSize
    duration_seconds: float | None = None
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    jobs: list[JobSummary]


class ErrorResponse(BaseModel):
    class _Error(BaseModel):
        code: str
        message: str

    error: _Error

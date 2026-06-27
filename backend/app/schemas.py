"""Enums and Pydantic response models for the v1 API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RestorationMode(str, Enum):
    NATURAL = "natural"
    RESTORE = "restore"
    ULTRA = "ultra"


class OutputSize(str, Enum):
    X2 = "2x"
    X4 = "4x"
    K4 = "4k"
    K8 = "8k"


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
    PREPROCESSING = "preprocessing"
    REPAIRING = "repairing"
    ENHANCING = "enhancing"
    RESTORING_FACES = "restoring_faces"
    GENERATING_DETAIL = "generating_detail"
    UPSCALING = "upscaling"
    ENCODING = "encoding"
    READY = "ready"


class Fidelity(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    GENERATIVE = "generative"


TERMINAL_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}
)

# Human-readable copy for each stage, surfaced as the status "message".
STAGE_MESSAGES: dict[JobStage, str] = {
    JobStage.CREATED: "Created",
    JobStage.UPLOADING: "Uploading",
    JobStage.QUEUED: "Queued",
    JobStage.VALIDATING: "Validating",
    JobStage.PREPROCESSING: "Preparing image",
    JobStage.REPAIRING: "Repairing damage",
    JobStage.ENHANCING: "Enhancing photo",
    JobStage.RESTORING_FACES: "Restoring faces",
    JobStage.GENERATING_DETAIL: "Generating detail",
    JobStage.UPSCALING: "Building high-resolution result",
    JobStage.ENCODING: "Encoding",
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
    mode: RestorationMode
    output: OutputSize
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
    fidelity: Fidelity | None = None
    generated_detail: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class JobSummary(BaseModel):
    job_id: str
    status: JobStatus
    mode: RestorationMode
    output: OutputSize
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    jobs: list[JobSummary]


class ErrorResponse(BaseModel):
    class _Error(BaseModel):
        code: str
        message: str

    error: _Error

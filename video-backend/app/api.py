"""v1 API routes.

Dependencies pull shared components (settings, verifier, job service,
processor) off ``request.app.state`` so the app can be assembled with test
doubles in ``create_app``.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Form, Header, Request, UploadFile
from fastapi.responses import Response

from .auth import verify_and_authorize
from .errors import ApiError, ErrorCode
from .jobs import JobService
from .schemas import (
    STAGE_MESSAGES,
    HealthResponse,
    JobListResponse,
    JobStatusResponse,
    JobSummary,
    MeResponse,
    OutputSize,
    SubmitJobResponse,
    UpscaleMode,
)
from .storage import source_path
from .validation import validate_video_bytes

router = APIRouter(prefix="/v1")


# --- shared accessors ----------------------------------------------------


def _state(request: Request):
    return request.app.state


def _authorize(request: Request, authorization: str | None) -> dict:
    st = _state(request)
    return verify_and_authorize(authorization, st.verifier, st.settings)


def _jobs(request: Request) -> JobService:
    return _state(request).job_service


# --- routes --------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(version=_state(request).settings.api_version)


@router.get("/me", response_model=MeResponse)
def me(request: Request, authorization: str | None = Header(default=None)) -> MeResponse:
    claims = _authorize(request, authorization)
    return MeResponse(email=claims["email"], authorized=True)


@router.post("/jobs", response_model=SubmitJobResponse, status_code=201)
async def submit_job(
    request: Request,
    background: BackgroundTasks,
    video: UploadFile,
    output: str = Form(...),
    mode: str = Form(default=UpscaleMode.NATURAL.value),
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SubmitJobResponse:
    claims = _authorize(request, authorization)
    st = _state(request)
    settings = st.settings
    jobs = _jobs(request)

    parsed_mode = _parse_enum(mode, UpscaleMode, "mode")
    parsed_output = _parse_enum(output, OutputSize, "output")

    video_bytes = await video.read()
    info = validate_video_bytes(
        video_bytes,
        max_bytes=settings.max_upload_bytes,
        max_seconds=settings.max_duration_seconds,
        max_pixels=settings.max_input_pixels,
        max_fps=settings.max_fps,
    )

    record = jobs.create_job(
        owner_sub=claims["sub"],
        owner_email=claims["email"],
        mode=parsed_mode,
        output=parsed_output,
        duration_seconds=info.duration_seconds,
        fps=info.fps,
        frames_total=info.frames_estimate,
        idempotency_key=idempotency_key,
    )

    # The source is stored byte-for-byte: no re-encode, no quality loss. Any
    # container metadata is dropped when the result is re-muxed, and the
    # source itself is retention-deleted.
    files = st.files
    files.write(source_path(record.owner_sub, record.job_id), video_bytes)
    files.commit()

    # Local async: run the placeholder processor in the background. In Modal
    # this is replaced by a GPU worker .spawn() whose call id is stored.
    jobs.set_call_id(record.job_id, f"local_{secrets.token_hex(8)}")
    background.add_task(st.processor.process, record.job_id)

    return SubmitJobResponse(
        job_id=record.job_id,
        status=record.status,
        mode=record.mode,
        output=record.output,
        duration_seconds=record.duration_seconds,
        frames_total=record.frames_total,
        created_at=record.created_at,
    )


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    request: Request,
    limit: int = 20,
    authorization: str | None = Header(default=None),
) -> JobListResponse:
    claims = _authorize(request, authorization)
    records = _jobs(request).list_for_owner(claims["sub"], limit=limit)
    return JobListResponse(
        jobs=[
            JobSummary(
                job_id=r.job_id,
                status=r.status,
                mode=r.mode,
                output=r.output,
                duration_seconds=r.duration_seconds,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    request: Request,
    job_id: str,
    authorization: str | None = Header(default=None),
) -> JobStatusResponse:
    claims = _authorize(request, authorization)
    r = _jobs(request).get_owned(job_id, claims["sub"])
    return JobStatusResponse(
        job_id=r.job_id,
        status=r.status,
        stage=r.stage,
        progress=r.progress,
        message=STAGE_MESSAGES.get(r.stage),
        result_available=r.result_path is not None and r.status.value == "completed",
        width=r.width,
        height=r.height,
        duration_seconds=r.duration_seconds,
        fps=r.fps,
        frames_total=r.frames_total,
        frames_done=r.frames_done,
        error_code=r.error_code,
        error_message=r.error_message,
    )


@router.get("/jobs/{job_id}/result")
def download_result(
    request: Request,
    job_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    claims = _authorize(request, authorization)
    data = _jobs(request).read_result(job_id, claims["sub"])
    return Response(
        content=data,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.mp4"'},
    )


@router.get("/jobs/{job_id}/preview")
def download_preview(
    request: Request,
    job_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    claims = _authorize(request, authorization)
    data = _jobs(request).read_preview(job_id, claims["sub"])
    return Response(content=data, media_type="image/jpeg")


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    request: Request,
    job_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    claims = _authorize(request, authorization)
    _jobs(request).delete_owned(job_id, claims["sub"])
    return Response(status_code=204)


# --- helpers -------------------------------------------------------------


def _parse_enum(value: str, enum_cls, field: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ApiError(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid {field} '{value}'. Allowed: {allowed}",
        ) from exc

"""v1 API routes.

Dependencies pull shared components (settings, verifier, job service, processor)
off ``request.app.state`` so the app can be assembled with test doubles in
``create_app``.
"""

from __future__ import annotations

import io
import secrets

from fastapi import APIRouter, BackgroundTasks, Form, Header, Request, UploadFile
from fastapi.responses import Response

from .auth import verify_and_authorize
from .errors import ApiError, ErrorCode
from .image_validation import validate_and_load, validate_mask
from .jobs import JobService
from .schemas import (
    STAGE_MESSAGES,
    HealthResponse,
    JobListResponse,
    JobStatusResponse,
    JobSummary,
    MeResponse,
    OutputSize,
    RestorationMode,
    SubmitJobResponse,
)
from .storage import mask_path, source_path
from .workers.processor import _encode_jpeg  # reuse the metadata-stripping encoder

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
    photo: UploadFile,
    mode: str = Form(...),
    output: str = Form(...),
    preserve_metadata: bool = Form(default=False),
    crop_json: str | None = Form(default=None),
    rotation: int = Form(default=0),
    repair_mask: UploadFile | None = None,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SubmitJobResponse:
    claims = _authorize(request, authorization)
    st = _state(request)
    settings = st.settings
    jobs = _jobs(request)

    parsed_mode = _parse_enum(mode, RestorationMode, "mode")
    parsed_output = _parse_enum(output, OutputSize, "output")

    photo_bytes = await photo.read()
    validated = validate_and_load(
        photo_bytes,
        allowed_formats=settings.allowed_formats,
        max_bytes=settings.max_upload_bytes,
        max_pixels=settings.max_input_pixels,
    )

    mask_image = None
    if repair_mask is not None:
        mask_bytes = await repair_mask.read()
        mask_image = validate_mask(
            mask_bytes, image_size=(validated.width, validated.height)
        )

    record = jobs.create_job(
        owner_sub=claims["sub"],
        owner_email=claims["email"],
        mode=parsed_mode,
        output=parsed_output,
        has_mask=mask_image is not None,
        preserve_metadata=preserve_metadata,
        idempotency_key=idempotency_key,
    )

    # Persist the normalized (EXIF-corrected, metadata-stripped) source + mask.
    files = st.files
    files.write(
        source_path(record.owner_sub, record.job_id),
        _encode_jpeg(validated.image, quality=95),
    )
    if mask_image is not None:
        buf = io.BytesIO()
        mask_image.save(buf, format="PNG")
        files.write(mask_path(record.owner_sub, record.job_id), buf.getvalue())
    files.commit()

    # Local async: run the placeholder processor in the background. In Modal this
    # is replaced by a GPU worker .spawn() whose call id is stored on the record.
    jobs.set_call_id(record.job_id, f"local_{secrets.token_hex(8)}")
    background.add_task(st.processor.process, record.job_id)

    return SubmitJobResponse(
        job_id=record.job_id,
        status=record.status,
        mode=record.mode,
        output=record.output,
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
        fidelity=r.fidelity,
        generated_detail=r.generated_detail,
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
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.jpg"'},
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

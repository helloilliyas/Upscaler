"""Processor protocol, the shared job-orchestration helper, and the local
placeholder implementation.

``run_image_job`` owns the stage transitions, storage, preview generation, and
error mapping that every image job shares. A processor supplies only an
``enhance`` function — a resize for the GPU-free placeholder, Real-ESRGAN for the
standard worker — so the orchestration is written and tested once.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from ..errors import ApiError, ErrorCode
from ..jobs import JobService
from ..pipelines.sizing import compute_target_size
from ..schemas import Fidelity, JobStage, OutputSize, RestorationMode
from ..storage import FileStore, preview_path, result_path, source_path

# Longest edge of the generated screen preview.
_PREVIEW_MAX_EDGE = 1280

# Coarse fidelity label per mode for the placeholder. Real pipelines compute
# this from actual generated-detail measurements.
_MODE_FIDELITY = {
    RestorationMode.NATURAL: (Fidelity.HIGH, None),
    RestorationMode.RESTORE: (Fidelity.MODERATE, "low"),
    RestorationMode.ULTRA: (Fidelity.GENERATIVE, "medium"),
}


@dataclass(frozen=True)
class EnhanceOutcome:
    """Result of an enhance step: the finished image and its fidelity label."""

    image: Image.Image
    fidelity: Fidelity
    generated_detail: str | None = None


# (source_image, mode, output) -> EnhanceOutcome
EnhanceFn = Callable[[Image.Image, RestorationMode, OutputSize], EnhanceOutcome]


class Processor(Protocol):
    """Runs a single job to completion (or failure), updating its record."""

    def process(self, job_id: str) -> None: ...


def run_image_job(
    jobs: JobService,
    files: FileStore,
    job_id: str,
    enhance: EnhanceFn,
) -> None:
    """Drive one image job through its stages using the supplied ``enhance``.

    Reads the normalized source, runs ``enhance``, writes the result + preview,
    commits storage, and marks the job completed — mapping any failure to a job
    error rather than raising.
    """
    record = jobs.get(job_id)
    try:
        jobs.update_progress(job_id, stage=JobStage.VALIDATING, progress=5)
        files.reload()
        src_bytes = files.read(source_path(record.owner_sub, record.job_id))
        image = Image.open(io.BytesIO(src_bytes)).convert("RGB")

        jobs.update_progress(job_id, stage=JobStage.ENHANCING, progress=40)
        outcome = enhance(
            image,
            RestorationMode(record.mode),
            OutputSize(record.output),
        )
        result = outcome.image

        jobs.update_progress(job_id, stage=JobStage.UPSCALING, progress=75)
        res_path = result_path(record.owner_sub, record.job_id) + ".jpg"
        prev_path = preview_path(record.owner_sub, record.job_id) + ".jpg"

        jobs.update_progress(job_id, stage=JobStage.ENCODING, progress=90)
        files.write(res_path, _encode_jpeg(result))
        files.write(prev_path, _encode_jpeg(_make_preview(result)))
        files.commit()

        jobs.mark_completed(
            job_id,
            result_path=res_path,
            preview_path=prev_path,
            width=result.width,
            height=result.height,
            fidelity=outcome.fidelity,
            generated_detail=outcome.generated_detail,
        )
    except ApiError as exc:
        jobs.mark_failed(job_id, code=exc.code, message=exc.message)
    except Exception as exc:  # any model/IO failure becomes a job error, not a crash
        jobs.mark_failed(
            job_id, code=ErrorCode.MODEL_ERROR, message=f"Processing failed: {exc}"
        )


class LocalPlaceholderProcessor:
    """GPU-free processor: resizes the source to the requested output.

    Stands in for the model pipelines so the async job flow, storage, preview
    generation, and status transitions can be exercised end to end.
    """

    def __init__(self, jobs: JobService, files: FileStore) -> None:
        self._jobs = jobs
        self._files = files

    def process(self, job_id: str) -> None:
        run_image_job(self._jobs, self._files, job_id, self._resize)

    @staticmethod
    def _resize(
        image: Image.Image, mode: RestorationMode, output: OutputSize
    ) -> EnhanceOutcome:
        target = compute_target_size(image.width, image.height, output)
        resized = image.resize(target, Image.Resampling.LANCZOS)
        fidelity, generated = _MODE_FIDELITY[mode]
        return EnhanceOutcome(resized, fidelity, generated)


def _encode_jpeg(image: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    # No exif= argument -> metadata (incl. GPS) is dropped on encode.
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _make_preview(image: Image.Image) -> Image.Image:
    if max(image.size) <= _PREVIEW_MAX_EDGE:
        return image
    preview = image.copy()
    preview.thumbnail((_PREVIEW_MAX_EDGE, _PREVIEW_MAX_EDGE), Image.Resampling.LANCZOS)
    return preview

"""Processor protocol and the local placeholder implementation."""

from __future__ import annotations

import io
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


class Processor(Protocol):
    """Runs a single job to completion (or failure), updating its record."""

    def process(self, job_id: str) -> None: ...


class LocalPlaceholderProcessor:
    """GPU-free processor: resizes the source to the requested output.

    Stands in for the model pipelines so the async job flow, storage, preview
    generation, and status transitions can be exercised end to end.
    """

    def __init__(self, jobs: JobService, files: FileStore) -> None:
        self._jobs = jobs
        self._files = files

    def process(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        try:
            self._jobs.update_progress(job_id, stage=JobStage.VALIDATING, progress=5)
            self._files.reload()
            src_bytes = self._files.read(source_path(record.owner_sub, record.job_id))

            self._jobs.update_progress(job_id, stage=JobStage.ENHANCING, progress=40)
            image = Image.open(io.BytesIO(src_bytes)).convert("RGB")
            target = compute_target_size(image.width, image.height, OutputSize(record.output))

            self._jobs.update_progress(job_id, stage=JobStage.UPSCALING, progress=70)
            resized = image.resize(target, Image.Resampling.LANCZOS)

            self._jobs.update_progress(job_id, stage=JobStage.ENCODING, progress=90)
            res_path = result_path(record.owner_sub, record.job_id) + ".jpg"
            self._files.write(res_path, _encode_jpeg(resized))

            preview = _make_preview(resized)
            prev_path = preview_path(record.owner_sub, record.job_id) + ".jpg"
            self._files.write(prev_path, _encode_jpeg(preview))
            self._files.commit()

            fidelity, generated = _MODE_FIDELITY[RestorationMode(record.mode)]
            self._jobs.mark_completed(
                job_id,
                result_path=res_path,
                preview_path=prev_path,
                width=target[0],
                height=target[1],
                fidelity=fidelity,
                generated_detail=generated,
            )
        except ApiError as exc:
            self._jobs.mark_failed(job_id, code=exc.code, message=exc.message)
        except Exception as exc:  # pragma: no cover - defensive catch-all
            self._jobs.mark_failed(
                job_id, code=ErrorCode.MODEL_ERROR, message=f"Processing failed: {exc}"
            )


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

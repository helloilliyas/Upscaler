"""Tests for the shared run_image_job orchestration and the placeholder.

These exercise the exact code path the Real-ESRGAN standard processor uses,
with a stub enhance function so no GPU/torch is required.
"""

from __future__ import annotations

import io

import pytest
from app.jobs import JobService
from app.schemas import Fidelity, JobStatus, OutputSize, RestorationMode
from app.storage import InMemoryMetadataStore, LocalFileStore, source_path
from app.workers.processor import (
    EnhanceOutcome,
    LocalPlaceholderProcessor,
    run_image_job,
)
from PIL import Image


def _setup(tmp_path, mode=RestorationMode.NATURAL, output=OutputSize.X4):
    files = LocalFileStore(tmp_path)
    jobs = JobService(InMemoryMetadataStore(), files)
    record = jobs.create_job(
        owner_sub="owner",
        owner_email="e@example.com",
        mode=mode,
        output=output,
    )
    buf = io.BytesIO()
    Image.new("RGB", (16, 12), (10, 20, 30)).save(buf, format="JPEG")
    files.write(source_path("owner", record.job_id), buf.getvalue())
    return jobs, files, record.job_id


def test_run_image_job_completes_with_stub_enhance(tmp_path):
    jobs, files, job_id = _setup(tmp_path)

    def enhance(image, mode, output):
        return EnhanceOutcome(Image.new("RGB", (40, 20)), Fidelity.HIGH, None)

    run_image_job(jobs, files, job_id, enhance)

    rec = jobs.get(job_id)
    assert rec.status == JobStatus.COMPLETED
    assert (rec.width, rec.height) == (40, 20)
    assert rec.result_path and files.exists(rec.result_path)
    assert rec.preview_path and files.exists(rec.preview_path)
    assert rec.fidelity == Fidelity.HIGH


def test_run_image_job_marks_failed_on_enhance_error(tmp_path):
    jobs, files, job_id = _setup(tmp_path)

    def enhance(image, mode, output):
        raise RuntimeError("boom")

    run_image_job(jobs, files, job_id, enhance)

    rec = jobs.get(job_id)
    assert rec.status == JobStatus.FAILED
    assert rec.error_code == "MODEL_ERROR"


def test_placeholder_processor_resizes_to_target(tmp_path):
    # 16x12 source at 4x -> 64x48, natural -> high fidelity.
    jobs, files, job_id = _setup(tmp_path, output=OutputSize.X4)
    LocalPlaceholderProcessor(jobs, files).process(job_id)

    rec = jobs.get(job_id)
    assert rec.status == JobStatus.COMPLETED
    assert (rec.width, rec.height) == (64, 48)
    assert rec.fidelity == Fidelity.HIGH


def test_realesrgan_module_is_importable_without_torch(tmp_path):
    # Importing the pipeline and constructing the upscaler must not import torch
    # (load() does). This guards the lazy-import contract the web layer relies on.
    from app.pipelines.realesrgan import SUPPORTED_MODELS, RealEsrganUpscaler

    assert "RealESRGAN_x4plus" in SUPPORTED_MODELS
    upscaler = RealEsrganUpscaler("RealESRGAN_x4plus", str(tmp_path))
    assert upscaler.model_name == "RealESRGAN_x4plus"

    with pytest.raises(ValueError):
        RealEsrganUpscaler("not-a-model", str(tmp_path))

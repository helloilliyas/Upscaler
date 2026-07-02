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


def test_gfpgan_module_is_importable_without_torch(tmp_path):
    # Constructing the face restorer must not import gfpgan/torch (load() does).
    from app.pipelines.gfpgan_face import GfpganFaceRestorer

    restorer = GfpganFaceRestorer(str(tmp_path))
    assert restorer.weights_dir == str(tmp_path)


def test_lama_module_is_importable_without_torch(tmp_path):
    # Constructing the inpainter must not import simple_lama/torch (load() does).
    from app.pipelines.lama_inpaint import LamaInpainter

    inpainter = LamaInpainter(str(tmp_path))
    assert inpainter.weights_dir == str(tmp_path)
    assert inpainter.model_path.endswith("big-lama.pt")


def test_blend_to_target_respects_strength():
    from app.workers.standard_processor import _blend_to_target

    source = Image.new("RGB", (16, 12))  # 4x -> 64x48 target
    model = Image.new("RGB", (64, 48), (255, 255, 255))
    base = Image.new("RGB", (64, 48), (0, 0, 0))

    full = _blend_to_target(model, base, source, OutputSize.X4, 1.0)
    assert full.size == (64, 48)
    assert full.getpixel((0, 0)) == (255, 255, 255)  # pure model output

    none = _blend_to_target(model, base, source, OutputSize.X4, 0.0)
    assert none.getpixel((0, 0)) == (0, 0, 0)  # pure baseline

    half = _blend_to_target(model, base, source, OutputSize.X4, 0.5)
    # 0*0.5 + 255*0.5 -> ~127 on every channel.
    assert all(120 <= c <= 135 for c in half.getpixel((0, 0)))


def test_blend_to_target_resizes_model_output_to_box():
    from app.workers.standard_processor import _blend_to_target

    source = Image.new("RGB", (16, 12))
    # A native-4x model output already at the target box is returned as-is at 1.0.
    model = Image.new("RGB", (100, 80))
    fitted = _blend_to_target(model, source, source, OutputSize.X4, 1.0)
    assert fitted.size == (64, 48)


def test_standard_processor_loads_repair_mask(tmp_path):
    # The Restore path reads the stored mask back as an L image; a job without a
    # mask (or with the blob missing) yields None and skips inpainting.
    from app.storage import mask_path
    from app.workers.standard_processor import StandardModelProcessor

    files = LocalFileStore(tmp_path)
    jobs = JobService(InMemoryMetadataStore(), files)
    proc = StandardModelProcessor(jobs, files, weights_dir=str(tmp_path))

    no_mask = jobs.create_job(
        owner_sub="owner",
        owner_email="e@example.com",
        mode=RestorationMode.RESTORE,
        output=OutputSize.X4,
    )
    assert proc._load_mask(jobs.get(no_mask.job_id)) is None

    with_mask = jobs.create_job(
        owner_sub="owner",
        owner_email="e@example.com",
        mode=RestorationMode.RESTORE,
        output=OutputSize.X4,
        has_mask=True,
    )
    buf = io.BytesIO()
    Image.new("L", (16, 12), 255).save(buf, format="PNG")
    files.write(mask_path("owner", with_mask.job_id), buf.getvalue())

    loaded = proc._load_mask(jobs.get(with_mask.job_id))
    assert loaded is not None
    assert loaded.mode == "L"
    assert loaded.size == (16, 12)

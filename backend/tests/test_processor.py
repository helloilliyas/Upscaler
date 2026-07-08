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


def test_lama_inpaint_composites_only_the_masked_region():
    # Stub the model with a solid-red fill; the surrounding logic (binarize,
    # dilate, downscale, crop, feathered composite) runs for real on CPU.
    from app.pipelines.lama_inpaint import LamaInpainter

    inpainter = LamaInpainter("/nonexistent")
    inpainter._lama = lambda img, msk: Image.new("RGB", img.size, (255, 0, 0))

    src = Image.new("RGB", (400, 300), (10, 120, 40))
    mask = Image.new("L", (400, 300), 0)
    for x in range(180, 220):  # 40px square hole in the middle
        for y in range(130, 170):
            mask.putpixel((x, y), 255)

    out = inpainter.inpaint(src, mask)
    assert out.size == (400, 300)
    # Center of the hole is the model's fill.
    assert out.getpixel((200, 150)) == (255, 0, 0)
    # Far from the hole (beyond dilation+feather) the original is bit-identical.
    assert out.getpixel((10, 10)) == (10, 120, 40)
    assert out.getpixel((390, 290)) == (10, 120, 40)


def test_lama_inpaint_caps_working_resolution_for_large_images():
    from app.pipelines.lama_inpaint import _WORK_EDGE, LamaInpainter

    seen_sizes = []
    inpainter = LamaInpainter("/nonexistent")

    def fake_lama(img, msk):
        seen_sizes.append(img.size)
        assert img.size == msk.size
        return Image.new("RGB", img.size, (255, 0, 0))

    inpainter._lama = fake_lama

    src = Image.new("RGB", (4000, 3000), (10, 120, 40))
    mask = Image.new("L", (4000, 3000), 0)
    for x in range(1900, 2100):
        for y in range(1400, 1600):
            mask.putpixel((x, y), 255)

    out = inpainter.inpaint(src, mask)
    assert out.size == (4000, 3000)
    assert max(seen_sizes[0]) == _WORK_EDGE  # model ran at the capped size
    assert out.getpixel((2000, 1500)) == (255, 0, 0)
    assert out.getpixel((100, 100)) == (10, 120, 40)


def test_diffusion_module_is_importable_without_torch():
    # Constructing the upscaler must not import torch/diffusers (load() does).
    from app.pipelines.diffusion_upscale import MODEL_ID, DiffusionUpscaler

    upscaler = DiffusionUpscaler()
    assert upscaler.model_id == MODEL_ID
    assert upscaler.tile > upscaler.overlap > 0


def test_tile_origins_cover_the_full_length():
    from app.pipelines.diffusion_upscale import tile_origins

    # Smaller than one tile -> single origin.
    assert tile_origins(100, 384, 336) == [0]
    assert tile_origins(384, 384, 336) == [0]
    # Exact stride fit.
    assert tile_origins(720, 384, 336) == [0, 336]
    # Non-exact fit appends a final end-aligned origin.
    assert tile_origins(721, 384, 336) == [0, 336, 337]
    # Every pixel is covered by at least one tile.
    for length in (385, 500, 1280, 1337):
        origins = tile_origins(length, 384, 336)
        assert origins[0] == 0
        assert origins[-1] + 384 == length
        for prev, nxt in zip(origins, origins[1:], strict=False):
            assert nxt <= prev + 384  # no gap between consecutive tiles


def test_diffusion_stitching_is_seamless_and_exact_4x():
    # Stub the per-tile GPU call with a plain 4x resize; the stitching
    # (padding, tiling, feather-blend, crop) is exercised for real on CPU.
    pytest.importorskip("numpy")
    from app.pipelines.diffusion_upscale import DiffusionUpscaler

    upscaler = DiffusionUpscaler(tile=64, overlap=16)
    upscaler._pipe = object()  # pretend load() already ran
    upscaler._tile_output = lambda tile_img, seed: tile_img.resize(  # type: ignore[method-assign]
        (tile_img.width * 4, tile_img.height * 4), Image.Resampling.LANCZOS
    )

    # 150x90 is deliberately not a multiple of 64 -> exercises reflection pad.
    src = Image.new("RGB", (150, 90), (37, 141, 201))
    out = upscaler.upscale(src)

    assert out.size == (600, 360)  # exactly 4x, padding cropped away
    # A constant image must come out exactly constant: proves the overlapping
    # feather weights normalise to 1 everywhere (no seams, no dark edges).
    assert out.getextrema() == ((37, 37), (141, 141), (201, 201))


def test_capped_size_shrinks_but_never_grows():
    from app.pipelines.diffusion_upscale import capped_size

    assert capped_size(4000, 3000, 1280) == (1280, 960)
    assert capped_size(3000, 4000, 1280) == (960, 1280)
    assert capped_size(800, 600, 1280) == (800, 600)  # never upscales
    w, h = capped_size(5, 9000, 1280)
    assert w >= 1 and h == 1280


def test_ultra_processor_is_importable_without_torch(tmp_path):
    from app.workers.ultra_processor import UltraModelProcessor

    files = LocalFileStore(tmp_path)
    jobs = JobService(InMemoryMetadataStore(), files)
    processor = UltraModelProcessor(jobs, files)
    assert processor is not None


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

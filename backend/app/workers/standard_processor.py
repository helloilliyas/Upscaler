"""Standard GPU worker processor: Real-ESRGAN (Natural) + GFPGAN faces (Restore).

Used inside the Modal standard worker. Loads models once and reuses them.
Natural mode runs a Real-ESRGAN 4× pass; Restore mode runs GFPGAN, which
restores faces and upscales the background in one call. Both then resize to the
requested target box. LaMa inpainting (repair mask) lands in a later phase.
"""

from __future__ import annotations

from PIL import Image

from ..jobs import JobService
from ..pipelines.gfpgan_face import GfpganFaceRestorer
from ..pipelines.realesrgan import RealEsrganUpscaler
from ..pipelines.sizing import compute_target_size
from ..schemas import Fidelity, OutputSize, RestorationMode
from ..storage import FileStore
from .processor import EnhanceOutcome, run_image_job

# Checkpoint routing. The general model is lighter (preview/very noisy); x4plus
# is the default for final natural output.
_DEFAULT_MODEL = "RealESRGAN_x4plus"


class StandardModelProcessor:
    """Upscales with Real-ESRGAN (Natural) or GFPGAN faces (Restore)."""

    def __init__(
        self,
        jobs: JobService,
        files: FileStore,
        *,
        weights_dir: str,
        tile: int = 512,
        half: bool = True,
    ) -> None:
        self._jobs = jobs
        self._files = files
        self._weights_dir = weights_dir
        self._tile = tile
        self._half = half
        self._upscalers: dict[str, RealEsrganUpscaler] = {}
        self._face_restorer: GfpganFaceRestorer | None = None

    def warmup(self) -> None:
        """Pre-load the default Real-ESRGAN checkpoint so the first job isn't cold."""
        self._upscaler(_DEFAULT_MODEL)

    def _upscaler(self, model_name: str) -> RealEsrganUpscaler:
        existing = self._upscalers.get(model_name)
        if existing is not None:
            return existing
        upscaler = RealEsrganUpscaler(
            model_name,
            self._weights_dir,
            tile=self._tile,
            half=self._half,
        ).load()
        self._upscalers[model_name] = upscaler
        return upscaler

    def _faces(self) -> GfpganFaceRestorer:
        if self._face_restorer is None:
            self._face_restorer = GfpganFaceRestorer(
                self._weights_dir, tile=self._tile, half=self._half
            ).load()
        return self._face_restorer

    def process(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        mode = RestorationMode(record.mode)

        if mode == RestorationMode.RESTORE:
            enhance = self._restore_enhance()
        else:
            enhance = self._natural_enhance()

        run_image_job(self._jobs, self._files, job_id, enhance)

    def _natural_enhance(self):
        upscaler = self._upscaler(_DEFAULT_MODEL)

        def enhance(
            image: Image.Image, mode: RestorationMode, output: OutputSize
        ) -> EnhanceOutcome:
            restored = _fit(upscaler.enhance(image), image, output)
            return EnhanceOutcome(restored, Fidelity.HIGH, None)

        return enhance

    def _restore_enhance(self):
        faces = self._faces()

        def enhance(
            image: Image.Image, mode: RestorationMode, output: OutputSize
        ) -> EnhanceOutcome:
            restored = _fit(faces.restore(image), image, output)
            return EnhanceOutcome(restored, Fidelity.MODERATE, "low")

        return enhance


def _fit(restored: Image.Image, source: Image.Image, output: OutputSize) -> Image.Image:
    """Resize a native-4× result to the requested output box (one model pass)."""
    target = compute_target_size(source.width, source.height, output)
    if restored.size == target:
        return restored
    return restored.resize(target, Image.Resampling.LANCZOS)

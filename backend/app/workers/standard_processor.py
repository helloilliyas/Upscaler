"""Standard GPU worker processor backed by Real-ESRGAN.

Used inside the Modal standard worker. Loads a checkpoint once (``warmup``), then
runs one native 4× pass per job and resizes to the requested target box. Face
restoration (CodeFormer) and inpainting (LaMa) are added in later phases; this
phase covers Natural and the upscaling part of Restore.
"""

from __future__ import annotations

from PIL import Image

from ..jobs import JobService
from ..pipelines.realesrgan import RealEsrganUpscaler
from ..pipelines.sizing import compute_target_size
from ..schemas import Fidelity, OutputSize, RestorationMode
from ..storage import FileStore
from .processor import EnhanceOutcome, run_image_job

# Checkpoint routing. The general model is lighter (preview/very noisy); x4plus
# is the default for final natural output.
_DEFAULT_MODEL = "RealESRGAN_x4plus"


class StandardModelProcessor:
    """Processor that upscales with Real-ESRGAN, then fits the target box."""

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

    def warmup(self) -> None:
        """Pre-load the default checkpoint so the first job isn't cold."""
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

    def process(self, job_id: str) -> None:
        upscaler = self._upscaler(_DEFAULT_MODEL)

        def enhance(
            image: Image.Image, mode: RestorationMode, output: OutputSize
        ) -> EnhanceOutcome:
            restored = upscaler.enhance(image)
            target = compute_target_size(image.width, image.height, output)
            final = (
                restored
                if restored.size == target
                else restored.resize(target, Image.Resampling.LANCZOS)
            )
            # Real-ESRGAN is structure-preserving; restore mode (pre-face-stage)
            # is labelled moderate until CodeFormer/LaMa land.
            if mode == RestorationMode.NATURAL:
                return EnhanceOutcome(final, Fidelity.HIGH, None)
            return EnhanceOutcome(final, Fidelity.MODERATE, "low")

        run_image_job(self._jobs, self._files, job_id, enhance)

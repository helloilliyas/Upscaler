"""Ultra GPU worker processor: generative diffusion upscaling (Ultra Detail).

Used inside the Modal Ultra worker. Runs Stability AI's latent-diffusion 4×
upscaler over the source (tiled), then fits the result to the requested output
box. The working input is capped to a sane long edge first — diffusion cost
grows with area, and old/low-res photos (Ultra's target material) are small
anyway; anything larger keeps its detail through the model's own 4×.

``strength`` is deliberately ignored here: the app hides the strength slider in
Ultra mode, and a hidden control must never affect output.
"""

from __future__ import annotations

from PIL import Image

from ..jobs import JobService
from ..pipelines.diffusion_upscale import DiffusionUpscaler, capped_size
from ..pipelines.sizing import compute_target_size
from ..schemas import Fidelity, OutputSize, RestorationMode
from ..storage import FileStore
from .processor import EnhanceOutcome, run_image_job

# Long edge the diffusion stage works at. 1280 → native 5120px output before the
# final fit, ~12-30 tiles per photo: detailed results in a couple of minutes.
_MAX_INPUT_EDGE = 1280


class UltraModelProcessor:
    """Generates detail with the x4 diffusion upscaler, then fits to target."""

    def __init__(self, jobs: JobService, files: FileStore) -> None:
        self._jobs = jobs
        self._files = files
        self._upscaler: DiffusionUpscaler | None = None

    def warmup(self) -> None:
        """Pre-load the diffusion pipeline so the first job isn't cold."""
        self._diffusion()

    def _diffusion(self) -> DiffusionUpscaler:
        if self._upscaler is None:
            self._upscaler = DiffusionUpscaler().load()
        return self._upscaler

    def process(self, job_id: str) -> None:
        run_image_job(self._jobs, self._files, job_id, self._enhance)

    def _enhance(
        self, image: Image.Image, mode: RestorationMode, output: OutputSize
    ) -> EnhanceOutcome:
        working = image
        capped = capped_size(image.width, image.height, _MAX_INPUT_EDGE)
        if capped != image.size:
            working = image.resize(capped, Image.Resampling.LANCZOS)

        upscaled = self._diffusion().upscale(working)

        # The output box is always computed from the ORIGINAL source dimensions,
        # like every other mode, so the cap never changes the delivered size.
        target = compute_target_size(image.width, image.height, output)
        if upscaled.size != target:
            upscaled = upscaled.resize(target, Image.Resampling.LANCZOS)
        return EnhanceOutcome(upscaled, Fidelity.GENERATIVE, "medium")

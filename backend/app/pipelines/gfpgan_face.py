"""GFPGAN face restoration for Restore mode.

Detects faces, restores each one, upscales the background with Real-ESRGAN, and
pastes the faces back — all in a single ``GFPGANer.enhance`` call. Heavy
dependencies (gfpgan, facexlib, torch, cv2) are imported lazily so the web layer
and CPU tests don't need them.

CodeFormer's sibling from the same lab; chosen here for a clean, reliable API.
The auxiliary face detection/parsing weights are fetched by facexlib on first
use; the main GFPGAN weight is baked into the image (see scripts/models.json).
"""

from __future__ import annotations

import os
from typing import Any

from PIL import Image

from .realesrgan import RealEsrganUpscaler

_GFPGAN_MODEL = "GFPGANv1.4"
# Background upscaler model (lighter general model is plenty behind the faces).
_BG_MODEL = "realesr-general-x4v3"
_NATIVE_SCALE = 4


class GfpganFaceRestorer:
    """Restores faces and upscales the background by a native 4×."""

    def __init__(
        self,
        weights_dir: str,
        *,
        tile: int = 512,
        half: bool = True,
        fidelity_weight: float = 0.5,
    ) -> None:
        self.weights_dir = weights_dir
        self.tile = tile
        self.half = half
        self.fidelity_weight = fidelity_weight
        self._restorer: Any = None

    def load(self) -> GfpganFaceRestorer:
        from gfpgan import GFPGANer

        bg_upsampler = RealEsrganUpscaler(
            _BG_MODEL, self.weights_dir, tile=self.tile, half=self.half
        ).upsampler

        self._restorer = GFPGANer(
            model_path=os.path.join(self.weights_dir, f"{_GFPGAN_MODEL}.pth"),
            upscale=_NATIVE_SCALE,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=bg_upsampler,
        )
        return self

    def restore(self, image: Image.Image) -> Image.Image:
        """Return the 4×, face-restored RGB image."""
        if self._restorer is None:
            self.load()

        import cv2
        import numpy as np

        bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        _, _, output = self._restorer.enhance(
            bgr,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,
            weight=self.fidelity_weight,
        )
        return Image.fromarray(cv2.cvtColor(output, cv2.COLOR_BGR2RGB))

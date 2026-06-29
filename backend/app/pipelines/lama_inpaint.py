"""LaMa inpainting for the Restore-mode repair brush.

Fills the regions a user painted over (scratches, stains, unwanted objects) with
plausible content before the image is restored/upscaled. Wraps the
``simple-lama-inpainting`` torchscript ``big-lama`` model.

Heavy dependencies (torch, simple_lama_inpainting, cv2) are imported lazily
inside ``load()`` / ``inpaint()`` so the web layer and CPU tests stay importable
without a GPU. The ``big-lama.pt`` weight is baked into the standard worker image
(see scripts/models.json) and located via the ``LAMA_MODEL`` env var the wrapper
reads, so nothing is downloaded at runtime.
"""

from __future__ import annotations

import os
from typing import Any

from PIL import Image

_WEIGHT_FILE = "big-lama.pt"


class LamaInpainter:
    """Inpaints masked regions of an image with the LaMa big-lama model."""

    def __init__(self, weights_dir: str) -> None:
        self.weights_dir = weights_dir
        self.model_path = os.path.join(weights_dir, _WEIGHT_FILE)
        self._lama: Any = None

    def load(self) -> LamaInpainter:
        # SimpleLama reads LAMA_MODEL for a pre-baked checkpoint; point it at the
        # weight baked into the image so it never reaches out to GitHub at runtime.
        os.environ.setdefault("LAMA_MODEL", self.model_path)

        import torch
        from simple_lama_inpainting import SimpleLama

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._lama = SimpleLama(device=device)
        return self

    def inpaint(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        """Return ``image`` with the white regions of ``mask`` filled in.

        ``mask`` is a grayscale image the same size as ``image``; any non-black
        pixel marks a region to repaint. The result keeps the input resolution.
        """
        if self._lama is None:
            self.load()

        rgb = image.convert("RGB")
        # The wrapper treats any non-zero mask pixel as a region to inpaint; keep
        # a hard binary mask so anti-aliased brush edges don't bleed.
        binary = mask.convert("L").point(lambda v: 255 if v > 0 else 0)
        result = self._lama(rgb, binary)

        # big-lama pads to a multiple of 8 internally and crops back, but guard
        # against any off-by-padding so callers can rely on size == input size.
        if result.size != rgb.size:
            result = result.resize(rgb.size, Image.Resampling.LANCZOS)
        return result.convert("RGB")

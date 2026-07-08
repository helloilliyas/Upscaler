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

# Working long edge for the fill pass. Big holes need to be small relative to
# LaMa's receptive field to get structure instead of smudge; the composite step
# keeps the full-resolution pixels everywhere outside the mask.
_WORK_EDGE = 1280


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

        Large removals (a person, a car) are filled at a capped working
        resolution: LaMa's receptive field is small relative to a big hole at
        full resolution, which yields smeary averages. Shrinking makes the hole
        small enough for real structure to form; the fill is then upscaled and
        composited back so every unmasked pixel stays bit-identical.
        """
        if self._lama is None:
            self.load()

        from PIL import ImageFilter

        rgb = image.convert("RGB")
        width, height = rgb.size
        long_edge = max(width, height)

        # Hard-binarize: anti-aliased brush edges must not bleed.
        binary = mask.convert("L").point(lambda v: 255 if v > 0 else 0)

        def dilate(m: Image.Image) -> Image.Image:
            # Grow the mask ~1% past the painted outline: a surviving rim of
            # the removed object poisons the fill with its colours (ghosting).
            # Runs at the working size, where MaxFilter (O(n*k^2)) stays cheap.
            k = max(3, int(max(m.size) * 0.01) // 2 * 2 + 1)  # odd kernel
            return m.filter(ImageFilter.MaxFilter(k))

        if long_edge > _WORK_EDGE:
            scale = _WORK_EDGE / long_edge
            small = (max(1, round(width * scale)), max(1, round(height * scale)))
            small_mask = dilate(binary.resize(small, Image.Resampling.NEAREST))
            filled = self._fill(
                rgb.resize(small, Image.Resampling.LANCZOS), small_mask
            ).resize((width, height), Image.Resampling.LANCZOS)
            dilated = small_mask.resize((width, height), Image.Resampling.NEAREST)
        else:
            dilated = dilate(binary)
            filled = self._fill(rgb, dilated)

        # Paste only the filled region over the pristine original, with a soft
        # edge. The feather ramp lives inside the dilated margin (background),
        # never over the removed object, so nothing ghosts back in.
        feather = max(3, int(long_edge * 0.004))
        soft = dilated.filter(ImageFilter.GaussianBlur(feather))
        return Image.composite(filled, rgb, soft).convert("RGB")

    def _fill(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        """One LaMa pass. The model pads to a multiple of 8 and returns the
        padded canvas; crop (not resize) back to the input size."""
        result = self._lama(image, mask)
        if result.size != image.size:
            result = result.crop((0, 0, image.width, image.height))
        return result

"""Real-ESRGAN super-resolution.

Heavy dependencies (torch, realesrgan, basicsr, cv2) are imported lazily inside
``load()`` / ``enhance()`` so this module — and the rest of ``backend/app`` —
stays importable for the web layer and the unit tests, which never touch a GPU.
The model libraries live only in the standard GPU worker image.

Checkpoints (see ``scripts/models.json``):
* ``realesr-general-x4v3`` — small SRVGGNetCompact, good for fast previews.
* ``RealESRGAN_x4plus``    — RRDBNet, the default for final natural output.

Both are native 4× models. Per the blueprint we run a single 4× pass and then a
controlled resize to the requested target box, rather than repeated model passes.
"""

from __future__ import annotations

import os
from typing import Any

from PIL import Image

# Known checkpoints and their architecture/scale.
_NATIVE_SCALE = 4
_GENERAL = "realesr-general-x4v3"
_X4PLUS = "RealESRGAN_x4plus"
SUPPORTED_MODELS = (_GENERAL, _X4PLUS)


class RealEsrganUpscaler:
    """Loads one Real-ESRGAN checkpoint and upscales PIL images.

    Tiling (``tile`` / ``tile_pad``) is handled internally by ``RealESRGANer`` so
    large outputs are processed in overlapping tiles with reflection padding.
    """

    def __init__(
        self,
        model_name: str,
        weights_dir: str,
        *,
        tile: int = 512,
        tile_pad: int = 32,
        half: bool = True,
    ) -> None:
        if model_name not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")
        self.model_name = model_name
        self.weights_dir = weights_dir
        self.tile = tile
        self.tile_pad = tile_pad
        self.half = half
        # RealESRGANer; typed Any because it is imported lazily inside load().
        self._upsampler: Any = None

    def load(self) -> RealEsrganUpscaler:
        """Build the network and the RealESRGANer. Call once per container."""
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact

        if self.model_name == _GENERAL:
            model = SRVGGNetCompact(
                num_in_ch=3,
                num_out_ch=3,
                num_feat=64,
                num_conv=32,
                upscale=_NATIVE_SCALE,
                act_type="prelu",
            )
        else:  # _X4PLUS
            model = RRDBNet(
                num_in_ch=3,
                num_out_ch=3,
                num_feat=64,
                num_block=23,
                num_grow_ch=32,
                scale=_NATIVE_SCALE,
            )

        model_path = os.path.join(self.weights_dir, f"{self.model_name}.pth")
        self._upsampler = RealESRGANer(
            scale=_NATIVE_SCALE,
            model_path=model_path,
            model=model,
            tile=self.tile,
            tile_pad=self.tile_pad,
            pre_pad=0,
            half=self.half,
        )
        return self

    @property
    def upsampler(self) -> Any:
        """The underlying RealESRGANer (e.g. for use as a GFPGAN background upsampler)."""
        if self._upsampler is None:
            self.load()
        return self._upsampler

    def enhance(self, image: Image.Image) -> Image.Image:
        """Run one native-scale (4×) pass and return the upscaled RGB image."""
        if self._upsampler is None:
            self.load()

        import cv2
        import numpy as np

        rgb = np.array(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        output, _ = self._upsampler.enhance(bgr, outscale=_NATIVE_SCALE)
        out_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        return Image.fromarray(out_rgb)

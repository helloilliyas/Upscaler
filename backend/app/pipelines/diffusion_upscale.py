"""Latent-diffusion 4× upscaling for Ultra Detail mode.

Wraps Stability AI's ``stable-diffusion-x4-upscaler`` — a text-guided latent
diffusion model purpose-built for upscaling. Unlike Real-ESRGAN (which repairs
and sharpens what is there), this *generates* plausible new texture and detail,
which is the Ultra promise. Large inputs are processed as overlapping tiles and
feather-blended back together so VRAM stays bounded and seams stay invisible.

Heavy dependencies (torch, diffusers, numpy) are imported lazily inside
``load()`` / ``upscale()`` so the web layer and CPU tests never need them. The
model snapshot is baked into the Ultra worker image at build time (HF_HOME
points at the baked cache), so nothing is fetched at runtime.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

MODEL_ID = "stabilityai/stable-diffusion-x4-upscaler"
_NATIVE_SCALE = 4

# Generic photographic conditioning; the model needs *a* prompt, and this steers
# it toward faithful texture rather than stylised invention.
_PROMPT = "a sharp, highly detailed, high quality photograph"
_NEGATIVE = "blurry, lowres, low quality, jpeg artifacts, watermark, text, deformed"


def tile_origins(length: int, tile: int, stride: int) -> list[int]:
    """Origins for overlapping tiles covering [0, length): stride apart, and a
    final end-aligned tile so the far edge is always fully covered."""
    if length <= tile:
        return [0]
    origins = list(range(0, length - tile + 1, stride))
    if origins[-1] != length - tile:
        origins.append(length - tile)
    return origins


def capped_size(width: int, height: int, max_edge: int) -> tuple[int, int]:
    """Proportionally shrink (never grow) so the long edge is <= max_edge."""
    longest = max(width, height)
    if longest <= max_edge:
        return (width, height)
    scale = max_edge / longest
    return (max(1, round(width * scale)), max(1, round(height * scale)))


class DiffusionUpscaler:
    """Loads the x4 upscaler pipeline once and upscales PIL images tiled."""

    def __init__(
        self,
        model_id: str = MODEL_ID,
        *,
        tile: int = 384,
        overlap: int = 48,
        steps: int = 25,
        guidance: float = 6.0,
        noise_level: int = 20,
        seed: int = 42,
    ) -> None:
        self.model_id = model_id
        self.tile = tile
        self.overlap = overlap
        self.steps = steps
        self.guidance = guidance
        self.noise_level = noise_level
        self.seed = seed
        # StableDiffusionUpscalePipeline; Any because it is imported lazily.
        self._pipe: Any = None

    def load(self) -> DiffusionUpscaler:
        """Build the fp16 pipeline on CUDA. Call once per container."""
        import torch
        from diffusers import StableDiffusionUpscalePipeline

        pipe = StableDiffusionUpscalePipeline.from_pretrained(
            self.model_id, torch_dtype=torch.float16
        )
        pipe.to("cuda")
        # Bounds attention memory so 384px tiles fit comfortably in fp16.
        pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        self._pipe = pipe
        return self

    def _tile_output(self, tile_img: Image.Image, seed: int) -> Image.Image:
        """One diffusion pass over a single tile -> the 4× tile. Isolated so the
        (GPU-free) stitching logic in upscale() is unit-testable with a stub."""
        import torch

        generator = torch.Generator(device="cuda").manual_seed(seed)
        return self._pipe(
            prompt=_PROMPT,
            negative_prompt=_NEGATIVE,
            image=tile_img,
            num_inference_steps=self.steps,
            guidance_scale=self.guidance,
            noise_level=self.noise_level,
            generator=generator,
        ).images[0]

    def upscale(self, image: Image.Image) -> Image.Image:
        """Return the 4× upscaled RGB image (same aspect, generated detail)."""
        if self._pipe is None:
            self.load()

        import numpy as np

        rgb = image.convert("RGB")
        src_w, src_h = rgb.size

        # Reflection-pad to a multiple of 64 so every tile (and a smaller-than-
        # tile image) has model-friendly dimensions; cropped off at the end.
        arr = np.asarray(rgb)
        pad_h = (64 - src_h % 64) % 64
        pad_w = (64 - src_w % 64) % 64
        if pad_h or pad_w:
            arr = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
        height, width = arr.shape[:2]

        stride = self.tile - self.overlap
        scale = _NATIVE_SCALE
        out = np.zeros((height * scale, width * scale, 3), dtype=np.float32)
        acc = np.zeros((height * scale, width * scale, 1), dtype=np.float32)
        feather = max(1, self.overlap * scale)

        ys = tile_origins(height, self.tile, stride)
        xs = tile_origins(width, self.tile, stride)
        for j, y in enumerate(ys):
            tile_h = min(self.tile, height)
            for i, x in enumerate(xs):
                tile_w = min(self.tile, width)
                tile_img = Image.fromarray(arr[y : y + tile_h, x : x + tile_w])
                # Deterministic per-tile seed: same job in, same pixels out.
                result = self._tile_output(tile_img, self.seed + j * 1000 + i)

                piece = np.asarray(result, dtype=np.float32)
                weight = _feather_mask(piece.shape[0], piece.shape[1], feather)
                oy, ox = y * scale, x * scale
                out[oy : oy + piece.shape[0], ox : ox + piece.shape[1]] += piece * weight
                acc[oy : oy + piece.shape[0], ox : ox + piece.shape[1]] += weight

        merged = out / np.maximum(acc, 1e-6)
        merged = merged.round().clip(0, 255).astype(np.uint8)
        # Drop the reflection padding (in output space).
        merged = merged[: src_h * scale, : src_w * scale]
        return Image.fromarray(merged)


def _feather_mask(height: int, width: int, feather: int):
    """2D blend weights: 1.0 in the interior, ramping to ~0 across `feather`
    pixels at every edge. Overlap-summed weights are normalised by the caller,
    so border tiles (with no neighbour) still come out at full strength."""
    import numpy as np

    def ramp(length: int):
        idx = np.arange(1, length + 1, dtype=np.float32)
        return np.minimum(1.0, np.minimum(idx, idx[::-1]) / float(feather))

    return (ramp(height)[:, None] * ramp(width)[None, :])[:, :, None]

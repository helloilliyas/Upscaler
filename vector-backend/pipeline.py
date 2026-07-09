"""Image -> vector conversion pipeline.

Pure functions, no Modal/FastAPI imports, so the same file runs locally
and inside the Modal container.
"""
import io
import os
import tempfile
import time

import cv2
import numpy as np
import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

MAX_SIDE = 2048

# Each preset is a preprocessing recipe + VTracer parameters.
# detail (0-100) and colors (0 = preset default) tune them further.
PRESETS = {
    "photo": {
        "description": "Natural photos - many colors, smooth curves",
        "quantize": 0,          # 0 = keep full color, VTracer clusters itself
        "denoise": True,
        "contrast": False,
        "binary": False,
        "vtracer": dict(colormode="color", hierarchical="stacked", mode="spline",
                        color_precision=8, layer_difference=16,
                        corner_threshold=60, splice_threshold=45),
    },
    "poster": {
        "description": "Flat poster art - reduced palette, bold shapes",
        "quantize": 8,
        "denoise": True,
        "contrast": True,
        "binary": False,
        "vtracer": dict(colormode="color", hierarchical="stacked", mode="spline",
                        color_precision=6, layer_difference=28,
                        corner_threshold=60, splice_threshold=45),
    },
    "logo": {
        "description": "Logos & graphics - few colors, crisp edges",
        "quantize": 6,
        "denoise": False,
        "contrast": False,
        "binary": False,
        "vtracer": dict(colormode="color", hierarchical="stacked", mode="spline",
                        color_precision=5, layer_difference=32,
                        corner_threshold=45, splice_threshold=45),
    },
    "sketch": {
        "description": "Line drawings - black & white strokes",
        "quantize": 0,
        "denoise": False,
        "contrast": False,
        "binary": True,
        "vtracer": dict(colormode="binary", hierarchical="stacked", mode="spline",
                        corner_threshold=60, splice_threshold=45),
    },
}


def _load_and_resize(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        # flatten transparency onto white so binary/quantize behave
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return img


def _preprocess(img: Image.Image, preset: dict, colors: int) -> Image.Image:
    arr = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    if preset["denoise"]:
        arr = cv2.bilateralFilter(arr, d=7, sigmaColor=40, sigmaSpace=40)

    if preset["contrast"]:
        lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
        arr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    if preset["binary"]:
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(bw).convert("RGB")

    out = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

    n = colors if colors >= 2 else preset["quantize"]
    if n >= 2:
        out = out.quantize(colors=n, method=Image.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    return out


def _detail_params(detail: int) -> dict:
    """Map a single 0-100 'detail' knob onto VTracer's noise filters."""
    detail = max(0, min(100, detail))
    return dict(
        filter_speckle=int(round(12 - detail * 0.11)),   # 100 -> 1, 0 -> 12
        length_threshold=round(8.0 - detail * 0.065, 2),  # 100 -> 1.5, 0 -> 8.0
        path_precision=3 if detail < 80 else 4,
        max_iterations=10,
    )


def vectorize(data: bytes, preset_name: str = "photo", colors: int = 0,
              detail: int = 60) -> dict:
    """Convert image bytes to an SVG string. Returns dict with svg + metadata."""
    import vtracer

    t0 = time.time()
    preset = PRESETS.get(preset_name, PRESETS["photo"])
    img = _load_and_resize(data)
    img = _preprocess(img, preset, colors)

    params = dict(preset["vtracer"])
    params.update(_detail_params(detail))

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.png")
        dst = os.path.join(tmp, "out.svg")
        img.save(src)
        vtracer.convert_image_to_svg_py(src, dst, **params)
        with open(dst) as fh:
            svg = fh.read()

    return {
        "svg": svg,
        "width": img.width,
        "height": img.height,
        "path_count": svg.count("<path"),
        "duration_ms": int((time.time() - t0) * 1000),
    }


def to_pdf(svg: str) -> bytes:
    import cairosvg
    return cairosvg.svg2pdf(bytestring=svg.encode())


def to_png(svg: str, scale: float = 2.0) -> bytes:
    import cairosvg
    return cairosvg.svg2png(bytestring=svg.encode(), scale=scale)

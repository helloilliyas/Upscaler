"""Upload validation: decode, enforce limits, normalize orientation, strip GPS.

Validates both the declared metadata and the actual bytes. Pillow does the
decode; decompression-bomb protection is on. Nothing here executes uploaded
content.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ApiError, ErrorCode

# Pillow raises DecompressionBombError above this; we set it from the configured
# pixel ceiling at validation time too, but keep a hard safety cap as well.
_HARD_PIXEL_CAP = 60_000_000
Image.MAX_IMAGE_PIXELS = _HARD_PIXEL_CAP


@dataclass(frozen=True)
class ValidatedImage:
    image: Image.Image  # RGB, EXIF-orientation applied, metadata stripped
    format: str  # normalized Pillow format, e.g. "JPEG"
    width: int
    height: int


def validate_and_load(
    data: bytes,
    *,
    allowed_formats: frozenset[str],
    max_bytes: int,
    max_pixels: int,
) -> ValidatedImage:
    """Validate raw upload bytes and return a clean RGB image.

    Raises ``ApiError`` with the appropriate code on any failure.
    """
    if len(data) > max_bytes:
        raise ApiError(ErrorCode.FILE_TOO_LARGE, "Uploaded file exceeds the size limit")
    if not data:
        raise ApiError(ErrorCode.INVALID_IMAGE, "Empty upload")

    try:
        probe = Image.open(io.BytesIO(data))
        fmt = (probe.format or "").upper()
    except UnidentifiedImageError as exc:
        raise ApiError(ErrorCode.INVALID_IMAGE, "Image could not be decoded") from exc
    except Image.DecompressionBombError as exc:
        raise ApiError(ErrorCode.PIXEL_LIMIT_EXCEEDED, "Image is too large to process") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise ApiError(ErrorCode.INVALID_IMAGE, "Image could not be decoded") from exc

    if fmt not in allowed_formats:
        raise ApiError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"Unsupported format: {fmt or 'unknown'}",
        )

    width, height = probe.size
    if width * height > max_pixels:
        raise ApiError(
            ErrorCode.PIXEL_LIMIT_EXCEEDED,
            "Image resolution exceeds the safety limit",
        )

    # Fully decode now (probe was lazy). Re-open so we own a clean handle.
    try:
        decoded = Image.open(io.BytesIO(data))
        # Honour EXIF orientation, then drop EXIF by working on the returned copy.
        image: Image.Image = ImageOps.exif_transpose(decoded) or decoded
    except Image.DecompressionBombError as exc:
        raise ApiError(ErrorCode.PIXEL_LIMIT_EXCEEDED, "Image is too large to process") from exc
    except Exception as exc:
        raise ApiError(ErrorCode.INVALID_IMAGE, "Image could not be decoded") from exc

    if image.mode != "RGB":
        image = image.convert("RGB")

    # exif_transpose may have swapped dimensions; report the post-transpose size.
    out_w, out_h = image.size
    return ValidatedImage(image=image, format=fmt, width=out_w, height=out_h)


def validate_mask(data: bytes, *, image_size: tuple[int, int]) -> Image.Image:
    """Validate a repair mask: must be PNG and match the image coordinate system."""
    try:
        mask = Image.open(io.BytesIO(data))
        fmt = (mask.format or "").upper()
    except Exception as exc:
        raise ApiError(ErrorCode.INVALID_IMAGE, "Mask could not be decoded") from exc

    if fmt != "PNG":
        raise ApiError(ErrorCode.UNSUPPORTED_FORMAT, "Repair mask must be a PNG")

    if mask.size != image_size:
        raise ApiError(
            ErrorCode.MASK_SIZE_MISMATCH,
            f"Mask dimensions {mask.size} do not match image {image_size}",
        )

    return mask.convert("L")

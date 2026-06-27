"""Unit tests for upload + mask validation."""

from __future__ import annotations

import io

import pytest
from app.config import ALLOWED_FORMATS
from app.errors import ApiError, ErrorCode
from app.image_validation import validate_and_load, validate_mask
from PIL import Image

from tests.conftest import make_image_bytes, make_mask_bytes

_LIMITS = dict(allowed_formats=ALLOWED_FORMATS, max_bytes=40 * 1024 * 1024, max_pixels=50_000_000)


def test_valid_jpeg_loads_as_rgb():
    result = validate_and_load(make_image_bytes((64, 48), "JPEG"), **_LIMITS)
    assert result.format == "JPEG"
    assert (result.width, result.height) == (64, 48)
    assert result.image.mode == "RGB"


def test_valid_png_and_webp():
    assert validate_and_load(make_image_bytes(fmt="PNG"), **_LIMITS).format == "PNG"
    assert validate_and_load(make_image_bytes(fmt="WEBP"), **_LIMITS).format == "WEBP"


def test_unsupported_format_rejected():
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    with pytest.raises(ApiError) as exc:
        validate_and_load(gif.getvalue(), **_LIMITS)
    assert exc.value.code == ErrorCode.UNSUPPORTED_FORMAT


def test_empty_and_garbage_bytes_rejected():
    with pytest.raises(ApiError) as exc:
        validate_and_load(b"", **_LIMITS)
    assert exc.value.code == ErrorCode.INVALID_IMAGE

    with pytest.raises(ApiError) as exc:
        validate_and_load(b"not an image at all", **_LIMITS)
    assert exc.value.code == ErrorCode.INVALID_IMAGE


def test_file_too_large_rejected():
    data = make_image_bytes((64, 64))
    with pytest.raises(ApiError) as exc:
        validate_and_load(
            data, allowed_formats=ALLOWED_FORMATS, max_bytes=10, max_pixels=50_000_000
        )
    assert exc.value.code == ErrorCode.FILE_TOO_LARGE


def test_pixel_limit_rejected():
    data = make_image_bytes((200, 200))
    with pytest.raises(ApiError) as exc:
        validate_and_load(
            data, allowed_formats=ALLOWED_FORMATS, max_bytes=40 * 1024 * 1024, max_pixels=100
        )
    assert exc.value.code == ErrorCode.PIXEL_LIMIT_EXCEEDED


def test_mask_must_match_image_size():
    img = validate_and_load(make_image_bytes((64, 48)), **_LIMITS)
    ok = validate_mask(make_mask_bytes((64, 48)), image_size=(img.width, img.height))
    assert ok.size == (64, 48)

    with pytest.raises(ApiError) as exc:
        validate_mask(make_mask_bytes((30, 30)), image_size=(64, 48))
    assert exc.value.code == ErrorCode.MASK_SIZE_MISMATCH


def test_mask_must_be_png():
    jpeg_mask = make_image_bytes((64, 48), "JPEG")
    with pytest.raises(ApiError) as exc:
        validate_mask(jpeg_mask, image_size=(64, 48))
    assert exc.value.code == ErrorCode.UNSUPPORTED_FORMAT

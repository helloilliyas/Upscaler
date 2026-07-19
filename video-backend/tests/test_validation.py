"""Upload validation against real ffprobe on synthetic clips."""

from __future__ import annotations

import pytest
from app.errors import ApiError, ErrorCode
from app.validation import validate_video_bytes

from .conftest import make_video_bytes, requires_ffmpeg

pytestmark = requires_ffmpeg

_LIMITS = {
    "max_bytes": 20 * 1024 * 1024,
    "max_seconds": 10.0,
    "max_pixels": 2_100_000,
    "max_fps": 61.0,
}


def _code(exc_info) -> ErrorCode:
    return exc_info.value.code


def test_valid_mp4_probes_correctly():
    info = validate_video_bytes(
        make_video_bytes(duration=1.0, size=(64, 48), fps=10), **_LIMITS
    )
    assert (info.width, info.height) == (64, 48)
    assert info.codec == "h264"
    assert "mp4" in info.container
    assert info.fps == pytest.approx(10.0, rel=0.01)
    assert info.duration_seconds == pytest.approx(1.0, rel=0.1)
    assert info.frames_estimate == 10
    assert info.has_audio is False


def test_mkv_with_audio_is_accepted():
    info = validate_video_bytes(
        make_video_bytes(duration=1.0, audio=True, container="mkv"), **_LIMITS
    )
    assert "matroska" in info.container
    assert info.has_audio is True
    assert info.audio_codec == "aac"


def test_empty_upload_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(b"", **_LIMITS)
    assert _code(exc) == ErrorCode.INVALID_VIDEO


def test_garbage_bytes_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(b"not a video" * 100, **_LIMITS)
    assert _code(exc) == ErrorCode.INVALID_VIDEO


def test_oversize_upload_rejected():
    data = make_video_bytes()
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(data, **{**_LIMITS, "max_bytes": len(data) - 1})
    assert _code(exc) == ErrorCode.FILE_TOO_LARGE


def test_too_long_video_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(
            make_video_bytes(duration=2.0), **{**_LIMITS, "max_seconds": 1.0}
        )
    assert _code(exc) == ErrorCode.VIDEO_TOO_LONG


def test_pixel_limit_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(
            make_video_bytes(size=(128, 96)), **{**_LIMITS, "max_pixels": 64 * 48}
        )
    assert _code(exc) == ErrorCode.PIXEL_LIMIT_EXCEEDED


def test_high_frame_rate_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(
            make_video_bytes(fps=120.0), **{**_LIMITS, "max_fps": 61.0}
        )
    assert _code(exc) == ErrorCode.FRAME_RATE_TOO_HIGH


def test_avi_container_rejected():
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(make_video_bytes(container="avi"), **_LIMITS)
    assert _code(exc) == ErrorCode.UNSUPPORTED_FORMAT


def test_still_image_rejected():
    # A JPEG probes as an image2/mjpeg "video", which the container allow-list
    # rejects deterministically.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 20, 30)).save(buf, format="JPEG")
    with pytest.raises(ApiError) as exc:
        validate_video_bytes(buf.getvalue(), **_LIMITS)
    assert _code(exc) in {ErrorCode.UNSUPPORTED_FORMAT, ErrorCode.INVALID_VIDEO}

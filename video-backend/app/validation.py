"""Upload validation: probe with ffprobe and enforce every cost guardrail.

Only container/codec families with well-tested ffmpeg demuxers are accepted.
The uploaded bytes are written to a private temp file for probing and are
never executed or parsed by Python.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .errors import ApiError, ErrorCode
from .video_io import ProbeError, ToolMissingError, VideoInfo, probe_video

# ffprobe format_name values we accept (MP4/MOV family and Matroska/WebM).
ALLOWED_CONTAINERS: frozenset[str] = frozenset(
    {
        "mov,mp4,m4a,3gp,3g2,mj2",
        "matroska,webm",
    }
)

# Video codecs we accept from those containers.
ALLOWED_CODECS: frozenset[str] = frozenset(
    {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4"}
)


def validate_video_bytes(
    data: bytes,
    *,
    max_bytes: int,
    max_seconds: float,
    max_pixels: int,
    max_fps: float,
) -> VideoInfo:
    """Validate raw upload bytes and return the probed video facts.

    Raises ``ApiError`` with the appropriate code on any failure.
    """
    if len(data) > max_bytes:
        raise ApiError(ErrorCode.FILE_TOO_LARGE, "Uploaded file exceeds the size limit")
    if not data:
        raise ApiError(ErrorCode.INVALID_VIDEO, "Empty upload")

    with tempfile.NamedTemporaryFile(suffix=".upload") as tmp:
        Path(tmp.name).write_bytes(data)
        try:
            info = probe_video(tmp.name)
        except ToolMissingError as exc:
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Video toolchain unavailable") from exc
        except ProbeError as exc:
            raise ApiError(ErrorCode.INVALID_VIDEO, "Video could not be read") from exc

    if info.container not in ALLOWED_CONTAINERS:
        raise ApiError(
            ErrorCode.UNSUPPORTED_FORMAT,
            "Unsupported container; use MP4, MOV, WebM, or MKV",
        )
    if info.codec not in ALLOWED_CODECS:
        raise ApiError(ErrorCode.UNSUPPORTED_FORMAT, f"Unsupported video codec: {info.codec}")

    if info.duration_seconds > max_seconds:
        raise ApiError(
            ErrorCode.VIDEO_TOO_LONG,
            f"Video is {info.duration_seconds:.1f}s; the limit is {max_seconds:.0f}s",
        )
    if info.width * info.height > max_pixels:
        raise ApiError(
            ErrorCode.PIXEL_LIMIT_EXCEEDED,
            "Video resolution exceeds the 1080p input limit",
        )
    if info.fps > max_fps:
        raise ApiError(
            ErrorCode.FRAME_RATE_TOO_HIGH,
            f"Frame rate {info.fps:.0f} fps exceeds the {max_fps:.0f} fps limit",
        )

    return info

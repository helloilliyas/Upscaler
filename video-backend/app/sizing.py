"""Deterministic output-dimension rules for 2x / 4x / 4K.

Aspect ratio is always preserved. Every result is capped inside an
orientation-aware 4K box (video beyond 4K is an encode/storage/playback trap),
and dimensions are rounded down to even numbers because yuv420 encoders
(H.264/HEVC) require them.
"""

from __future__ import annotations

from .schemas import OutputSize

_BOX_4K = (3840, 2160)  # long edge x short edge


def _box_for(width: int, height: int) -> tuple[int, int]:
    long_edge, short_edge = _BOX_4K
    return (long_edge, short_edge) if width >= height else (short_edge, long_edge)


def _even(value: int) -> int:
    return max(2, value - (value % 2))


def compute_target_size(width: int, height: int, output: OutputSize) -> tuple[int, int]:
    """Return the even, 4K-capped target (width, height) for the requested output.

    Raises ValueError for non-positive input dimensions.
    """
    if width <= 0 or height <= 0:
        raise ValueError("video dimensions must be positive")

    box_w, box_h = _box_for(width, height)
    if output == OutputSize.X2:
        out_w, out_h = width * 2, height * 2
    elif output == OutputSize.X4:
        out_w, out_h = width * 4, height * 4
    else:  # K4: scale up (or down) to fit the box exactly
        scale = min(box_w / width, box_h / height)
        out_w, out_h = round(width * scale), round(height * scale)

    # Cap 2x/4x results inside the 4K box, preserving aspect.
    if out_w > box_w or out_h > box_h:
        scale = min(box_w / out_w, box_h / out_h)
        out_w, out_h = round(out_w * scale), round(out_h * scale)

    return _even(out_w), _even(out_h)

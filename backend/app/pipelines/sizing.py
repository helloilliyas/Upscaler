"""Deterministic output-dimension rules for 2x / 4x / 4K / 8K.

Aspect ratio is always preserved; a photo is never stretched to the wrong shape.
4K/8K fit the image inside an orientation-aware bounding box.
"""

from __future__ import annotations

from ..schemas import OutputSize

# Long-edge x short-edge for each bounding-box target.
_BOX = {
    OutputSize.K4: (3840, 2160),
    OutputSize.K8: (7680, 4320),
}


def compute_target_size(width: int, height: int, output: OutputSize) -> tuple[int, int]:
    """Return the target (width, height) for the requested output.

    Raises ValueError for non-positive input dimensions.
    """
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")

    if output == OutputSize.X2:
        return width * 2, height * 2
    if output == OutputSize.X4:
        return width * 4, height * 4

    long_edge, short_edge = _BOX[output]
    if width >= height:
        box_w, box_h = long_edge, short_edge  # landscape box
    else:
        box_w, box_h = short_edge, long_edge  # portrait box

    scale = min(box_w / width, box_h / height)
    out_w = max(1, round(width * scale))
    out_h = max(1, round(height * scale))
    return out_w, out_h

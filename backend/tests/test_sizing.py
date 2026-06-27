"""Unit tests for output-dimension rules."""

from __future__ import annotations

import pytest
from app.pipelines.sizing import compute_target_size
from app.schemas import OutputSize


def test_2x_and_4x_multiply():
    assert compute_target_size(100, 50, OutputSize.X2) == (200, 100)
    assert compute_target_size(100, 50, OutputSize.X4) == (400, 200)


def test_4k_landscape_fits_box_and_preserves_aspect():
    w, h = compute_target_size(1000, 500, OutputSize.K4)  # 2:1
    assert (w, h) == (3840, 1920)  # width-bound by 3840, aspect kept


def test_4k_portrait_uses_portrait_box():
    w, h = compute_target_size(500, 1000, OutputSize.K4)  # 1:2 portrait
    assert (w, h) == (1920, 3840)  # height-bound by the 3840 long edge of the portrait box


def test_8k_landscape():
    w, h = compute_target_size(1000, 500, OutputSize.K8)
    assert (w, h) == (7680, 3840)


def test_aspect_ratio_never_distorted():
    w, h = compute_target_size(1600, 900, OutputSize.K8)
    assert abs((w / h) - (1600 / 900)) < 1e-6


def test_non_positive_dims_raise():
    with pytest.raises(ValueError):
        compute_target_size(0, 10, OutputSize.X2)

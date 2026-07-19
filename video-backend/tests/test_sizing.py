"""Output-dimension rules: scaling, the 4K cap, and even rounding."""

from __future__ import annotations

import pytest
from app.schemas import OutputSize
from app.sizing import compute_target_size


def test_2x_within_box():
    assert compute_target_size(640, 480, OutputSize.X2) == (1280, 960)


def test_2x_of_1080p_hits_4k_exactly():
    assert compute_target_size(1920, 1080, OutputSize.X2) == (3840, 2160)


def test_4x_of_1080p_is_capped_to_4k():
    assert compute_target_size(1920, 1080, OutputSize.X4) == (3840, 2160)


def test_4x_within_box():
    assert compute_target_size(640, 360, OutputSize.X4) == (2560, 1440)


def test_k4_fits_landscape_box():
    w, h = compute_target_size(1280, 720, OutputSize.K4)
    assert (w, h) == (3840, 2160)


def test_k4_portrait_uses_portrait_box():
    w, h = compute_target_size(720, 1280, OutputSize.K4)
    assert (w, h) == (2160, 3840)


def test_odd_aspect_results_are_even():
    w, h = compute_target_size(1279, 719, OutputSize.K4)
    assert w % 2 == 0 and h % 2 == 0
    assert w <= 3840 and h <= 2160


def test_aspect_ratio_preserved_under_cap():
    w, h = compute_target_size(1440, 1080, OutputSize.X4)
    assert w <= 3840 and h <= 2160
    assert abs((w / h) - (1440 / 1080)) < 0.01


def test_nonpositive_dimensions_raise():
    with pytest.raises(ValueError):
        compute_target_size(0, 100, OutputSize.X2)

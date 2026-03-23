"""Tests for synth_head.core.math."""

from synth_head.core.math import clamp


def test_clamp_within_range():
    assert clamp(0.5) == 0.5


def test_clamp_below():
    assert clamp(-1.0) == 0.0


def test_clamp_above():
    assert clamp(2.0) == 1.0


def test_bpy_importable():
    """Verify the bpy pip package is installed and importable."""
    import bpy

    assert hasattr(bpy, "context")

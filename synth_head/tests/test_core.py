"""Starter tests for synth_head.core — validates the dev environment works."""

from synth_head import core


def test_clamp_within_range():
    assert core.clamp(0.5) == 0.5


def test_clamp_below():
    assert core.clamp(-1.0) == 0.0


def test_clamp_above():
    assert core.clamp(2.0) == 1.0


def test_bpy_importable():
    """Verify the bpy pip package is installed and importable."""
    import bpy

    assert hasattr(bpy, "context")

"""Tests for core brow pool texture remap math."""

import numpy as np

from synth_head.core.brow_texture_fix import (
    BrowRemapSpec,
    UVRect,
    remap_brow_pixels,
    tight_alpha_bbox,
    uv_rect_to_pixel_rect,
)


class TestUvRectToPixelRect:
    def test_full_image_rect(self):
        rect = UVRect(u_min=0.0, u_max=1.0, v_min=0.0, v_max=1.0)
        assert uv_rect_to_pixel_rect(rect, width=100, height=200) == (0, 200, 0, 100)

    def test_row_index_increases_with_v(self):
        # v=0 is the bottom row (row 0), v=1 is the top row (row height).
        rect = UVRect(u_min=0.0, u_max=1.0, v_min=0.25, v_max=0.75)
        row_min, row_max, _, _ = uv_rect_to_pixel_rect(rect, width=10, height=100)
        assert row_min == 25
        assert row_max == 75


class TestTightAlphaBbox:
    def test_finds_bbox_of_visible_pixels(self):
        alpha = np.zeros((10, 10))
        alpha[3:6, 4:8] = 1.0
        assert tight_alpha_bbox(alpha) == (3, 6, 4, 8)

    def test_returns_none_when_fully_transparent(self):
        alpha = np.zeros((10, 10))
        assert tight_alpha_bbox(alpha) is None


class TestRemapBrowPixels:
    def _make_canvas(self, size=40):
        pixels = np.zeros((size, size, 4), dtype=np.float32)
        return pixels

    def test_moves_content_into_dest_rect_and_clears_elsewhere(self):
        size = 40
        pixels = self._make_canvas(size)
        # Paint a small solid patch inside the "right" source band (v 0.7-0.9).
        pixels[29:33, 10:20, :] = (1.0, 0.5, 0.25, 1.0)

        spec = BrowRemapSpec(
            source_bands={"right": UVRect(0.0, 1.0, 0.7, 0.9)},
            dest_rects={"right": UVRect(0.0, 0.5, 0.0, 0.2)},
        )
        out = remap_brow_pixels(pixels, spec)

        # Nothing left behind in the original source band.
        sr0, sr1, sc0, sc1 = uv_rect_to_pixel_rect(spec.source_bands["right"], size, size)
        assert np.all(out[sr0:sr1, sc0:sc1, 3] == 0.0)

        # Content now lives inside the destination rect.
        dr0, dr1, dc0, dc1 = uv_rect_to_pixel_rect(spec.dest_rects["right"], size, size)
        dest_alpha = out[dr0:dr1, dc0:dc1, 3]
        assert dest_alpha.max() > 0.0

        # Color of the painted content is preserved (allowing for resample blending).
        painted = out[dr0:dr1, dc0:dc1][out[dr0:dr1, dc0:dc1, 3] > 0.9]
        assert painted.shape[0] > 0
        np.testing.assert_allclose(painted[0][:3], (1.0, 0.5, 0.25), atol=1e-5)

    def test_empty_source_band_produces_no_content(self):
        pixels = self._make_canvas()
        spec = BrowRemapSpec(
            source_bands={"left": UVRect(0.0, 1.0, 0.0, 0.2)},
            dest_rects={"left": UVRect(0.0, 1.0, 0.5, 0.7)},
        )
        out = remap_brow_pixels(pixels, spec)
        assert np.all(out[:, :, 3] == 0.0)

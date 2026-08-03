"""Tests for core brow pool texture remap math."""

import numpy as np

from synth_head.core.brow_texture_fix import (
    BrowRemapSpec,
    OrientedRect,
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
            dest_rects={
                "right": OrientedRect(
                    u_center=0.25, v_center=0.2, length=0.25, width=0.1, angle_deg=0.0,
                ),
            },
        )
        out = remap_brow_pixels(pixels, spec)

        # Nothing left behind in the original source band.
        sr0, sr1, sc0, sc1 = uv_rect_to_pixel_rect(spec.source_bands["right"], size, size)
        assert np.all(out[sr0:sr1, sc0:sc1, 3] == 0.0)

        # Content now lives near the destination center, not the old location.
        dest_row = int(round(spec.dest_rects["right"].v_center * size))
        dest_col = int(round(spec.dest_rects["right"].u_center * size))
        window = out[max(dest_row - 5, 0):dest_row + 5, max(dest_col - 5, 0):dest_col + 5]
        assert window[:, :, 3].max() > 0.0

        # Color of the painted content is preserved (allowing for resample blending).
        opaque = window[window[:, :, 3] > 0.9]
        assert opaque.shape[0] > 0
        np.testing.assert_allclose(opaque[0][:3], (1.0, 0.5, 0.25), atol=1e-5)

    def test_empty_source_band_produces_no_content(self):
        pixels = self._make_canvas()
        spec = BrowRemapSpec(
            source_bands={"left": UVRect(0.0, 1.0, 0.0, 0.2)},
            dest_rects={
                "left": OrientedRect(
                    u_center=0.5, v_center=0.6, length=0.5, width=0.1, angle_deg=0.0,
                ),
            },
        )
        out = remap_brow_pixels(pixels, spec)
        assert np.all(out[:, :, 3] == 0.0)

    def test_rotated_dest_tilts_content_bounding_box(self):
        size = 200
        pixels = self._make_canvas(size)
        # A wide, short solid patch (like a brow stroke) in the source band.
        pixels[170:180, 40:160, :] = (0.1, 0.1, 0.1, 1.0)

        spec_flat = BrowRemapSpec(
            source_bands={"right": UVRect(0.0, 1.0, 0.8, 1.0)},
            dest_rects={
                "right": OrientedRect(
                    u_center=0.5, v_center=0.3, length=0.5, width=0.1, angle_deg=0.0,
                ),
            },
        )
        spec_tilted = BrowRemapSpec(
            source_bands={"right": UVRect(0.0, 1.0, 0.8, 1.0)},
            dest_rects={
                "right": OrientedRect(
                    u_center=0.5, v_center=0.3, length=0.5, width=0.1, angle_deg=30.0,
                ),
            },
        )

        out_flat = remap_brow_pixels(pixels, spec_flat)
        out_tilted = remap_brow_pixels(pixels, spec_tilted)

        def row_span_of_content(img):
            rows = np.where(img[:, :, 3].max(axis=1) > 0.5)[0]
            return rows.max() - rows.min()

        # A 30-degree tilt of a long, thin patch noticeably taller its own
        # axis-aligned bounding box compared to the untilted placement.
        assert row_span_of_content(out_tilted) > row_span_of_content(out_flat) * 1.2

"""Brow pool texture remap — pure Python, no bpy.

The brow texture-swap pool images (``data/input-pipeline/texture/brow/*.png``)
were authored against ``eyebrows_geo``'s own UV (``map1``), which stacks the
right brow in its upper half and the left brow in its lower half. But
``head_mat``'s ``brow-sequence`` node samples these images using
``headOnly_geo``'s own UV (``UVChannel_1``) — the same plain per-object UV the
already-correct lash/beard/lip decals use — where the brow artwork actually
belongs to a small, narrow rectangle. That source/destination UV mismatch is
why the eyebrow decal reads as misaligned while lash/beard/lip do not.

This module crops the actual brow artwork out of its authored (map1) location
and repositions/rescales it to sit in the correct (UVChannel_1) rectangle,
leaving everything else transparent. Scene-side image I/O lives in
``scene/brow_texture_fix.py``.

The transform always reads from the pristine, hand-authored source pool and
writes to a separate output pool — never in place. Applying it to its own
output would find nothing left in the source bands (the artwork already moved
out of them) and produce a blank image.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class UVRect:
    """A rectangle in normalized UV space (0..1), v=0 at the bottom."""

    u_min: float
    u_max: float
    v_min: float
    v_max: float


@dataclass(frozen=True)
class BrowRemapSpec:
    """Per-side source (authored) and destination (target) UV rectangles."""

    source_bands: dict[str, UVRect]
    dest_rects: dict[str, UVRect]


# Measured directly from data/gen13.blend (2026-07-31):
#   - source_bands: eyebrows_geo's own 'map1' UV, split by LeftBrowBind/RightBrowBind
#     (loose >0 membership is fine here — remap_brow_pixels tight-crops to
#     actual alpha content within the band anyway).
#   - dest_rects:   headOnly_geo's 'UVChannel_1', split by the same vertex
#     groups but restricted to vertices with weight >= 0.9. A loose (>0.3)
#     threshold pulls in low-weight skinning-falloff vertices that spill past
#     the midline and into the forehead, producing an oversized rect where
#     left/right overlap in the center. The >=0.9 core is what's actually
#     dominated by each bone and stays a clean, separated pair of regions.
# Re-measure and update these if either mesh is ever re-unwrapped or reweighted.
DEFAULT_BROW_REMAP_SPEC = BrowRemapSpec(
    source_bands={
        "right": UVRect(u_min=0.0219, u_max=0.9843, v_min=0.7261, v_max=0.9780),
        "left": UVRect(u_min=0.0219, u_max=0.9843, v_min=0.4795, v_max=0.7315),
    },
    dest_rects={
        "right": UVRect(u_min=0.1026, u_max=0.2010, v_min=0.1693, v_max=0.2329),
        "left": UVRect(u_min=0.2214, u_max=0.3198, v_min=0.1693, v_max=0.2329),
    },
)


def uv_rect_to_pixel_rect(rect: UVRect, width: int, height: int) -> tuple[int, int, int, int]:
    """Convert a UVRect to (row_min, row_max, col_min, col_max) pixel indices.

    Assumes the Blender pixel-buffer convention: row 0 is v=0 (bottom of the
    image), row height-1 is v=1 (top) — i.e. row index increases with v.
    """
    row_min = int(round(rect.v_min * height))
    row_max = int(round(rect.v_max * height))
    col_min = int(round(rect.u_min * width))
    col_max = int(round(rect.u_max * width))
    return row_min, row_max, col_min, col_max


def tight_alpha_bbox(alpha_band: np.ndarray, threshold: float = 0.02) -> tuple[int, int, int, int] | None:
    """Return the tight (row_min, row_max, col_min, col_max) bbox of pixels above *threshold*.

    Returns None if no pixel in *alpha_band* exceeds the threshold.
    """
    rows = np.where(alpha_band.max(axis=1) > threshold)[0]
    cols = np.where(alpha_band.max(axis=0) > threshold)[0]
    if rows.size == 0 or cols.size == 0:
        return None
    return int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1


def _resize_bilinear(src: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Resize an (h, w, c) float array to (out_h, out_w, c) via bilinear sampling."""
    src_h, src_w = src.shape[:2]
    if src_h == 0 or src_w == 0 or out_h <= 0 or out_w <= 0:
        return np.zeros((max(out_h, 0), max(out_w, 0), src.shape[2]), dtype=src.dtype)

    row_idx = np.clip((np.arange(out_h) + 0.5) * (src_h / out_h) - 0.5, 0, src_h - 1)
    col_idx = np.clip((np.arange(out_w) + 0.5) * (src_w / out_w) - 0.5, 0, src_w - 1)

    r0 = np.floor(row_idx).astype(int)
    r1 = np.clip(r0 + 1, 0, src_h - 1)
    c0 = np.floor(col_idx).astype(int)
    c1 = np.clip(c0 + 1, 0, src_w - 1)

    rf = (row_idx - r0)[:, None, None]
    cf = (col_idx - c0)[None, :, None]

    top = src[r0][:, c0] * (1 - cf) + src[r0][:, c1] * cf
    bottom = src[r1][:, c0] * (1 - cf) + src[r1][:, c1] * cf
    return top * (1 - rf) + bottom * rf


def remap_brow_pixels(
    pixels: np.ndarray,
    spec: BrowRemapSpec = DEFAULT_BROW_REMAP_SPEC,
    alpha_threshold: float = 0.02,
) -> np.ndarray:
    """Crop the brow artwork out of *pixels* and reposition it per *spec*.

    Args:
        pixels: (height, width, 4) float array, Blender pixel-buffer convention
            (row 0 = bottom / v=0).
        spec: per-side source/destination UV rectangles.
        alpha_threshold: minimum alpha to count as "content" when tight-cropping.

    Returns:
        A new (height, width, 4) array with the remapped content on an
        otherwise fully-transparent canvas.
    """
    height, width = pixels.shape[:2]
    out = np.zeros_like(pixels)

    for side, src_rect in spec.source_bands.items():
        sr0, sr1, sc0, sc1 = uv_rect_to_pixel_rect(src_rect, width, height)
        band = pixels[sr0:sr1, sc0:sc1]

        bbox = tight_alpha_bbox(band[:, :, 3], alpha_threshold)
        if bbox is None:
            continue
        r0, r1, c0, c1 = bbox
        crop = band[r0:r1, c0:c1]

        dest_rect = spec.dest_rects[side]
        dr0, dr1, dc0, dc1 = uv_rect_to_pixel_rect(dest_rect, width, height)
        dest_h, dest_w = dr1 - dr0, dc1 - dc0

        crop_h, crop_w = crop.shape[:2]
        scale = min(dest_w / crop_w, dest_h / crop_h)
        new_h = max(1, int(round(crop_h * scale)))
        new_w = max(1, int(round(crop_w * scale)))
        resized = _resize_bilinear(crop, new_h, new_w)

        pad_r = dr0 + (dest_h - new_h) // 2
        pad_c = dc0 + (dest_w - new_w) // 2
        out[pad_r:pad_r + new_h, pad_c:pad_c + new_w] = resized

    return out

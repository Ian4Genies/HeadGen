"""Brow pool texture remap — pure Python, no bpy.

The brow texture-swap pool images (``data/input-pipeline/texture/brow/*.png``)
were authored against ``eyebrows_geo``'s own UV (``map1``), which stacks the
right brow in its upper half and the left brow in its lower half. But
``head_mat``'s ``brow-sequence`` node samples these images using
``headOnly_geo``'s own UV (``UVChannel_1``) — the same plain per-object UV the
already-correct lash/beard/lip decals use — where the brow artwork actually
belongs to a small, narrow, *rotated* region (the natural brow ridge isn't
axis-aligned in UV space). That source/destination UV mismatch — including
the rotation — is why the eyebrow decal reads as misaligned while
lash/beard/lip do not.

This module crops the actual brow artwork out of its authored (map1) location
and repositions/rescales/rotates it to sit in the correct (UVChannel_1)
oriented rectangle, leaving everything else transparent. Scene-side image I/O
lives in ``scene/brow_texture_fix.py``.

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
class OrientedRect:
    """A rotated rectangle in normalized UV space (0..1), v=0 at the bottom.

    ``length`` is the extent along the rotated major axis, ``width`` along the
    minor axis (both in normalized UV units). ``angle_deg`` rotates the major
    axis counter-clockwise from the +U axis, using the same convention as
    standard math angles (consistent with row index increasing with v).
    """

    u_center: float
    v_center: float
    length: float
    width: float
    angle_deg: float


@dataclass(frozen=True)
class BrowRemapSpec:
    """Per-side source (authored) UV band and destination oriented rectangle."""

    source_bands: dict[str, UVRect]
    dest_rects: dict[str, OrientedRect]


# Measured directly from data/gen13.blend (2026-07-31, re-measured 2026-08-03
# to add rotation):
#   - source_bands: eyebrows_geo's own 'map1' UV, split by LeftBrowBind/RightBrowBind
#     (loose >0 membership is fine here — remap_brow_pixels tight-crops to
#     actual alpha content within the band anyway).
#   - dest_rects: headOnly_geo's 'UVChannel_1', fit as an oriented (rotated)
#     rectangle via PCA over vertices with LeftBrowBind/RightBrowBind weight
#     >= 0.9 (a loose >0.3 threshold pulls in low-weight skinning-falloff
#     vertices that spill past the midline, inflating and overlapping the
#     two sides). The natural brow ridge isn't axis-aligned in UV space —
#     fitting a plain bounding box ignored that tilt and made the pasted
#     artwork read as rotated relative to the reference art.
#
#     The raw PCA extents (length=0.0989, width=0.0587) are the *skinning
#     influence* region, not the visible brow-hair area — filling them
#     edge-to-edge made both brows meet in the middle ("unibrow"). Shrunk by
#     ~30%/~20% below so there's a visible gap and better proportion to the
#     eyes; re-tune against reference art if still off.
# Re-measure and update these if either mesh is ever re-unwrapped or reweighted.
DEFAULT_BROW_REMAP_SPEC = BrowRemapSpec(
    source_bands={
        "right": UVRect(u_min=0.0219, u_max=0.9843, v_min=0.7261, v_max=0.9780),
        "left": UVRect(u_min=0.0219, u_max=0.9843, v_min=0.4795, v_max=0.7315),
    },
    dest_rects={
        "right": OrientedRect(
            u_center=0.1599, v_center=0.1978, length=0.070, width=0.047, angle_deg=-8.89,
        ),
        "left": OrientedRect(
            u_center=0.2624, v_center=0.1978, length=0.070, width=0.047, angle_deg=8.89,
        ),
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


def _sample_bilinear(src: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Sample *src* (h, w, c) at arbitrary float (xs, ys) pixel coordinates.

    *xs*/*ys* share a common shape; the result has that shape plus the
    channel dimension. Out-of-bounds samples come back fully transparent.
    """
    h, w = src.shape[:2]
    valid = (xs >= 0) & (xs <= w - 1) & (ys >= 0) & (ys <= h - 1)
    xs_c = np.clip(xs, 0, w - 1)
    ys_c = np.clip(ys, 0, h - 1)

    x0 = np.floor(xs_c).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y0 = np.floor(ys_c).astype(int)
    y1 = np.clip(y0 + 1, 0, h - 1)

    xf = (xs_c - x0)[..., None]
    yf = (ys_c - y0)[..., None]

    top = src[y0, x0] * (1 - xf) + src[y0, x1] * xf
    bottom = src[y1, x0] * (1 - xf) + src[y1, x1] * xf
    result = top * (1 - yf) + bottom * yf
    return result * valid[..., None]


def _rotate_image(src: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate an (h, w, c) RGBA image counter-clockwise by *angle_deg*.

    The output canvas expands to fit the whole rotated content; pixels
    outside the original image are fully transparent. Uses the same
    convention as the rest of this module: increasing row = +v/+y.
    """
    h, w = src.shape[:2]
    if h == 0 or w == 0:
        return src

    theta = np.radians(angle_deg)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    cx0, cy0 = (w - 1) / 2.0, (h - 1) / 2.0

    corners_x = np.array([0.0, w - 1, 0.0, w - 1]) - cx0
    corners_y = np.array([0.0, 0.0, h - 1, h - 1]) - cy0
    rx = corners_x * cos_t - corners_y * sin_t
    ry = corners_x * sin_t + corners_y * cos_t
    new_w = max(1, int(np.ceil(rx.max() - rx.min())) + 1)
    new_h = max(1, int(np.ceil(ry.max() - ry.min())) + 1)
    ncx, ncy = (new_w - 1) / 2.0, (new_h - 1) / 2.0

    ys_out, xs_out = np.meshgrid(np.arange(new_h), np.arange(new_w), indexing="ij")
    dx = xs_out - ncx
    dy = ys_out - ncy
    # Inverse-rotate each output pixel back into source space.
    src_x = dx * cos_t + dy * sin_t + cx0
    src_y = -dx * sin_t + dy * cos_t + cy0

    return _sample_bilinear(src, src_x, src_y)


def _composite_at(out: np.ndarray, patch: np.ndarray, top: int, left: int) -> None:
    """Alpha-composite *patch* onto *out* at (top, left), clipped to bounds."""
    oh, ow = out.shape[:2]
    ph, pw = patch.shape[:2]

    dst_r0, dst_r1 = max(top, 0), min(top + ph, oh)
    dst_c0, dst_c1 = max(left, 0), min(left + pw, ow)
    if dst_r0 >= dst_r1 or dst_c0 >= dst_c1:
        return

    src_r0, src_c0 = dst_r0 - top, dst_c0 - left
    src_r1, src_c1 = src_r0 + (dst_r1 - dst_r0), src_c0 + (dst_c1 - dst_c0)

    region = patch[src_r0:src_r1, src_c0:src_c1]
    a = region[:, :, 3:4]
    out[dst_r0:dst_r1, dst_c0:dst_c1] = out[dst_r0:dst_r1, dst_c0:dst_c1] * (1 - a) + region * a


def remap_brow_pixels(
    pixels: np.ndarray,
    spec: BrowRemapSpec = DEFAULT_BROW_REMAP_SPEC,
    alpha_threshold: float = 0.02,
) -> np.ndarray:
    """Crop the brow artwork out of *pixels* and reposition/rotate it per *spec*.

    Args:
        pixels: (height, width, 4) float array, Blender pixel-buffer convention
            (row 0 = bottom / v=0).
        spec: per-side source UV band and destination oriented rectangle.
        alpha_threshold: minimum alpha to count as "content" when tight-cropping.

    Returns:
        A new (height, width, 4) array with the remapped content on an
        otherwise fully-transparent canvas.
    """
    height, width = pixels.shape[:2]
    out = np.zeros_like(pixels)
    px_per_uv = (width + height) / 2.0

    for side, src_rect in spec.source_bands.items():
        sr0, sr1, sc0, sc1 = uv_rect_to_pixel_rect(src_rect, width, height)
        band = pixels[sr0:sr1, sc0:sc1]

        bbox = tight_alpha_bbox(band[:, :, 3], alpha_threshold)
        if bbox is None:
            continue
        r0, r1, c0, c1 = bbox
        crop = band[r0:r1, c0:c1]

        dest = spec.dest_rects[side]
        length_px = dest.length * px_per_uv
        width_px = dest.width * px_per_uv

        crop_h, crop_w = crop.shape[:2]
        scale = min(length_px / crop_w, width_px / crop_h)
        new_w = max(1, int(round(crop_w * scale)))
        new_h = max(1, int(round(crop_h * scale)))
        resized = _resize_bilinear(crop, new_h, new_w)

        rotated = _rotate_image(resized, dest.angle_deg)
        rot_h, rot_w = rotated.shape[:2]

        center_col = dest.u_center * width
        center_row = dest.v_center * height
        top = int(round(center_row - rot_h / 2.0))
        left = int(round(center_col - rot_w / 2.0))

        _composite_at(out, rotated, top, left)

    return out

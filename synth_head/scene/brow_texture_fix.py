"""Brow pool texture remap — bpy image I/O around core.brow_texture_fix.

Loads each PNG from the hand-authored source pool, remaps its content to
headOnly_geo's UV via the pure Python transform in
``core/brow_texture_fix.py``, and writes the result to a separate output
pool — the source pool is never modified.
"""

from __future__ import annotations

from pathlib import Path

import bpy
import numpy as np

from ..core.brow_texture_fix import BrowRemapSpec, DEFAULT_BROW_REMAP_SPEC, remap_brow_pixels


def remap_brow_texture_file(
    source_path: Path,
    output_path: Path,
    spec: BrowRemapSpec = DEFAULT_BROW_REMAP_SPEC,
) -> None:
    """Crop+reposition the brow artwork in *source_path*, writing the result to *output_path*."""
    source_path = Path(source_path)
    output_path = Path(output_path)
    img = bpy.data.images.load(str(source_path))
    try:
        width, height = img.size
        flat = np.empty(width * height * 4, dtype=np.float32)
        img.pixels.foreach_get(flat)
        pixels = flat.reshape(height, width, 4)

        remapped = remap_brow_pixels(pixels, spec)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        out_img = bpy.data.images.new(
            name="_BrowRemapTemp",
            width=width,
            height=height,
            alpha=True,
            float_buffer=False,
        )
        try:
            out_img.pixels.foreach_set(remapped.reshape(-1))
            out_img.filepath_raw = str(output_path)
            out_img.file_format = "PNG"
            out_img.save()
        finally:
            bpy.data.images.remove(out_img, do_unlink=True)
    finally:
        bpy.data.images.remove(img, do_unlink=True)


def remap_brow_pool(
    source_dir: Path,
    output_dir: Path,
    spec: BrowRemapSpec = DEFAULT_BROW_REMAP_SPEC,
) -> list[Path]:
    """Remap every PNG in *source_dir*, writing results (same filenames) into *output_dir*.

    *source_dir* is only ever read from. Returns the list of written output paths.
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    processed = []
    for f in sorted(source_dir.glob("*.png")):
        out_path = output_dir / f.name
        remap_brow_texture_file(f, out_path, spec)
        processed.append(out_path)
    return processed

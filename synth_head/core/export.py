"""
Pure Python path formatters for the Export pipeline — no bpy.

Tiny helpers for consistent, zero-padded filenames across the export pipeline
so that `operators.py`, `scene.export_bake`, and `scene.export_glb` all agree
on the layout inside `data/final-output/`.

Layout (per frame): every artifact for a given frame lives in the same folder.

    data/final-output/
      frame_0007/
        frame_0007.glb                    <- static GLB with embedded textures
        final_frame0007_<ts>.json         <- snapshot metadata
        head_diffuse.png                  <- baked from head_mat
        R_eye_wedge_diffuse.png           <- baked from eye_mat.001
        L_eye_wedge_diffuse.png           <- baked from eye_mat.002
"""

from __future__ import annotations

FRAME_PAD = 4


def frame_glb_name(frame: int) -> str:
    """Return ``"frame_0007.glb"`` for ``frame=7``."""
    return f"frame_{frame:0{FRAME_PAD}d}.glb"


def frame_dir_name(frame: int) -> str:
    """Return ``"frame_0007"`` for ``frame=7`` — the per-frame output directory."""
    return f"frame_{frame:0{FRAME_PAD}d}"


def frame_png_name(suffix: str) -> str:
    """Return ``"<suffix>_diffuse.png"`` — e.g. ``"head_diffuse.png"``."""
    return f"{suffix}_diffuse.png"

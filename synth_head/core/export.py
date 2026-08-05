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


def frame_dir_name(frame: int, auth_head_name: str | None = None, include_frame: bool = True) -> str:
    """Return the per-frame output directory name.

    ``auth_head_name=None`` — legacy/no-authored-head case: ``"frame_0007"``.
    ``auth_head_name`` set, ``include_frame=True`` (Variation Pipeline — one
    authored head held constant across many frames, so the frame number is
    still needed to disambiguate): ``"auth_Warrior_frame_0007"``.
    ``auth_head_name`` set, ``include_frame=False`` (Generate Authored Head
    Variations — each frame is already a distinct, uniquely-named head, so no
    frame suffix is needed): ``"auth_Warrior"``. ``include_frame`` is kept as a
    real parameter rather than removed so a frame suffix can be reinstated here
    later without re-deriving this logic.
    """
    frame_part = f"frame_{frame:0{FRAME_PAD}d}"
    if auth_head_name is None:
        return frame_part
    if include_frame:
        return f"{auth_head_name}_{frame_part}"
    return auth_head_name


def frame_png_name(suffix: str) -> str:
    """Return ``"<suffix>_diffuse.png"`` — e.g. ``"head_diffuse.png"``."""
    return f"{suffix}_diffuse.png"


def eye_bake_seq_png_name(frame: int, side: str) -> str:
    """Return the filename written by SYNTHHEAD_OT_BakeEyes into the sequence dir.

    E.g. ``eye_bake_seq_png_name(1, "R")`` → ``"frame_0001_R_eye_wedge_diffuse.png"``.
    """
    return f"frame_{frame:0{FRAME_PAD}d}_{side}_eye_wedge_diffuse.png"

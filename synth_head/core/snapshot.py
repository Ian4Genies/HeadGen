"""
Pure Python serialization for head snapshots — no bpy.

Builds, saves, and loads JSON snapshot files that capture every tracked
parameter on a head (chaos joints, variation shapes, expression shapes)
plus the constraint rules active at the time of capture.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SNAPSHOT_VERSION = 2


def build_snapshot(
    chaos_joints: dict[str, dict],
    variation_shapes: dict[str, float],
    expression_shapes: dict[str, float],
    frame: int,
    label: str,
    note: str = "",
    config_snapshot: dict | None = None,
    rules_raw: dict | None = None,
) -> dict:
    """Assemble a complete snapshot dict ready for serialization.

    Args:
        chaos_joints: ``{bone_name: {location: [...], rotation_quaternion: [...], scale: [...]}}``
        variation_shapes: ``{shape_name: value}``
        expression_shapes: ``{shape_name: value}``
        frame: The Blender frame number this snapshot was taken on.
        label: ``"issue"`` or ``"good"`` — used in the filename.
        note: Optional freeform note describing the snapshot.
        config_snapshot: Full config directory contents (v2+).
        rules_raw: Legacy v1 rules_snapshot (kept for backward compat).
    """
    snap: dict = {
        "version": SNAPSHOT_VERSION,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "frame": frame,
        "label": label,
        "note": note,
        "chaos_joints": chaos_joints,
        "variation_shapes": variation_shapes,
        "expression_shapes": expression_shapes,
    }
    if config_snapshot is not None:
        snap["config_snapshot"] = config_snapshot
    if rules_raw is not None:
        snap["rules_snapshot"] = rules_raw
    return snap


def save_snapshot(snapshot: dict, directory: str | Path) -> Path:
    """Write *snapshot* as pretty-printed JSON and an optional companion .md note.

    Filename is auto-generated: ``{label}_frame{NNN}_{YYYYMMDD_HHMMSS}.json``.
    Creates *directory* if it doesn't exist.

    Returns the Path to the saved JSON file.
    """
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)

    label = snapshot.get("label", "snapshot")
    frame = snapshot.get("frame", 0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = f"{label}_frame{frame:03d}_{stamp}"

    json_path = d / f"{basename}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    note = snapshot.get("note", "")
    if note.strip():
        md_path = d / f"{basename}.md"
        md_path.write_text(
            f"# {label.title()} — frame {frame}\n\n{note}\n",
            encoding="utf-8",
        )

    return json_path


def load_snapshot(path: str | Path) -> dict:
    """Read and return a previously saved snapshot JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

"""Config file metadata for the UI."""

from __future__ import annotations

CONFIG_FILES: list[dict[str, str]] = [
    {"id": "runner", "label": "Runner", "description": "Frame count, seed, and file paths"},
    {"id": "chaos_joints", "label": "Chaos Joints", "description": "Joint names, ranges, and per-joint overrides"},
    {"id": "blendshapes", "label": "Blendshapes", "description": "Shape lists, weights, and overrides"},
    {"id": "constraints", "label": "Constraints", "description": "Hard clamps and relational rules"},
    {"id": "modifiers", "label": "Modifiers", "description": "Smooth corrective modifier settings"},
    {"id": "attractor", "label": "Attractor", "description": "Attractive-head nudge system"},
    {"id": "materials", "label": "Materials", "description": "Skin material and color node settings"},
    {"id": "cleanup", "label": "Cleanup", "description": "Mesh surgery and object names"},
    {"id": "drivers", "label": "Drivers", "description": "FCurve driver wiring between properties"},
    {"id": "projection", "label": "Projection", "description": "Eye projection bake objects and settings"},
    {"id": "export", "label": "Export", "description": "Pipeline 03 GLB export and bake settings"},
    {"id": "texture_swap", "label": "Texture Swap", "description": "Image sequence overlay slots"},
    {"id": "rerandomize", "label": "Rerandomize", "description": "Selective post-pipeline re-randomization"},
]

CONFIG_FILE_IDS = {entry["id"] for entry in CONFIG_FILES}

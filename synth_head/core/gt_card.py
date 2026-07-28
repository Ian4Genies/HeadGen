# synth_head/core/gt_card.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime

GT_CARD_VERSION = 1

@dataclass
class GTCard:
    asset_id: str                              # matches auth_* shape key name
    anchor: str                                # e.g. "gen13_v1"
    extracted_at: str
    landmarks: dict[str, list[float]]          # {name: [x, y, z]} at shape_key=1.0
    landmark_deltas: dict[str, list[float]]    # landmarks minus Basis positions
    feature_signatures: dict[str, dict[str, float]]  # derived per-region scalars
    version: int = GT_CARD_VERSION

def save_gt_card(card: GTCard, directory: str | Path) -> Path:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "gt_card.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(card.__dict__, f, indent=2, ensure_ascii=False)
    return path

def load_gt_card(path: str | Path) -> GTCard:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return GTCard(**data)

def compute_feature_signatures(
    deltas: dict[str, list[float]]
) -> dict[str, dict[str, float]]:
    """Derive per-region scalars from landmark deltas. Extend as needed."""
    def dx(name): return deltas[name][0]
    def dy(name): return deltas[name][1]
    def dz(name): return deltas[name][2]

    sigs = {}

    if {"nose_tip", "alar_left", "alar_right"} <= deltas.keys():
        sigs["nose"] = {
            "width":      abs(dx("alar_right")) - abs(dx("alar_left")),  # symmetry check
            "alar_width": dx("alar_right") - dx("alar_left"),
            "projection": dz("nose_tip"),
            "height":     dy("nose_tip"),
        }

    if {"jaw_left", "jaw_right"} <= deltas.keys():
        sigs["jaw"] = {
            "width":  dx("jaw_right") - dx("jaw_left"),
            "height": (dy("jaw_left") + dy("jaw_right")) / 2,
        }

    if {"mouth_left", "mouth_right"} <= deltas.keys():
        sigs["mouth"] = {
            "width":    dx("mouth_right") - dx("mouth_left"),
            "vertical": (dy("mouth_left") + dy("mouth_right")) / 2,
        }

    if {"eye_inner_left", "eye_inner_right"} <= deltas.keys():
        sigs["eyes"] = {
            "inner_spacing": dx("eye_inner_right") - dx("eye_inner_left"),
            "vertical":      (dy("eye_inner_left") + dy("eye_inner_right")) / 2,
        }

    return sigs
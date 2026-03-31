"""Configuration dataclasses for Blender modifiers — pure Python, no bpy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SmoothCorrectiveConfig:
    factor: float = .6
    iterations: int = 5
    scale: float = 1.0
    smooth_type: str = "SIMPLE"
    use_only_smooth: bool = False
    use_pin_boundary: bool = False
    rest_source: str = "ORCO"

    @classmethod
    def from_dict(cls, data: dict) -> "SmoothCorrectiveConfig":
        return cls(
            factor=data.get("factor", 0.6),
            iterations=data.get("iterations", 5),
            scale=data.get("scale", 1.0),
            smooth_type=data.get("smooth_type", "SIMPLE"),
            use_only_smooth=data.get("use_only_smooth", False),
            use_pin_boundary=data.get("use_pin_boundary", False),
            rest_source=data.get("rest_source", "ORCO"),
        )

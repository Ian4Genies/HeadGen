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

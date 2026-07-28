"""Eye-socket depth fit — pure Python, no bpy.

Computes bone-local depth corrections that recess the eye/cutter relative to
the face rim. Scene measurement lives in ``scene/eye_fit.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .math import clamp
from .variation import ChaosTransform

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass
class EyeFitConfig:
    enabled: bool = True
    depth_axis: str = "y"
    left_bone: str = "LeftEyeSocketBind"
    right_bone: str = "RightEyeSocketBind"
    target_inset: float = 0.002
    max_correction: float = 0.05
    max_iters: int = 4
    gain: float = 0.5
    tolerance: float = 0.0005
    weight_min: float = 0.1
    weight_max: float = 0.9
    sample_radius: float = 0.08
    eye_front_percentile: float = 0.9
    outward_sign: float = 1.0
    min_face_samples: int = 8
    min_eye_samples: int = 8

    @classmethod
    def from_dict(cls, d: dict) -> "EyeFitConfig":
        axis = str(d.get("depth_axis", "y")).lower()
        if axis not in _AXIS_INDEX:
            axis = "y"
        return cls(
            enabled=bool(d.get("enabled", True)),
            depth_axis=axis,
            left_bone=str(d.get("left_bone", "LeftEyeSocketBind")),
            right_bone=str(d.get("right_bone", "RightEyeSocketBind")),
            target_inset=float(d.get("target_inset", 0.002)),
            max_correction=float(d.get("max_correction", 0.05)),
            max_iters=max(1, int(d.get("max_iters", 4))),
            gain=float(d.get("gain", 0.5)),
            tolerance=float(d.get("tolerance", 0.0005)),
            weight_min=float(d.get("weight_min", 0.1)),
            weight_max=float(d.get("weight_max", 0.9)),
            sample_radius=float(d.get("sample_radius", 0.08)),
            eye_front_percentile=clamp(float(d.get("eye_front_percentile", 0.9)), 0.0, 1.0),
            outward_sign=float(d.get("outward_sign", 1.0)) or 1.0,
            min_face_samples=max(1, int(d.get("min_face_samples", 8))),
            min_eye_samples=max(1, int(d.get("min_eye_samples", 8))),
        )

    @property
    def depth_param_left(self) -> str:
        return f"{self.left_bone}.location.{self.depth_axis}"

    @property
    def depth_param_right(self) -> str:
        return f"{self.right_bone}.location.{self.depth_axis}"

    def is_depth_param(self, key: str) -> bool:
        return key in (self.depth_param_left, self.depth_param_right)


def compute_depth_correction(
    gap: float,
    *,
    target_inset: float,
    max_correction: float,
    gain: float,
) -> float:
    """Return delta to add to bone ``location[axis]``.

    *gap* is ``eye_proj - rim_proj`` along the outward axis (positive = eye
    sits past the face rim). Target is ``gap == -target_inset``.
    Assumes increasing the bone location component moves content outward.
    """
    error = gap + target_inset
    return clamp(-error * gain, -max_correction, max_correction)


def percentile_mean(values: list[float], percentile: float) -> float | None:
    """Mean of samples at/above *percentile* (0–1) of the sorted list."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    start = min(n - 1, max(0, int(percentile * (n - 1))))
    subset = ordered[start:]
    return sum(subset) / len(subset)


def set_transform_location_axis(
    xform: ChaosTransform,
    axis: str,
    value: float,
) -> ChaosTransform:
    """Return a copy of *xform* with one location axis replaced."""
    idx = _AXIS_INDEX[axis]
    loc = list(xform.location)
    loc[idx] = value
    return ChaosTransform(
        location=(loc[0], loc[1], loc[2]),
        rotation=xform.rotation,
        scale=xform.scale,
    )


def get_transform_location_axis(xform: ChaosTransform, axis: str) -> float:
    return xform.location[_AXIS_INDEX[axis]]

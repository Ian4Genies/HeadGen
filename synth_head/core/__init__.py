"""Public API for synth_head.core."""

from .math import clamp, euler_degrees_to_quaternion
from .modifiers import SmoothCorrectiveConfig
from .variation import (
    CHAOS_JOINT_NAMES,
    ChaosTransform,
    VariationConfig,
    classify_joints,
    generate_chaos_transforms,
)

__all__ = [
    "clamp",
    "euler_degrees_to_quaternion",
    "SmoothCorrectiveConfig",
    "CHAOS_JOINT_NAMES",
    "ChaosTransform",
    "VariationConfig",
    "classify_joints",
    "generate_chaos_transforms",
]

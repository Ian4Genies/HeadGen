"""Public API for synth_head.core."""

from .math import clamp, euler_degrees_to_quaternion
from .modifiers import SmoothCorrectiveConfig
from .variation import (
    CHAOS_JOINT_NAMES,
    ChaosTransform,
    VariationConfig,
    classify_joints,
    generate_chaos_transforms,
    generate_single_frame_transforms,
)
from .blendshapes import (
    VARIATION_SHAPES,
    EXPRESSION_SHAPES,
    BlendshapeConfig,
    classify_variation_shapes,
    classify_expression_shapes,
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
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
    "generate_single_frame_transforms",
    "VARIATION_SHAPES",
    "EXPRESSION_SHAPES",
    "BlendshapeConfig",
    "classify_variation_shapes",
    "classify_expression_shapes",
    "generate_blendshape_weights",
    "generate_single_frame_blendshape_weights",
]

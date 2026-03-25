"""Public API for synth_head.core."""

from .math import clamp, euler_degrees_to_quaternion
from .constraints import (
    ConstraintRules,
    ValidationReport,
    constrain,
    expand_joint_keys,
    flatten_params,
    load_rules,
    unflatten_params,
    validate_rules,
)
from .modifiers import SmoothCorrectiveConfig
from .variation import (
    CHAOS_JOINT_NAMES,
    DEFAULT_JOINT_OVERRIDES,
    ChaosTransform,
    VariationConfig,
    classify_joints,
    generate_chaos_transforms,
    generate_single_frame_transforms,
)
from .blendshapes import (
    VARIATION_SHAPES,
    EXPRESSION_SHAPES,
    DEFAULT_VARIATION_OVERRIDES,
    DEFAULT_EXPRESSION_OVERRIDES,
    BlendshapeConfig,
    classify_variation_shapes,
    classify_expression_shapes,
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
)

__all__ = [
    "clamp",
    "euler_degrees_to_quaternion",
    "ConstraintRules",
    "ValidationReport",
    "constrain",
    "expand_joint_keys",
    "flatten_params",
    "load_rules",
    "unflatten_params",
    "validate_rules",
    "SmoothCorrectiveConfig",
    "CHAOS_JOINT_NAMES",
    "DEFAULT_JOINT_OVERRIDES",
    "ChaosTransform",
    "VariationConfig",
    "classify_joints",
    "generate_chaos_transforms",
    "generate_single_frame_transforms",
    "VARIATION_SHAPES",
    "EXPRESSION_SHAPES",
    "DEFAULT_VARIATION_OVERRIDES",
    "DEFAULT_EXPRESSION_OVERRIDES",
    "BlendshapeConfig",
    "classify_variation_shapes",
    "classify_expression_shapes",
    "generate_blendshape_weights",
    "generate_single_frame_blendshape_weights",
]

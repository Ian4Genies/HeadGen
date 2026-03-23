"""
Pure Python logic for the variation pipeline.

No bpy imports — fully testable with pytest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


CHAOS_JOINT_NAMES: frozenset[str] = frozenset({
    "JawBind",
    "MouthBind",
    "MouthInnerBind",
    "NoseBind",
    "LeftBrowBind",
    "RightBrowBind",
    "RightEyeSocketBind",
    "LeftEyeSocketBind",
    "FaceBind",
    "NeckBind",
    "LeftShoulderBind",
    "RightShoulderBind",
    "Spine2Bind",
})


@dataclass
class ChaosTransform:
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: tuple[float, float, float]


@dataclass
class VariationConfig:
    frame_count: int = 400
    transform_max: float = 0.2
    rotate_max: float = 10.0
    scale_max: float = 0.2
    seed: int | None = None


def generate_chaos_transforms(
    config: VariationConfig,
    joint_names: list[str],
) -> dict[int, dict[str, ChaosTransform]]:
    """Return {frame: {joint_name: ChaosTransform}} for every frame in config.

    Uses an optionally seeded RNG so results are reproducible when config.seed
    is set. The returned structure is plain Python data — no bpy types.
    """
    rng = random.Random(config.seed)
    result: dict[int, dict[str, ChaosTransform]] = {}

    t = config.transform_max
    r = config.rotate_max
    s = config.scale_max

    for frame in range(1, config.frame_count + 1):
        joints: dict[str, ChaosTransform] = {}
        for name in joint_names:
            joints[name] = ChaosTransform(
                location=(
                    rng.uniform(-t, t),
                    rng.uniform(-t, t),
                    rng.uniform(-t, t),
                ),
                rotation=(
                    rng.uniform(-r, r),
                    rng.uniform(-r, r),
                    rng.uniform(-r, r),
                ),
                scale=(
                    1.0 + rng.uniform(-s, s),
                    1.0 + rng.uniform(-s, s),
                    1.0 + rng.uniform(-s, s),
                ),
            )
        result[frame] = joints

    return result

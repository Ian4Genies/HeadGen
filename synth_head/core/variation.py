"""
Pure Python logic for the variation pipeline.

No bpy imports — fully testable with pytest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


CHAOS_JOINT_NAMES: frozenset[str] = frozenset({
    "JawBind",
    "MouthBind",
    "MouthInnerBind",
    "NoseBind",
    "LeftBrowBind",
    "RightBrowBind",
    "RightEyeSocketBind",
    "LeftEyeSocketBind",
    "FaceBind"


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
    enable_scale: bool = True


def classify_joints(
    joint_names: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Split joints into symmetric pairs and unpaired center joints.

    A pair is any (Left*, Right*) joint whose suffix matches exactly.
    Everything else — including any unmatched Left/Right joints — falls
    into the center list.

    Returns:
        (pairs, center) where pairs is [(left_name, right_name), ...] and
        center is [name, ...].
    """
    lefts = {n for n in joint_names if n.startswith("Left")}
    rights = {n for n in joint_names if n.startswith("Right")}

    pairs: list[tuple[str, str]] = []
    matched_lefts: set[str] = set()
    matched_rights: set[str] = set()

    for left in sorted(lefts):
        right = "Right" + left.removeprefix("Left")
        if right in rights:
            pairs.append((left, right))
            matched_lefts.add(left)
            matched_rights.add(right)

    center = [
        n for n in joint_names
        if n not in matched_lefts and n not in matched_rights
    ]

    return pairs, center


def generate_chaos_transforms(
    config: VariationConfig,
    joint_names: list[str],
) -> dict[int, dict[str, ChaosTransform]]:
    """Return {frame: {joint_name: ChaosTransform}} for every frame in config.

    Symmetry rules applied during generation:
    - Paired (Left*/Right*) joints: identical Y/Z location and X rotation;
      Left X location is negated for Right (mirror across YZ plane);
      Left Y/Z rotation is negated for Right.
    - Center joints (no Left/Right prefix): zero X location; only X-axis
      rotation is non-zero.
    - Scale is identity (1, 1, 1) unless config.enable_scale is True.

    Uses an optionally seeded RNG so results are reproducible when
    config.seed is set.
    """
    rng = random.Random(config.seed)
    result: dict[int, dict[str, ChaosTransform]] = {}

    t = config.transform_max
    r = config.rotate_max
    s = config.scale_max

    pairs, center = classify_joints(joint_names)
    identity_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def _scale() -> tuple[float, float, float]:
        if config.enable_scale:
            return (
                1.0 + rng.uniform(-s, s),
                1.0 + rng.uniform(-s, s),
                1.0 + rng.uniform(-s, s),
            )
        return identity_scale

    for frame in range(1, config.frame_count + 1):
        joints: dict[str, ChaosTransform] = {}

        for left_name, right_name in pairs:
            lx = rng.uniform(-t, t)
            ly = rng.uniform(-t, t)
            lz = rng.uniform(-t, t)
            rot_x = rng.uniform(-r, r)
            rot_y = rng.uniform(-r, r)
            rot_z = rng.uniform(-r, r)
            scale = _scale()

            joints[left_name] = ChaosTransform(
                location=(lx, ly, lz),
                rotation=(rot_x, rot_y, rot_z),
                scale=scale,
            )
            joints[right_name] = ChaosTransform(
                location=(-lx, ly, lz),
                rotation=(rot_x, -rot_y, -rot_z),
                scale=scale,
            )

        for name in center:
            joints[name] = ChaosTransform(
                location=(0.0, rng.uniform(-t, t), rng.uniform(-t, t)),
                rotation=(rng.uniform(-r, r), 0.0, 0.0),
                scale=_scale(),
            )

        result[frame] = joints

    return result

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
})

DEFAULT_JOINT_OVERRIDES: dict[str, float] = {
    # --- FaceBind — moves the whole face, needs tight limits ---------------
    "FaceBind.location":   0.02,
    "FaceBind.rotation":   0.0,
    "FaceBind.scale":      0.02,

    # --- JawBind -----------------------------------------------------------
    "JawBind.location":    0.15,
    "JawBind.rotation.x":  8.0,

    # --- MouthBind ---------------------------------------------------------
    "MouthBind.location":  0.1,
    "MouthBind.rotation":  5.0,

    # --- MouthInnerBind ----------------------------------------------------
    "MouthInnerBind.location": 0.08,
    "MouthInnerBind.rotation": 4.0,

    # --- NoseBind ----------------------------------------------------------
    "NoseBind.location":   0.1,
    "NoseBind.rotation.x": 5.0,

    # --- Brow pair (keyed to Left; Right inherits via symmetry) ------------
    "LeftBrowBind.location":   0.15,
    "LeftBrowBind.rotation":   8.0,

    # --- EyeSocket pair (keyed to Left) ------------------------------------
    "LeftEyeSocketBind.location":   0.1,
    "LeftEyeSocketBind.rotation":   6.0,
}


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
    joint_overrides: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_JOINT_OVERRIDES),
    )


def _resolve_range(
    joint_name: str,
    channel: str,
    global_max: float,
    overrides: dict[str, float],
    axis: str | None = None,
) -> float:
    """Look up the generation range for a joint+channel (optionally per-axis).

    Resolution order (most specific wins):
      1. ``"JointName.channel.axis"``  (e.g. ``"FaceBind.location.x"``)
      2. ``"JointName.channel"``       (e.g. ``"FaceBind.location"``)
      3. *global_max* fallback
    """
    if axis is not None:
        axis_key = f"{joint_name}.{channel}.{axis}"
        if axis_key in overrides:
            return overrides[axis_key]
    channel_key = f"{joint_name}.{channel}"
    return overrides.get(channel_key, global_max)


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


def _generate_joint_transforms(
    rng: random.Random,
    pairs: list[tuple[str, str]],
    center: list[str],
    t: float,
    r: float,
    s: float,
    enable_scale: bool,
    overrides: dict[str, float] | None = None,
) -> dict[str, ChaosTransform]:
    """Generate one frame of symmetry-aware chaos transforms.

    Per-joint generation ranges are resolved via *overrides* (keyed as
    ``"JointName.location"``, ``"JointName.rotation"``, ``"JointName.scale"``).
    Any joint+channel without an override falls back to the corresponding
    global max (*t*, *r*, or *s*).

    Symmetry rules:
    - Paired (Left*/Right*) joints: identical Y/Z location and X rotation;
      Left X location is negated for Right (mirror across YZ plane);
      Left Y/Z rotation is negated for Right.  The Left joint's override
      is used for the pair.
    - Center joints (no Left/Right prefix): zero X location; only X-axis
      rotation is non-zero.
    - Scale is identity (1, 1, 1) unless *enable_scale* is True.
    """
    ov = overrides or {}
    identity_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def _scale(joint_name: str) -> tuple[float, float, float]:
        if enable_scale:
            sx = _resolve_range(joint_name, "scale", s, ov, "x")
            sy = _resolve_range(joint_name, "scale", s, ov, "y")
            sz = _resolve_range(joint_name, "scale", s, ov, "z")
            return (
                1.0 + rng.uniform(-sx, sx),
                1.0 + rng.uniform(-sy, sy),
                1.0 + rng.uniform(-sz, sz),
            )
        return identity_scale

    joints: dict[str, ChaosTransform] = {}

    for left_name, right_name in pairs:
        ltx = _resolve_range(left_name, "location", t, ov, "x")
        lty = _resolve_range(left_name, "location", t, ov, "y")
        ltz = _resolve_range(left_name, "location", t, ov, "z")
        lrx = _resolve_range(left_name, "rotation", r, ov, "x")
        lry = _resolve_range(left_name, "rotation", r, ov, "y")
        lrz = _resolve_range(left_name, "rotation", r, ov, "z")

        lx = rng.uniform(-ltx, ltx)
        ly = rng.uniform(-lty, lty)
        lz = rng.uniform(-ltz, ltz)
        rot_x = rng.uniform(-lrx, lrx)
        rot_y = rng.uniform(-lry, lry)
        rot_z = rng.uniform(-lrz, lrz)
        scale = _scale(left_name)

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
        cty = _resolve_range(name, "location", t, ov, "y")
        ctz = _resolve_range(name, "location", t, ov, "z")
        crx = _resolve_range(name, "rotation", r, ov, "x")

        joints[name] = ChaosTransform(
            location=(0.0, rng.uniform(-cty, cty), rng.uniform(-ctz, ctz)),
            rotation=(rng.uniform(-crx, crx), 0.0, 0.0),
            scale=_scale(name),
        )

    return joints


def generate_chaos_transforms(
    config: VariationConfig,
    joint_names: list[str],
) -> dict[int, dict[str, ChaosTransform]]:
    """Return {frame: {joint_name: ChaosTransform}} for every frame in config.

    Uses an optionally seeded RNG so results are reproducible when
    config.seed is set.
    """
    rng = random.Random(config.seed)
    pairs, center = classify_joints(joint_names)

    return {
        frame: _generate_joint_transforms(
            rng, pairs, center,
            config.transform_max, config.rotate_max, config.scale_max,
            config.enable_scale, config.joint_overrides,
        )
        for frame in range(1, config.frame_count + 1)
    }


def generate_single_frame_transforms(
    config: VariationConfig,
    joint_names: list[str],
) -> dict[str, ChaosTransform]:
    """Return {joint_name: ChaosTransform} for a single random variation.

    Uses config.seed if set, otherwise a fresh random seed each call.
    Same symmetry rules as generate_chaos_transforms.
    """
    rng = random.Random(config.seed)
    pairs, center = classify_joints(joint_names)

    return _generate_joint_transforms(
        rng, pairs, center,
        config.transform_max, config.rotate_max, config.scale_max,
        config.enable_scale, config.joint_overrides,
    )

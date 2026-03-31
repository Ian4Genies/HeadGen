"""
Pure Python logic for blendshape variation and expression generation.

No bpy imports — fully testable with pytest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Default shape lists — prune or extend these in BlendshapeConfig
# ---------------------------------------------------------------------------

VARIATION_SHAPES: list[str] = [
    "eyes_female_varGp01A",
    "eyes_female_varGp01B",
    "eyes_female_varGp01C",
    "eyes_female_varGp01E",
    "eyes_female_varGp01G",
    "eyes_female_varGp01I",
    "eyes_male_varGp01D",
    "eyes_male_varGp01F",
    "eyes_male_varGp01H",
    "eyes_male_varGp01J",
    "eyes_male_varGp01K",
    "eyes_male_varGp01L",
    "jaw_female_varGp01A",
    "jaw_female_varGp01B",
    "jaw_female_varGp01D",
    "jaw_female_varGp01F",
    "jaw_female_varGp01H",
    "jaw_female_varGp01K",
    "jaw_male_varGp01A",
    "jaw_male_varGp01D",
    "jaw_male_varGp01E",
    "jaw_male_varGp01H",
    "jaw_male_varGp01K",
    "jaw_male_varGp01L",
    "lips_female_varGp01C",
    "lips_female_varGp01D",
    "lips_female_varGp01E",
    "lips_female_varGp01F",
    "lips_female_varGp01I",
    "lips_female_varGp01J",
    "lips_male_varGp01D",
    "lips_male_varGp01F",
    "lips_male_varGp01G",
    "lips_male_varGp01H",
    "lips_male_varGp01I",
    "lips_male_varGp01K",
    "nose_female_varGp01A",
    "nose_female_varGp01C",
    "nose_female_varGp01D",
    "nose_female_varGp01F",
    "nose_female_varGp01H",
    "nose_female_varGp01K",
    "nose_male_varGp01A",
    "nose_male_varGp01D",
    "nose_male_varGp01E",
    "nose_male_varGp01G",
    "nose_male_varGp01I",
    "nose_male_varGp01K",
]

EXPRESSION_SHAPES: list[str] = [
    "BROW_LOWERER_L",
    "BROW_LOWERER_R",
    "CHEEK_PUFF_L",
    "CHEEK_PUFF_R",
    "CHEEK_RAISER_L",
    "CHEEK_RAISER_R",
    "CHEEK_SUCK_L",
    "CHEEK_SUCK_R",
    "CHIN_DEPRESSOR_B",
    "CHIN_RAISER_B",
    "CHIN_RAISER_T",
    "DIMPLER_L",
    "DIMPLER_R",
    "EYES_CLOSED_L",
    "EYES_CLOSED_R",
    "EYES_LOOK_DOWN_L",
    "EYES_LOOK_DOWN_R",
    "EYES_LOOK_LEFT_L",
    "EYES_LOOK_LEFT_R",
    "EYES_LOOK_RIGHT_L",
    "EYES_LOOK_RIGHT_R",
    "EYES_LOOK_UP_L",
    "EYES_LOOK_UP_R",
    "INNER_BROW_CONTRACTOR_L",
    "INNER_BROW_CONTRACTOR_R",
    "INNER_BROW_RAISER_L",
    "INNER_BROW_RAISER_R",
    "JAW_COMPRESSOR",
    "JAW_DROP",
    "JAW_RETREAT",
    "JAW_SIDEWAYS_LEFT",
    "JAW_SIDEWAYS_RIGHT",
    "JAW_THRUST",
    "LID_TIGHTENER_L",
    "LID_TIGHTENER_R",
    "LIPS_TOWARD",
    "LIP_CORNER_DEPRESSOR_L",
    "LIP_CORNER_DEPRESSOR_R",
    "LIP_CORNER_PULLER_L",
    "LIP_CORNER_PULLER_R",
    "LIP_FUNNELER_LB",
    "LIP_FUNNELER_LT",
    "LIP_FUNNELER_RB",
    "LIP_FUNNELER_RT",
    "LIP_PRESSOR_L",
    "LIP_PRESSOR_R",
    "LIP_PUCKER_L",
    "LIP_PUCKER_R",
    "LIP_STRETCHER_L",
    "LIP_STRETCHER_R",
    "LIP_SUCK_LB",
    "LIP_SUCK_LT",
    "LIP_SUCK_RB",
    "LIP_SUCK_RT",
    "LIP_TIGHTENER_L",
    "LIP_TIGHTENER_R",
    "LOWER_LIP_DEPRESSOR_L",
    "LOWER_LIP_DEPRESSOR_R",
    "MOUTH_LEFT",
    "MOUTH_LOWERER",
    "MOUTH_RAISER",
    "MOUTH_RIGHT",
    "NOSE_WRINKLER_L",
    "NOSE_WRINKLER_R",
    "OUTER_BROW_RAISER_L",
    "OUTER_BROW_RAISER_R",
    "UPPER_LID_RAISER_L",
    "UPPER_LID_RAISER_R",
    "UPPER_LIP_RAISER_L",
    "UPPER_LIP_RAISER_R",
]


# ---------------------------------------------------------------------------
# Per-shape override defaults
# ---------------------------------------------------------------------------

DEFAULT_VARIATION_OVERRIDES: dict[str, float] = {
    # Variation shapes are normalized within each feature group, so the
    # override here caps the *maximum contribution* any single shape can
    # receive from that group's budget.  Values are in [0, max_variation].
    # Add entries for any shape that should be capped below the group max.
}

DEFAULT_EXPRESSION_OVERRIDES: dict[str, float] = {
    # Expression shapes that need tighter individual caps than expression_max.
    "CHEEK_PUFF_L":      0.3,
    "CHEEK_PUFF_R":      0.3,
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class BlendshapeConfig:
    frame_count: int = 400
    seed: int | None = None

    variation_shapes: list[str] = field(default_factory=lambda: list(VARIATION_SHAPES))
    max_var_shapes: int = 4
    max_variation: float = 1
    variation_overrides: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_VARIATION_OVERRIDES),
    )

    expression_shapes: list[str] = field(default_factory=lambda: list(EXPRESSION_SHAPES))
    expression_max: float = 0
    expression_overrides: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_EXPRESSION_OVERRIDES),
    )

    @classmethod
    def from_dict(
        cls,
        data: dict,
        frame_count: int = 400,
        seed: int | None = None,
    ) -> "BlendshapeConfig":
        return cls(
            frame_count=frame_count,
            seed=seed,
            variation_shapes=data.get("variation_shapes", list(VARIATION_SHAPES)),
            max_var_shapes=data.get("max_var_shapes", 4),
            max_variation=data.get("max_variation", 1.0),
            variation_overrides=data.get("variation_overrides", dict(DEFAULT_VARIATION_OVERRIDES)),
            expression_shapes=data.get("expression_shapes", list(EXPRESSION_SHAPES)),
            expression_max=data.get("expression_max", 0.0),
            expression_overrides=data.get("expression_overrides", dict(DEFAULT_EXPRESSION_OVERRIDES)),
        )


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def classify_variation_shapes(
    names: list[str],
) -> dict[str, list[str]]:
    """Group variation shape names by feature (first underscore-delimited segment).

    Example: ``"eyes_female_varGp01A"`` → group ``"eyes"``.
    """
    groups: dict[str, list[str]] = {}
    for name in names:
        feature = name.split("_", 1)[0]
        groups.setdefault(feature, []).append(name)
    return groups


def classify_expression_shapes(
    names: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Split expression shapes into symmetric (L/R) pairs and unpaired center shapes.

    Pairing rules:
    - ``_L`` / ``_R`` suffix → paired.
    - ``_LB`` / ``_RB`` and ``_LT`` / ``_RT`` suffix → paired.
    - Everything else → center (unpaired).
    """
    by_base: dict[str, dict[str, str]] = {}

    for name in names:
        if name.endswith("_L"):
            base = name[:-2]
            by_base.setdefault(base, {})["L"] = name
        elif name.endswith("_R"):
            base = name[:-2]
            by_base.setdefault(base, {})["R"] = name
        elif name.endswith("_LB"):
            base = name[:-3] + "_B"
            by_base.setdefault(base, {})["L"] = name
        elif name.endswith("_RB"):
            base = name[:-3] + "_B"
            by_base.setdefault(base, {})["R"] = name
        elif name.endswith("_LT"):
            base = name[:-3] + "_T"
            by_base.setdefault(base, {})["L"] = name
        elif name.endswith("_RT"):
            base = name[:-3] + "_T"
            by_base.setdefault(base, {})["R"] = name
        else:
            by_base.setdefault(name, {})["C"] = name

    pairs: list[tuple[str, str]] = []
    center: list[str] = []

    for base in sorted(by_base):
        sides = by_base[base]
        if "L" in sides and "R" in sides:
            pairs.append((sides["L"], sides["R"]))
        else:
            center.extend(sorted(sides.values()))

    return pairs, center


# ---------------------------------------------------------------------------
# Weight generation (single frame — shared inner function)
# ---------------------------------------------------------------------------

def _resolve_shape_max(
    name: str,
    global_max: float,
    overrides: dict[str, float],
) -> float:
    """Return the per-shape max, falling back to *global_max* if not overridden."""
    return overrides.get(name, global_max)


def _generate_blendshape_weights(
    rng: random.Random,
    var_groups: dict[str, list[str]],
    expr_pairs: list[tuple[str, str]],
    expr_center: list[str],
    max_var_shapes: int,
    max_variation: float,
    expression_max: float,
    variation_overrides: dict[str, float] | None = None,
    expression_overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    """Generate one frame of blendshape weights.

    Variation shapes: for each feature group, pick 1..max_var_shapes shapes
    and distribute *max_variation* across them randomly.  Any shape with a
    ``variation_overrides`` entry is additionally capped at that value after
    normalization.

    Expression shapes: L/R pairs get the same random value sampled from
    [0, per-shape max]; center shapes get an independent random value.
    Per-shape maxes are resolved from ``expression_overrides``, falling back
    to *expression_max*.
    """
    var_ov = variation_overrides or {}
    expr_ov = expression_overrides or {}
    weights: dict[str, float] = {}

    for _feature, members in var_groups.items():
        count = rng.randint(1, min(max_var_shapes, len(members)))
        selected = rng.sample(members, count)
        selected_set = set(selected)

        raw = [rng.random() for _ in selected]
        total = sum(raw)
        if total == 0.0:
            normalized = [max_variation / count] * count
        else:
            normalized = [v / total * max_variation for v in raw]

        for name, weight in zip(selected, normalized):
            cap = _resolve_shape_max(name, max_variation, var_ov)
            weights[name] = min(weight, cap)

        for name in members:
            if name not in selected_set:
                weights[name] = 0.0

    all_expr = {n for pair in expr_pairs for n in pair} | set(expr_center)
    for name in all_expr:
        weights[name] = 0.0

    for left, right in expr_pairs:
        left_max = _resolve_shape_max(left, expression_max, expr_ov)
        right_max = _resolve_shape_max(right, expression_max, expr_ov)
        shared_max = min(left_max, right_max)
        val = rng.uniform(0.0, shared_max)
        weights[left] = val
        weights[right] = val

    for name in expr_center:
        shape_max = _resolve_shape_max(name, expression_max, expr_ov)
        weights[name] = rng.uniform(0.0, shape_max)

    return weights


# ---------------------------------------------------------------------------
# Public API — multi-frame and single-frame
# ---------------------------------------------------------------------------

def generate_blendshape_weights(
    config: BlendshapeConfig,
) -> dict[int, dict[str, float]]:
    """Return ``{frame: {shape_name: weight}}`` for every frame in config."""
    rng = random.Random(config.seed)
    var_groups = classify_variation_shapes(config.variation_shapes)
    expr_pairs, expr_center = classify_expression_shapes(config.expression_shapes)

    return {
        frame: _generate_blendshape_weights(
            rng, var_groups, expr_pairs, expr_center,
            config.max_var_shapes, config.max_variation, config.expression_max,
            config.variation_overrides, config.expression_overrides,
        )
        for frame in range(1, config.frame_count + 1)
    }


def generate_single_frame_blendshape_weights(
    config: BlendshapeConfig,
) -> dict[str, float]:
    """Return ``{shape_name: weight}`` for a single random frame."""
    rng = random.Random(config.seed)
    var_groups = classify_variation_shapes(config.variation_shapes)
    expr_pairs, expr_center = classify_expression_shapes(config.expression_shapes)

    return _generate_blendshape_weights(
        rng, var_groups, expr_pairs, expr_center,
        config.max_var_shapes, config.max_variation, config.expression_max,
        config.variation_overrides, config.expression_overrides,
    )

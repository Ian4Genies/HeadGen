"""Tests for synth_head.core.constraints."""

from __future__ import annotations

from pathlib import Path

import pytest

from synth_head.core.variation import ChaosTransform, CHAOS_JOINT_NAMES
from synth_head.core.blendshapes import VARIATION_SHAPES, EXPRESSION_SHAPES
from synth_head.core.constraints import (
    ClampRange,
    ConstraintRules,
    ValidationReport,
    apply_hard_clamps,
    apply_relational_rules,
    constrain,
    expand_joint_keys,
    flatten_params,
    load_rules,
    unflatten_params,
    validate_rules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JOINT_NAMES = ["JawBind", "NoseBind"]

def _sample_transforms() -> dict[str, ChaosTransform]:
    return {
        "JawBind": ChaosTransform(
            location=(0.1, -0.2, 0.05),
            rotation=(5.0, -3.0, 1.0),
            scale=(1.1, 0.9, 1.05),
        ),
        "NoseBind": ChaosTransform(
            location=(0.0, 0.12, -0.04),
            rotation=(2.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        ),
    }

def _sample_bs_weights() -> dict[str, float]:
    return {"JAW_DROP": 0.7, "MOUTH_LOWERER": 0.4, "NOSE_WRINKLER_L": 0.15}


# ---------------------------------------------------------------------------
# Flatten / unflatten
# ---------------------------------------------------------------------------

class TestFlattenUnflatten:
    def test_round_trip(self):
        xforms = _sample_transforms()
        bs = _sample_bs_weights()
        flat = flatten_params(xforms, bs)
        xforms_out, bs_out = unflatten_params(flat, _JOINT_NAMES)

        for name in _JOINT_NAMES:
            assert xforms_out[name].location == pytest.approx(xforms[name].location)
            assert xforms_out[name].rotation == pytest.approx(xforms[name].rotation)
            assert xforms_out[name].scale == pytest.approx(xforms[name].scale)

        assert bs_out == pytest.approx(bs)

    def test_flat_keys_present(self):
        flat = flatten_params(_sample_transforms(), _sample_bs_weights())
        assert "JawBind.location.x" in flat
        assert "NoseBind.rotation.y" in flat
        assert "JAW_DROP" in flat
        assert "MOUTH_LOWERER" in flat

    def test_flat_values_correct(self):
        flat = flatten_params(_sample_transforms(), _sample_bs_weights())
        assert flat["JawBind.location.x"] == pytest.approx(0.1)
        assert flat["JawBind.rotation.y"] == pytest.approx(-3.0)
        assert flat["JAW_DROP"] == pytest.approx(0.7)

    def test_expand_joint_keys_count(self):
        keys = expand_joint_keys("FooBind")
        assert len(keys) == 9
        assert "FooBind.location.x" in keys
        assert "FooBind.scale.z" in keys


# ---------------------------------------------------------------------------
# Hard clamps
# ---------------------------------------------------------------------------

class TestHardClamps:
    def test_clamp_max(self):
        flat = {"A": 1.5}
        clamps = {"A": ClampRange(max=1.0)}
        result = apply_hard_clamps(flat, clamps)
        assert result["A"] == pytest.approx(1.0)

    def test_clamp_min(self):
        flat = {"A": -0.5}
        clamps = {"A": ClampRange(min=0.0)}
        result = apply_hard_clamps(flat, clamps)
        assert result["A"] == pytest.approx(0.0)

    def test_clamp_both(self):
        flat = {"A": 2.0}
        clamps = {"A": ClampRange(min=-1.0, max=1.0)}
        result = apply_hard_clamps(flat, clamps)
        assert result["A"] == pytest.approx(1.0)

    def test_within_range_unchanged(self):
        flat = {"A": 0.5}
        clamps = {"A": ClampRange(min=0.0, max=1.0)}
        result = apply_hard_clamps(flat, clamps)
        assert result["A"] == pytest.approx(0.5)

    def test_missing_key_skipped(self):
        flat = {"A": 0.5}
        clamps = {"MISSING": ClampRange(min=0.0, max=1.0)}
        result = apply_hard_clamps(flat, clamps)
        assert result == {"A": 0.5}


# ---------------------------------------------------------------------------
# Relational rules
# ---------------------------------------------------------------------------

class TestScaleFollow:
    def test_basic(self):
        flat = {"src": 0.4, "tgt": 999.0}
        rules = [{"type": "scale_follow", "source": "src", "target": "tgt", "factor": 0.5}]
        result = apply_relational_rules(flat, rules)
        assert result["tgt"] == pytest.approx(0.2)

    def test_missing_source_skipped(self):
        flat = {"tgt": 1.0}
        rules = [{"type": "scale_follow", "source": "GONE", "target": "tgt", "factor": 2.0}]
        result = apply_relational_rules(flat, rules)
        assert result["tgt"] == pytest.approx(1.0)

    def test_missing_target_skipped(self):
        flat = {"src": 1.0}
        rules = [{"type": "scale_follow", "source": "src", "target": "GONE", "factor": 2.0}]
        result = apply_relational_rules(flat, rules)
        assert "GONE" not in result


class TestConditionalClamp:
    def test_triggered_above(self):
        flat = {"cond": 0.8, "tgt": 0.9}
        rules = [{"type": "conditional_clamp", "target": "tgt",
                  "condition": {"param": "cond", "above": 0.5}, "max": 0.2}]
        result = apply_relational_rules(flat, rules)
        assert result["tgt"] == pytest.approx(0.2)

    def test_not_triggered(self):
        flat = {"cond": 0.3, "tgt": 0.9}
        rules = [{"type": "conditional_clamp", "target": "tgt",
                  "condition": {"param": "cond", "above": 0.5}, "max": 0.2}]
        result = apply_relational_rules(flat, rules)
        assert result["tgt"] == pytest.approx(0.9)

    def test_missing_condition_param_skipped(self):
        flat = {"tgt": 0.9}
        rules = [{"type": "conditional_clamp", "target": "tgt",
                  "condition": {"param": "GONE", "above": 0.5}, "max": 0.2}]
        result = apply_relational_rules(flat, rules)
        assert result["tgt"] == pytest.approx(0.9)


class TestMutualDampen:
    def test_dampens(self):
        flat = {"A": 0.8, "B": 0.6}
        rules = [{"type": "mutual_dampen", "params": ["A", "B"], "max_combined": 1.0}]
        result = apply_relational_rules(flat, rules)
        assert abs(result["A"]) + abs(result["B"]) == pytest.approx(1.0)

    def test_within_budget_unchanged(self):
        flat = {"A": 0.3, "B": 0.4}
        rules = [{"type": "mutual_dampen", "params": ["A", "B"], "max_combined": 1.0}]
        result = apply_relational_rules(flat, rules)
        assert result["A"] == pytest.approx(0.3)
        assert result["B"] == pytest.approx(0.4)

    def test_partially_missing(self):
        flat = {"A": 0.8}
        rules = [{"type": "mutual_dampen", "params": ["A", "GONE"], "max_combined": 0.5}]
        result = apply_relational_rules(flat, rules)
        assert result["A"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Constrain (integration)
# ---------------------------------------------------------------------------

class TestConstrain:
    def test_relational_then_clamp(self):
        flat = {"src": 0.6, "tgt": 999.0}
        rules = ConstraintRules(
            hard_clamps={"tgt": ClampRange(max=0.5)},
            relational_rules=[
                {"type": "scale_follow", "source": "src", "target": "tgt", "factor": 2.0},
            ],
        )
        result = constrain(flat, rules)
        # scale_follow: tgt = 0.6 * 2.0 = 1.2, then clamp to 0.5
        assert result["tgt"] == pytest.approx(0.5)

    def test_unknown_rule_type_skipped(self):
        flat = {"A": 1.0}
        rules = ConstraintRules(
            relational_rules=[{"type": "nonexistent_type", "target": "A"}],
        )
        result = constrain(flat, rules)
        assert result["A"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Pruned / added params
# ---------------------------------------------------------------------------

class TestPrunedParams:
    def test_clamp_on_pruned_param_is_noop(self):
        flat = {"A": 0.5}
        rules = ConstraintRules(
            hard_clamps={"PRUNED": ClampRange(min=0.0, max=1.0)},
        )
        result = constrain(flat, rules)
        assert result == {"A": 0.5}

    def test_relational_rule_with_pruned_source(self):
        flat = {"tgt": 1.0}
        rules = ConstraintRules(
            relational_rules=[
                {"type": "scale_follow", "source": "PRUNED", "target": "tgt", "factor": 2.0},
            ],
        )
        result = constrain(flat, rules)
        assert result["tgt"] == pytest.approx(1.0)

    def test_relational_rule_with_pruned_target(self):
        flat = {"src": 1.0}
        rules = ConstraintRules(
            relational_rules=[
                {"type": "scale_follow", "source": "src", "target": "PRUNED", "factor": 2.0},
            ],
        )
        result = constrain(flat, rules)
        assert "PRUNED" not in result


class TestAddedParams:
    def test_unconstrained_param_passes_through(self):
        flat = {"NEW_PARAM": 0.99, "A": 0.5}
        rules = ConstraintRules(
            hard_clamps={"A": ClampRange(max=0.6)},
        )
        result = constrain(flat, rules)
        assert result["NEW_PARAM"] == pytest.approx(0.99)
        assert result["A"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateRules:
    def test_stale_keys_detected(self):
        rules = ConstraintRules(
            hard_clamps={"STALE_PARAM": ClampRange(max=1.0)},
        )
        report = validate_rules(rules, {"A", "B"})
        assert "STALE_PARAM" in report.stale_keys

    def test_unconstrained_detected(self):
        rules = ConstraintRules(
            hard_clamps={"A": ClampRange(max=1.0)},
        )
        report = validate_rules(rules, {"A", "B"})
        assert "B" in report.unconstrained_params
        assert "A" not in report.unconstrained_params

    def test_clean_rules_no_stale(self):
        rules = ConstraintRules(
            hard_clamps={"A": ClampRange(max=1.0)},
        )
        report = validate_rules(rules, {"A"})
        assert report.stale_keys == []

    def test_relational_source_counted(self):
        rules = ConstraintRules(
            relational_rules=[
                {"type": "scale_follow", "source": "STALE_SRC", "target": "A", "factor": 1.0},
            ],
        )
        report = validate_rules(rules, {"A"})
        assert "STALE_SRC" in report.stale_keys


# ---------------------------------------------------------------------------
# Live validation against real configs
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _build_known_params() -> set[str]:
    """Build the full set of known parameter keys from the current configs."""
    params: set[str] = set()
    for joint in CHAOS_JOINT_NAMES:
        params.update(expand_joint_keys(joint))
    params.update(VARIATION_SHAPES)
    params.update(EXPRESSION_SHAPES)
    return params


def test_validate_live_rules():
    """Sanity check: every key in constraint_rules.json must reference a
    parameter that actually exists in the current joint/shape configs.

    Run with: ``pytest -k validate_live_rules -v``

    If this fails, the constraint_rules.json contains stale references that
    should be pruned.
    """
    rules_path = _DATA_DIR / "constraint_rules.json"
    if not rules_path.exists():
        pytest.skip("constraint_rules.json not found")

    rules = load_rules(rules_path)
    known = _build_known_params()
    report = validate_rules(rules, known)

    if report.stale_keys:
        lines = ["Stale keys in constraint_rules.json (no matching param):"]
        for key in report.stale_keys:
            lines.append(f"  - {key}")
        pytest.fail("\n".join(lines))


# ---------------------------------------------------------------------------
# Load from file
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_load_starter_json(self):
        rules_path = _DATA_DIR / "constraint_rules.json"
        if not rules_path.exists():
            pytest.skip("constraint_rules.json not found")
        rules = load_rules(rules_path)
        assert len(rules.hard_clamps) > 0
        assert len(rules.relational_rules) > 0

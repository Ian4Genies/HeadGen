"""Tests for synth_head.core.rerandomize."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from synth_head.core.config import PipelineConfig, load_config
from synth_head.core.constraints import ConstraintRules, flatten_params
from synth_head.core.rerandomize import (
    ResolvedTarget,
    build_param_registry,
    expand_constraint_peers,
    rerandomize_flat,
    resolve_targets,
    sample_value,
    _keys_changed_by_constrain,
)
from synth_head.core.variation import ChaosTransform, VariationConfig
from synth_head.core.blendshapes import BlendshapeConfig

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "data" / "config"


@pytest.fixture
def cfg() -> PipelineConfig:
    return load_config(_CONFIG_DIR)


class TestResolveTargets:
    def test_property_prefix(self, cfg: PipelineConfig):
        resolved, errors = resolve_targets(["property:var_iris_shrink"], cfg)
        assert not errors
        assert resolved == [ResolvedTarget(key="var_iris_shrink", kind="bone_property")]

    def test_plain_blendshape(self, cfg: PipelineConfig):
        resolved, errors = resolve_targets(["nose_female_varGp01C"], cfg)
        assert not errors
        assert resolved == [ResolvedTarget(key="nose_female_varGp01C", kind="blendshape")]

    def test_joint_flat_key(self, cfg: PipelineConfig):
        resolved, errors = resolve_targets(["JawBind.scale.y"], cfg)
        assert not errors
        assert resolved == [ResolvedTarget(key="JawBind.scale.y", kind="joint")]

    def test_joint_rotate_alias(self, cfg: PipelineConfig):
        resolved, errors = resolve_targets(["NoseBind.rotate.x"], cfg)
        assert not errors
        assert resolved == [ResolvedTarget(key="NoseBind.rotation.x", kind="joint")]

    def test_property_wildcard(self, cfg: PipelineConfig):
        resolved, errors = resolve_targets(["property:var_iris_*"], cfg)
        assert not errors
        keys = {t.key for t in resolved}
        assert keys == {"var_iris_shrink", "var_iris_grow"}

    def test_unknown_target_errors(self, cfg: PipelineConfig):
        _, errors = resolve_targets(["not_a_real_parameter"], cfg)
        assert any("Unknown target" in e for e in errors)

    def test_collision_defaults_to_blendshape(self):
        variation = VariationConfig(
            bone_properties={"shared_name": {"min": 0.0, "max": 1.0, "target_bone": "JawBind"}},
        )
        blendshapes = BlendshapeConfig(
            variation_shapes=["shared_name"],
            max_variation=1.0,
        )
        mini_cfg = PipelineConfig(
            variation=variation,
            blendshapes=blendshapes,
            chaos_joint_names=frozenset({"JawBind"}),
        )
        resolved, errors = resolve_targets(["shared_name"], mini_cfg)
        assert not errors
        assert resolved == [ResolvedTarget(key="shared_name", kind="blendshape")]


class TestRerandomizeFlat:
    def _flat_sample(self) -> dict[str, float]:
        xforms = {
            "JawBind": ChaosTransform(
                location=(0.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0),
                scale=(1.0, 1.0, 1.0),
            ),
        }
        bs = {
            "nose_female_varGp01C": 0.25,
            "var_iris_shrink": 0.5,
            "var_iris_grow": 0.3,
        }
        return flatten_params(xforms, bs)

    def test_target_changes_non_target_unchanged(self, cfg: PipelineConfig):
        flat = self._flat_sample()
        original_nose = flat["nose_female_varGp01C"]
        targets = [ResolvedTarget(key="JawBind.scale.y", kind="joint")]
        rng = random.Random(42)

        new_flat, apply_keys = rerandomize_flat(flat, targets, rng, cfg)

        assert new_flat["JawBind.scale.y"] != flat["JawBind.scale.y"]
        assert new_flat["nose_female_varGp01C"] == pytest.approx(original_nose)
        assert "JawBind.scale.y" in apply_keys

    def test_constraint_peers_included(self, cfg: PipelineConfig):
        flat = self._flat_sample()
        targets = [ResolvedTarget(key="var_iris_shrink", kind="bone_property")]
        rng = random.Random(99)

        new_flat, apply_keys = rerandomize_flat(flat, targets, rng, cfg)

        assert "var_iris_shrink" in apply_keys
        assert "var_iris_grow" in apply_keys
        assert new_flat["var_iris_shrink"] >= new_flat["var_iris_grow"]

    def test_seeded_reproducibility(self, cfg: PipelineConfig):
        flat = self._flat_sample()
        targets = [
            ResolvedTarget(key="nose_female_varGp01C", kind="blendshape"),
            ResolvedTarget(key="var_iris_shrink", kind="bone_property"),
        ]

        a, _ = rerandomize_flat(flat, targets, random.Random(123), cfg)
        b, _ = rerandomize_flat(flat, targets, random.Random(123), cfg)

        assert a["nose_female_varGp01C"] == pytest.approx(b["nose_female_varGp01C"])
        assert a["var_iris_shrink"] == pytest.approx(b["var_iris_shrink"])

    def test_reapply_constraints_false_limits_apply_keys(self, cfg: PipelineConfig):
        cfg.rerandomize.reapply_constraints = False
        flat = self._flat_sample()
        targets = [ResolvedTarget(key="NoseBind.scale.x", kind="joint")]

        _, apply_keys = rerandomize_flat(flat, targets, random.Random(0), cfg)

        assert apply_keys == {"NoseBind.scale.x"}

    def test_paired_joint_scale_matches_left_and_right(self, cfg: PipelineConfig):
        flat = {
            "LeftEyeSocketBind.scale.x": 1.0,
            "RightEyeSocketBind.scale.x": 1.0,
            "LeftEyeSocketBind.scale.y": 1.0,
            "RightEyeSocketBind.scale.y": 1.0,
        }
        targets = [
            ResolvedTarget(key="LeftEyeSocketBind.scale.x", kind="joint"),
            ResolvedTarget(key="RightEyeSocketBind.scale.x", kind="joint"),
            ResolvedTarget(key="LeftEyeSocketBind.scale.y", kind="joint"),
            ResolvedTarget(key="RightEyeSocketBind.scale.y", kind="joint"),
        ]
        new_flat, apply_keys = rerandomize_flat(
            flat, targets, random.Random(7), cfg,
        )
        assert new_flat["LeftEyeSocketBind.scale.x"] == pytest.approx(
            new_flat["RightEyeSocketBind.scale.x"],
        )
        assert new_flat["LeftEyeSocketBind.scale.y"] == pytest.approx(
            new_flat["RightEyeSocketBind.scale.y"],
        )
        assert "LeftEyeSocketBind.scale.x" in apply_keys
        assert "RightEyeSocketBind.scale.x" in apply_keys

    def test_paired_joint_left_only_target_mirrors_right(self, cfg: PipelineConfig):
        cfg.rerandomize.reapply_constraints = False
        flat = {
            "LeftEyeSocketBind.scale.x": 1.0,
            "RightEyeSocketBind.scale.x": 1.0,
        }
        targets = [ResolvedTarget(key="LeftEyeSocketBind.scale.x", kind="joint")]
        new_flat, apply_keys = rerandomize_flat(
            flat, targets, random.Random(3), cfg,
        )
        assert new_flat["LeftEyeSocketBind.scale.x"] == pytest.approx(
            new_flat["RightEyeSocketBind.scale.x"],
        )
        assert "RightEyeSocketBind.scale.x" in apply_keys

    def test_mirrors_right_when_partner_not_in_chaos_joint_names(self, cfg: PipelineConfig):
        from dataclasses import replace

        cfg = replace(
            cfg,
            chaos_joint_names=frozenset({"LeftEyeSocketBind", "JawBind"}),
        )
        cfg.rerandomize.reapply_constraints = False
        flat = {
            "LeftEyeSocketBind.scale.x": 1.0,
            "RightEyeSocketBind.scale.x": 0.9,
        }
        targets = [ResolvedTarget(key="LeftEyeSocketBind.scale.x", kind="joint")]
        new_flat, apply_keys = rerandomize_flat(
            flat, targets, random.Random(5), cfg,
        )
        assert new_flat["LeftEyeSocketBind.scale.x"] == pytest.approx(
            new_flat["RightEyeSocketBind.scale.x"],
        )
        assert "RightEyeSocketBind.scale.x" in apply_keys

    def test_paired_joint_location_x_mirrors_sign(self, cfg: PipelineConfig):
        cfg.rerandomize.reapply_constraints = False
        flat = {
            "LeftEyeSocketBind.location.x": 0.0,
            "RightEyeSocketBind.location.x": 0.0,
        }
        targets = [ResolvedTarget(key="LeftEyeSocketBind.location.x", kind="joint")]
        new_flat, _ = rerandomize_flat(flat, targets, random.Random(11), cfg)
        assert new_flat["LeftEyeSocketBind.location.x"] == pytest.approx(
            -new_flat["RightEyeSocketBind.location.x"],
        )

    def test_constrain_can_expand_nose_scale_apply_keys(self, cfg: PipelineConfig):
        flat = {
            "NoseBind.scale.x": 0.5,
            "NoseBind.scale.y": 1.2,
            "NoseBind.scale.z": 1.2,
        }
        changed = _keys_changed_by_constrain(
            {"NoseBind.scale.x": 0.5, "NoseBind.scale.y": 1.2, "NoseBind.scale.z": 1.2},
            {"NoseBind.scale.x": 0.5, "NoseBind.scale.y": 1.0, "NoseBind.scale.z": 0.9},
        )
        assert "NoseBind.scale.y" in changed
        assert "NoseBind.scale.z" in changed


class TestExpandConstraintPeers:
    def test_winner_take_all_expansion(self):
        rules = ConstraintRules.from_dict({
            "relational_rules": [{
                "type": "winner_take_all",
                "params": ["var_iris_grow", "var_iris_shrink"],
            }],
        })
        peers = expand_constraint_peers({"var_iris_shrink"}, rules)
        assert peers == {"var_iris_shrink", "var_iris_grow"}


class TestSampleValue:
    def test_value_within_range(self, cfg: PipelineConfig):
        rng = random.Random(0)
        for _ in range(20):
            val = sample_value("var_iris_shrink", rng, cfg)
            assert 0.2 <= val <= 1.0

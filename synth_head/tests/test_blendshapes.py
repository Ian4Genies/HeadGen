"""Tests for synth_head.core.blendshapes."""

import pytest

from synth_head.core.blendshapes import (
    VARIATION_SHAPES,
    EXPRESSION_SHAPES,
    DEFAULT_VARIATION_OVERRIDES,
    DEFAULT_EXPRESSION_OVERRIDES,
    BlendshapeConfig,
    _resolve_shape_max,
    classify_variation_shapes,
    classify_expression_shapes,
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
)

# Subsets for focused tests
_FEW_VAR_SHAPES = [
    "eyes_female_varGp01A",
    "eyes_male_varGp01D",
    "nose_female_varGp01A",
    "nose_male_varGp01D",
    "nose_male_varGp01E",
]

_FEW_EXPR_SHAPES = [
    "BROW_LOWERER_L",
    "BROW_LOWERER_R",
    "JAW_DROP",
    "LIP_FUNNELER_LB",
    "LIP_FUNNELER_RB",
    "MOUTH_LEFT",
]


class TestClassifyVariationShapes:
    def test_groups_by_feature(self):
        groups = classify_variation_shapes(_FEW_VAR_SHAPES)
        assert set(groups.keys()) == {"eyes", "nose"}

    def test_all_names_present(self):
        groups = classify_variation_shapes(_FEW_VAR_SHAPES)
        flat = [n for members in groups.values() for n in members]
        assert sorted(flat) == sorted(_FEW_VAR_SHAPES)

    def test_full_list_has_four_groups(self):
        groups = classify_variation_shapes(VARIATION_SHAPES)
        assert set(groups.keys()) == {"eyes", "jaw", "lips", "nose"}

    def test_empty_list(self):
        assert classify_variation_shapes([]) == {}


class TestClassifyExpressionShapes:
    def test_lr_suffix_paired(self):
        pairs, _ = classify_expression_shapes(_FEW_EXPR_SHAPES)
        assert ("BROW_LOWERER_L", "BROW_LOWERER_R") in pairs

    def test_lb_rb_suffix_paired(self):
        pairs, _ = classify_expression_shapes(_FEW_EXPR_SHAPES)
        assert ("LIP_FUNNELER_LB", "LIP_FUNNELER_RB") in pairs

    def test_center_detected(self):
        _, center = classify_expression_shapes(_FEW_EXPR_SHAPES)
        assert "JAW_DROP" in center
        assert "MOUTH_LEFT" in center

    def test_paired_not_in_center(self):
        _, center = classify_expression_shapes(_FEW_EXPR_SHAPES)
        for name in ("BROW_LOWERER_L", "BROW_LOWERER_R",
                      "LIP_FUNNELER_LB", "LIP_FUNNELER_RB"):
            assert name not in center

    def test_full_list_pairing(self):
        pairs, center = classify_expression_shapes(EXPRESSION_SHAPES)
        paired_names = {n for p in pairs for n in p}
        center_names = set(center)
        assert not paired_names & center_names
        assert len(paired_names) + len(center_names) == len(EXPRESSION_SHAPES)

    def test_empty_list(self):
        pairs, center = classify_expression_shapes([])
        assert pairs == []
        assert center == []


class TestBlendshapeConfig:
    def test_defaults(self):
        cfg = BlendshapeConfig()
        assert cfg.frame_count == 400
        assert cfg.max_var_shapes == 4
        assert cfg.max_variation == pytest.approx(0.5)
        assert cfg.expression_max == pytest.approx(0.2)
        assert cfg.seed is None

    def test_defaults_to_default_overrides(self):
        cfg = BlendshapeConfig()
        assert cfg.variation_overrides == DEFAULT_VARIATION_OVERRIDES
        assert cfg.expression_overrides == DEFAULT_EXPRESSION_OVERRIDES

    def test_override_dicts_are_independent_copies(self):
        cfg_a = BlendshapeConfig()
        cfg_b = BlendshapeConfig()
        assert cfg_a.expression_overrides is not cfg_b.expression_overrides

    def test_default_lists_populated(self):
        cfg = BlendshapeConfig()
        assert len(cfg.variation_shapes) == len(VARIATION_SHAPES)
        assert len(cfg.expression_shapes) == len(EXPRESSION_SHAPES)

    def test_lists_are_independent_copies(self):
        cfg = BlendshapeConfig()
        cfg.variation_shapes.pop()
        assert len(cfg.variation_shapes) != len(VARIATION_SHAPES)


class TestGenerateBlendshapeWeights:
    def test_frame_count(self):
        cfg = BlendshapeConfig(frame_count=5, seed=42)
        result = generate_blendshape_weights(cfg)
        assert set(result.keys()) == {1, 2, 3, 4, 5}

    def test_seed_determinism(self):
        cfg_a = BlendshapeConfig(frame_count=3, seed=99)
        cfg_b = BlendshapeConfig(frame_count=3, seed=99)
        assert generate_blendshape_weights(cfg_a) == generate_blendshape_weights(cfg_b)

    def test_different_seeds_differ(self):
        cfg_a = BlendshapeConfig(frame_count=3, seed=1)
        cfg_b = BlendshapeConfig(frame_count=3, seed=2)
        assert generate_blendshape_weights(cfg_a) != generate_blendshape_weights(cfg_b)

    def test_zero_frames(self):
        cfg = BlendshapeConfig(frame_count=0, seed=42)
        assert generate_blendshape_weights(cfg) == {}


class TestSingleFrameBlendshapeWeights:
    def test_returns_flat_dict(self):
        cfg = BlendshapeConfig(seed=42)
        result = generate_single_frame_blendshape_weights(cfg)
        assert isinstance(result, dict)
        for v in result.values():
            assert isinstance(v, float)

    def test_matches_first_frame(self):
        cfg = BlendshapeConfig(frame_count=5, seed=42)
        multi = generate_blendshape_weights(cfg)
        single = generate_single_frame_blendshape_weights(cfg)
        assert single == multi[1]

    def test_seed_determinism(self):
        cfg_a = BlendshapeConfig(seed=77)
        cfg_b = BlendshapeConfig(seed=77)
        assert generate_single_frame_blendshape_weights(cfg_a) == \
               generate_single_frame_blendshape_weights(cfg_b)


class TestVariationNormalization:
    """Verify that variation shape weights per group sum to max_variation."""

    def _get_group_weights(self, weights, groups):
        """Extract non-zero weights per feature group from a flat weight dict."""
        result = {}
        for feature, members in groups.items():
            group_w = {n: weights[n] for n in members if weights.get(n, 0.0) > 0.0}
            if group_w:
                result[feature] = group_w
        return result

    def test_weights_sum_to_max_variation(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=1,
            max_variation=1.0, max_var_shapes=4,
            variation_overrides={},
        )
        weights = generate_single_frame_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)
        group_weights = self._get_group_weights(weights, groups)

        for feature, gw in group_weights.items():
            assert sum(gw.values()) == pytest.approx(1.0), \
                f"{feature} weights don't sum to max_variation"

    def test_custom_max_variation(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=1,
            max_variation=0.6, max_var_shapes=4,
            variation_overrides={},
        )
        weights = generate_single_frame_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)
        group_weights = self._get_group_weights(weights, groups)

        for feature, gw in group_weights.items():
            assert sum(gw.values()) == pytest.approx(0.6), \
                f"{feature} weights don't sum to 0.6"

    def test_shape_count_within_bounds(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=10, max_var_shapes=2, variation_overrides={},
        )
        result = generate_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)

        for frame_weights in result.values():
            for feature, members in groups.items():
                active = [n for n in members if frame_weights.get(n, 0.0) > 0.0]
                assert 1 <= len(active) <= 2, \
                    f"{feature} has {len(active)} active shapes (expected 1-2)"

    def test_all_weights_positive(self):
        cfg = BlendshapeConfig(seed=42, frame_count=5)
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            for name, val in frame_weights.items():
                assert val >= 0.0, f"{name} has negative weight {val}"


class TestExpressionSymmetry:
    """Verify L/R expression pairs get identical values."""

    def test_lr_pairs_equal(self):
        cfg = BlendshapeConfig(seed=42, frame_count=10)
        result = generate_blendshape_weights(cfg)
        pairs, _ = classify_expression_shapes(cfg.expression_shapes)

        for frame_weights in result.values():
            for left, right in pairs:
                assert frame_weights[left] == pytest.approx(frame_weights[right]), \
                    f"Frame mismatch: {left}={frame_weights[left]} != {right}={frame_weights[right]}"

    def test_expression_values_in_range(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=10, expression_max=0.2, expression_overrides={},
        )
        result = generate_blendshape_weights(cfg)

        expr_names = set(cfg.expression_shapes)
        for frame_weights in result.values():
            for name in expr_names:
                if name in frame_weights:
                    assert 0.0 <= frame_weights[name] <= 0.2 + 1e-9, \
                        f"{name}={frame_weights[name]} out of range"


class TestResolveShapeMax:
    def test_global_fallback(self):
        assert _resolve_shape_max("JAW_DROP", 0.2, {}) == pytest.approx(0.2)

    def test_override_wins(self):
        assert _resolve_shape_max("JAW_DROP", 0.2, {"JAW_DROP": 0.05}) == pytest.approx(0.05)

    def test_unrelated_override_ignored(self):
        assert _resolve_shape_max("JAW_DROP", 0.2, {"MOUTH_LEFT": 0.05}) == pytest.approx(0.2)


class TestExpressionOverrides:
    def test_overridden_shape_stays_within_override(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=100,
            expression_max=0.5,
            expression_overrides={"JAW_DROP": 0.1},
        )
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            assert frame_weights.get("JAW_DROP", 0.0) <= 0.1 + 1e-9

    def test_non_overridden_shape_uses_global(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=100,
            expression_max=0.5,
            expression_overrides={"JAW_DROP": 0.1},
        )
        result = generate_blendshape_weights(cfg)
        max_chin = max(
            frame_weights.get("CHIN_RAISER_B", 0.0)
            for frame_weights in result.values()
        )
        assert max_chin > 0.1, "CHIN_RAISER_B should reach above JAW_DROP's tight cap"

    def test_empty_overrides_is_global_only(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=50,
            expression_max=0.3,
            expression_overrides={},
        )
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            for name, val in frame_weights.items():
                if name in _FEW_EXPR_SHAPES:
                    assert val <= 0.3 + 1e-9

    def test_default_overrides_are_applied(self):
        cfg = BlendshapeConfig(seed=42, frame_count=200)
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            assert frame_weights.get("JAW_DROP", 0.0) <= 0.4 + 1e-9
            assert frame_weights.get("JAW_THRUST", 0.0) <= 0.3 + 1e-9

    def test_paired_expression_uses_min_of_pair_overrides(self):
        """Paired L/R shapes should respect the tighter of the two overrides."""
        cfg = BlendshapeConfig(
            seed=42, frame_count=100,
            expression_max=0.5,
            expression_overrides={"BROW_LOWERER_L": 0.05, "BROW_LOWERER_R": 0.2},
        )
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            assert frame_weights.get("BROW_LOWERER_L", 0.0) <= 0.05 + 1e-9
            assert frame_weights.get("BROW_LOWERER_R", 0.0) <= 0.05 + 1e-9


class TestVariationOverrides:
    def test_override_caps_individual_shape(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=100,
            max_variation=1.0,
            variation_overrides={"eyes_female_varGp01A": 0.1},
        )
        result = generate_blendshape_weights(cfg)
        for frame_weights in result.values():
            assert frame_weights.get("eyes_female_varGp01A", 0.0) <= 0.1 + 1e-9

    def test_empty_variation_overrides_no_effect(self):
        cfg_a = BlendshapeConfig(seed=42, frame_count=5, variation_overrides={})
        cfg_b = BlendshapeConfig(seed=42, frame_count=5, variation_overrides={})
        assert generate_blendshape_weights(cfg_a) == generate_blendshape_weights(cfg_b)

    def test_default_variation_overrides_are_independent_copies(self):
        cfg = BlendshapeConfig()
        assert cfg.variation_overrides == DEFAULT_VARIATION_OVERRIDES
        assert cfg.variation_overrides is not DEFAULT_VARIATION_OVERRIDES


class TestVariationZeroing:
    """Unselected variation shapes must be explicitly set to 0.0 each frame."""

    def test_all_variation_shapes_present_every_frame(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=10, max_var_shapes=2, variation_overrides={},
        )
        result = generate_blendshape_weights(cfg)
        var_names = set(cfg.variation_shapes)
        for frame_weights in result.values():
            present = var_names & set(frame_weights.keys())
            assert present == var_names, "Every variation shape should appear in every frame"

    def test_unselected_shapes_are_zero(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=20, max_var_shapes=2, variation_overrides={},
        )
        result = generate_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)

        for frame_weights in result.values():
            for _feature, members in groups.items():
                active = [n for n in members if frame_weights[n] > 0.0]
                zeroed = [n for n in members if frame_weights[n] == 0.0]
                assert 1 <= len(active) <= 2
                assert len(active) + len(zeroed) == len(members)

    def test_normalization_only_counts_active_shapes(self):
        """Active shapes within a group should still sum to max_variation."""
        cfg = BlendshapeConfig(
            seed=42, frame_count=10, max_var_shapes=3,
            max_variation=0.8, variation_overrides={},
        )
        result = generate_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)

        for frame_weights in result.values():
            for feature, members in groups.items():
                active_sum = sum(frame_weights[n] for n in members if frame_weights[n] > 0.0)
                assert active_sum == pytest.approx(0.8), \
                    f"{feature} active sum {active_sum} != 0.8"

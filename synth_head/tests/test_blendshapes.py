"""Tests for synth_head.core.blendshapes."""

import pytest

from synth_head.core.blendshapes import (
    VARIATION_SHAPES,
    EXPRESSION_SHAPES,
    BlendshapeConfig,
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
        assert cfg.max_var_shapes == 3
        assert cfg.max_variation == pytest.approx(1.0)
        assert cfg.expression_max == pytest.approx(0.2)
        assert cfg.seed is None

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
        """Extract weights per feature group from a flat weight dict."""
        result = {}
        for feature, members in groups.items():
            group_w = {n: weights[n] for n in members if n in weights}
            if group_w:
                result[feature] = group_w
        return result

    def test_weights_sum_to_max_variation(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=1,
            max_variation=1.0, max_var_shapes=3,
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
            max_variation=0.6, max_var_shapes=3,
        )
        weights = generate_single_frame_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)
        group_weights = self._get_group_weights(weights, groups)

        for feature, gw in group_weights.items():
            assert sum(gw.values()) == pytest.approx(0.6), \
                f"{feature} weights don't sum to 0.6"

    def test_shape_count_within_bounds(self):
        cfg = BlendshapeConfig(
            seed=42, frame_count=10, max_var_shapes=2,
        )
        result = generate_blendshape_weights(cfg)
        groups = classify_variation_shapes(cfg.variation_shapes)

        for frame_weights in result.values():
            for feature, members in groups.items():
                active = [n for n in members if n in frame_weights]
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
        cfg = BlendshapeConfig(seed=42, frame_count=10, expression_max=0.2)
        result = generate_blendshape_weights(cfg)

        expr_names = set(cfg.expression_shapes)
        for frame_weights in result.values():
            for name in expr_names:
                if name in frame_weights:
                    assert 0.0 <= frame_weights[name] <= 0.2 + 1e-9, \
                        f"{name}={frame_weights[name]} out of range"

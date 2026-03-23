"""Tests for synth_head.core.variation."""

import pytest

from synth_head.core.variation import (
    CHAOS_JOINT_NAMES,
    ChaosTransform,
    VariationConfig,
    classify_joints,
    generate_chaos_transforms,
)

# Center-only joints for tests that don't need pairs
_CENTER_JOINTS = ["JawBind", "NoseBind", "FaceBind"]

# Mixed set with pairs + center joints
_MIXED_JOINTS = [
    "LeftBrowBind", "RightBrowBind",
    "LeftEyeSocketBind", "RightEyeSocketBind",
    "NoseBind", "JawBind",
]


class TestChaosJointNames:
    def test_is_frozenset(self):
        assert isinstance(CHAOS_JOINT_NAMES, frozenset)

    def test_expected_members(self):
        for name in _CENTER_JOINTS:
            assert name in CHAOS_JOINT_NAMES

    def test_count(self):
        assert len(CHAOS_JOINT_NAMES) == 9


class TestVariationConfig:
    def test_defaults(self):
        cfg = VariationConfig()
        assert cfg.frame_count == 400
        assert cfg.transform_max == pytest.approx(0.2)
        assert cfg.rotate_max == pytest.approx(10.0)
        assert cfg.scale_max == pytest.approx(0.2)
        assert cfg.seed is None
        assert cfg.enable_scale is True

    def test_custom_values(self):
        cfg = VariationConfig(frame_count=10, seed=42, enable_scale=True)
        assert cfg.frame_count == 10
        assert cfg.seed == 42
        assert cfg.enable_scale is True


class TestClassifyJoints:
    def test_pairs_detected(self):
        pairs, _ = classify_joints(_MIXED_JOINTS)
        assert ("LeftBrowBind", "RightBrowBind") in pairs
        assert ("LeftEyeSocketBind", "RightEyeSocketBind") in pairs

    def test_center_detected(self):
        _, center = classify_joints(_MIXED_JOINTS)
        assert "NoseBind" in center
        assert "JawBind" in center

    def test_paired_names_not_in_center(self):
        _, center = classify_joints(_MIXED_JOINTS)
        for name in ("LeftBrowBind", "RightBrowBind",
                     "LeftEyeSocketBind", "RightEyeSocketBind"):
            assert name not in center

    def test_unmatched_left_goes_to_center(self):
        joints = ["LeftOrphanBind", "NoseBind"]
        _, center = classify_joints(joints)
        assert "LeftOrphanBind" in center

    def test_empty_list(self):
        pairs, center = classify_joints([])
        assert pairs == []
        assert center == []


class TestGenerateChaosTransforms:
    def test_frame_count(self):
        cfg = VariationConfig(frame_count=5)
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        assert set(result.keys()) == {1, 2, 3, 4, 5}

    def test_joint_keys_per_frame(self):
        cfg = VariationConfig(frame_count=3)
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for frame_data in result.values():
            assert set(frame_data.keys()) == set(_CENTER_JOINTS)

    def test_returns_chaos_transform_instances(self):
        cfg = VariationConfig(frame_count=1)
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for xform in result[1].values():
            assert isinstance(xform, ChaosTransform)

    def test_seed_determinism(self):
        cfg_a = VariationConfig(frame_count=5, seed=99)
        cfg_b = VariationConfig(frame_count=5, seed=99)
        a = generate_chaos_transforms(cfg_a, _MIXED_JOINTS)
        b = generate_chaos_transforms(cfg_b, _MIXED_JOINTS)
        assert a == b

    def test_different_seeds_differ(self):
        cfg_a = VariationConfig(frame_count=5, seed=1)
        cfg_b = VariationConfig(frame_count=5, seed=2)
        a = generate_chaos_transforms(cfg_a, _MIXED_JOINTS)
        b = generate_chaos_transforms(cfg_b, _MIXED_JOINTS)
        assert a != b

    def test_empty_joint_list(self):
        cfg = VariationConfig(frame_count=3)
        result = generate_chaos_transforms(cfg, [])
        for frame_data in result.values():
            assert frame_data == {}

    def test_zero_frames(self):
        cfg = VariationConfig(frame_count=0)
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        assert result == {}


class TestSymmetry:
    def test_paired_location_x_mirrored(self):
        cfg = VariationConfig(frame_count=10, seed=42)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            left = frame_data["LeftBrowBind"]
            right = frame_data["RightBrowBind"]
            assert left.location[0] == pytest.approx(-right.location[0])
            assert left.location[1] == pytest.approx(right.location[1])
            assert left.location[2] == pytest.approx(right.location[2])

    def test_paired_rotation_mirrored(self):
        cfg = VariationConfig(frame_count=10, seed=42)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            left = frame_data["LeftEyeSocketBind"]
            right = frame_data["RightEyeSocketBind"]
            assert left.rotation[0] == pytest.approx(right.rotation[0])    # X same
            assert left.rotation[1] == pytest.approx(-right.rotation[1])   # Y negated
            assert left.rotation[2] == pytest.approx(-right.rotation[2])   # Z negated

    def test_paired_scale_identical(self):
        cfg = VariationConfig(frame_count=5, seed=7, enable_scale=True)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            assert frame_data["LeftBrowBind"].scale == frame_data["RightBrowBind"].scale

    def test_center_no_x_location(self):
        cfg = VariationConfig(frame_count=10, seed=42)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            assert frame_data["NoseBind"].location[0] == 0.0
            assert frame_data["JawBind"].location[0] == 0.0

    def test_center_only_x_rotation(self):
        cfg = VariationConfig(frame_count=10, seed=42)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            for name in ("NoseBind", "JawBind"):
                assert frame_data[name].rotation[1] == 0.0
                assert frame_data[name].rotation[2] == 0.0

    def test_scale_disabled(self):
        cfg = VariationConfig(frame_count=5, seed=42, enable_scale=False)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            for xform in frame_data.values():
                assert xform.scale == (1.0, 1.0, 1.0)

    def test_scale_enabled(self):
        cfg = VariationConfig(frame_count=5, seed=42, enable_scale=True)
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        any_non_identity = any(
            xform.scale != (1.0, 1.0, 1.0)
            for frame_data in result.values()
            for xform in frame_data.values()
        )
        assert any_non_identity

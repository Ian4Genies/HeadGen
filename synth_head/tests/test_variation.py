"""Tests for synth_head.core.variation."""

import pytest

from synth_head.core.variation import (
    CHAOS_JOINT_NAMES,
    ChaosTransform,
    VariationConfig,
    generate_chaos_transforms,
)

_JOINTS = ["JawBind", "NoseBind", "FaceBind"]


class TestChaosJointNames:
    def test_is_frozenset(self):
        assert isinstance(CHAOS_JOINT_NAMES, frozenset)

    def test_expected_members(self):
        for name in _JOINTS:
            assert name in CHAOS_JOINT_NAMES

    def test_count(self):
        assert len(CHAOS_JOINT_NAMES) == 13


class TestVariationConfig:
    def test_defaults(self):
        cfg = VariationConfig()
        assert cfg.frame_count == 400
        assert cfg.transform_max == pytest.approx(0.2)
        assert cfg.rotate_max == pytest.approx(10.0)
        assert cfg.scale_max == pytest.approx(0.2)
        assert cfg.seed is None

    def test_custom_values(self):
        cfg = VariationConfig(frame_count=10, seed=42)
        assert cfg.frame_count == 10
        assert cfg.seed == 42


class TestGenerateChaosTransforms:
    def test_frame_count(self):
        cfg = VariationConfig(frame_count=5)
        result = generate_chaos_transforms(cfg, _JOINTS)
        assert set(result.keys()) == {1, 2, 3, 4, 5}

    def test_joint_keys_per_frame(self):
        cfg = VariationConfig(frame_count=3)
        result = generate_chaos_transforms(cfg, _JOINTS)
        for frame_data in result.values():
            assert set(frame_data.keys()) == set(_JOINTS)

    def test_returns_chaos_transform_instances(self):
        cfg = VariationConfig(frame_count=1)
        result = generate_chaos_transforms(cfg, _JOINTS)
        for xform in result[1].values():
            assert isinstance(xform, ChaosTransform)

    def test_location_range(self):
        cfg = VariationConfig(frame_count=20, transform_max=0.2, seed=0)
        result = generate_chaos_transforms(cfg, _JOINTS)
        for frame_data in result.values():
            for xform in frame_data.values():
                for v in xform.location:
                    assert -0.2 <= v <= 0.2

    def test_rotation_range(self):
        cfg = VariationConfig(frame_count=20, rotate_max=10.0, seed=0)
        result = generate_chaos_transforms(cfg, _JOINTS)
        for frame_data in result.values():
            for xform in frame_data.values():
                for v in xform.rotation:
                    assert -10.0 <= v <= 10.0

    def test_scale_range(self):
        cfg = VariationConfig(frame_count=20, scale_max=0.2, seed=0)
        result = generate_chaos_transforms(cfg, _JOINTS)
        for frame_data in result.values():
            for xform in frame_data.values():
                for v in xform.scale:
                    assert 0.8 <= v <= 1.2

    def test_seed_determinism(self):
        cfg_a = VariationConfig(frame_count=5, seed=99)
        cfg_b = VariationConfig(frame_count=5, seed=99)
        a = generate_chaos_transforms(cfg_a, _JOINTS)
        b = generate_chaos_transforms(cfg_b, _JOINTS)
        assert a == b

    def test_different_seeds_differ(self):
        cfg_a = VariationConfig(frame_count=5, seed=1)
        cfg_b = VariationConfig(frame_count=5, seed=2)
        a = generate_chaos_transforms(cfg_a, _JOINTS)
        b = generate_chaos_transforms(cfg_b, _JOINTS)
        assert a != b

    def test_empty_joint_list(self):
        cfg = VariationConfig(frame_count=3)
        result = generate_chaos_transforms(cfg, [])
        for frame_data in result.values():
            assert frame_data == {}

    def test_zero_frames(self):
        cfg = VariationConfig(frame_count=0)
        result = generate_chaos_transforms(cfg, _JOINTS)
        assert result == {}

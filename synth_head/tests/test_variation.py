"""Tests for synth_head.core.variation."""

import pytest

from synth_head.core.variation import (
    CHAOS_JOINT_NAMES,
    DEFAULT_JOINT_OVERRIDES,
    ChaosTransform,
    VariationConfig,
    _resolve_range,
    classify_joints,
    generate_chaos_transforms,
    generate_single_frame_transforms,
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


class TestGenerateSingleFrameTransforms:
    def test_returns_flat_dict(self):
        cfg = VariationConfig(seed=42)
        result = generate_single_frame_transforms(cfg, _MIXED_JOINTS)
        assert isinstance(result, dict)
        assert set(result.keys()) == set(_MIXED_JOINTS)

    def test_returns_chaos_transform_instances(self):
        cfg = VariationConfig(seed=42)
        result = generate_single_frame_transforms(cfg, _MIXED_JOINTS)
        for xform in result.values():
            assert isinstance(xform, ChaosTransform)

    def test_seed_determinism(self):
        cfg_a = VariationConfig(seed=77)
        cfg_b = VariationConfig(seed=77)
        assert generate_single_frame_transforms(cfg_a, _MIXED_JOINTS) == \
               generate_single_frame_transforms(cfg_b, _MIXED_JOINTS)

    def test_matches_first_frame_of_multi(self):
        """Single-frame output with a given seed must equal frame 1 of the multi-frame version."""
        cfg = VariationConfig(frame_count=5, seed=42)
        multi = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        single = generate_single_frame_transforms(cfg, _MIXED_JOINTS)
        assert single == multi[1]

    def test_empty_joint_list(self):
        cfg = VariationConfig(seed=42)
        result = generate_single_frame_transforms(cfg, [])
        assert result == {}

    def test_symmetry_preserved(self):
        cfg = VariationConfig(seed=42)
        result = generate_single_frame_transforms(cfg, _MIXED_JOINTS)
        left = result["LeftBrowBind"]
        right = result["RightBrowBind"]
        assert left.location[0] == pytest.approx(-right.location[0])
        assert left.location[1] == pytest.approx(right.location[1])
        assert left.rotation[0] == pytest.approx(right.rotation[0])
        assert left.rotation[1] == pytest.approx(-right.rotation[1])


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


class TestResolveRange:
    def test_global_fallback(self):
        assert _resolve_range("FaceBind", "location", 0.2, {}) == pytest.approx(0.2)

    def test_override_wins(self):
        ov = {"FaceBind.location": 0.05}
        assert _resolve_range("FaceBind", "location", 0.2, ov) == pytest.approx(0.05)

    def test_unrelated_override_ignored(self):
        ov = {"NoseBind.location": 0.05}
        assert _resolve_range("FaceBind", "location", 0.2, ov) == pytest.approx(0.2)

    def test_channel_specificity(self):
        ov = {"FaceBind.location": 0.05, "FaceBind.rotation": 2.0}
        assert _resolve_range("FaceBind", "location", 0.2, ov) == pytest.approx(0.05)
        assert _resolve_range("FaceBind", "rotation", 10.0, ov) == pytest.approx(2.0)
        assert _resolve_range("FaceBind", "scale", 0.2, ov) == pytest.approx(0.2)

    def test_axis_override_wins_over_channel(self):
        ov = {"FaceBind.location": 0.1, "FaceBind.location.x": 0.01}
        assert _resolve_range("FaceBind", "location", 0.2, ov, "x") == pytest.approx(0.01)
        assert _resolve_range("FaceBind", "location", 0.2, ov, "y") == pytest.approx(0.1)

    def test_axis_override_wins_over_global(self):
        ov = {"FaceBind.location.z": 0.03}
        assert _resolve_range("FaceBind", "location", 0.2, ov, "z") == pytest.approx(0.03)
        assert _resolve_range("FaceBind", "location", 0.2, ov, "x") == pytest.approx(0.2)

    def test_axis_none_ignores_axis_keys(self):
        ov = {"FaceBind.location": 0.1, "FaceBind.location.x": 0.01}
        assert _resolve_range("FaceBind", "location", 0.2, ov) == pytest.approx(0.1)


class TestJointOverrides:
    """Verify that per-joint overrides tighten generation ranges."""

    def test_center_location_override(self):
        """FaceBind.location=0.01 should keep location values within +-0.01."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            transform_max=0.2,
            joint_overrides={"FaceBind.location": 0.01},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for frame_data in result.values():
            loc = frame_data["FaceBind"].location
            for v in loc:
                assert -0.01 <= v <= 0.01

    def test_center_rotation_override(self):
        """FaceBind.rotation=1.0 should keep rotation within +-1 degree."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            rotate_max=10.0,
            joint_overrides={"FaceBind.rotation": 1.0},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for frame_data in result.values():
            rot = frame_data["FaceBind"].rotation
            assert -1.0 <= rot[0] <= 1.0
            assert rot[1] == 0.0
            assert rot[2] == 0.0

    def test_non_overridden_joints_use_global(self):
        """NoseBind should still sample from the full global range."""
        cfg = VariationConfig(
            frame_count=200,
            seed=7,
            transform_max=0.2,
            joint_overrides={"FaceBind.location": 0.01},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        nose_maxes = [
            max(abs(frame_data["NoseBind"].location[1]),
                abs(frame_data["NoseBind"].location[2]))
            for frame_data in result.values()
        ]
        assert max(nose_maxes) > 0.05, "NoseBind should reach well beyond FaceBind's tiny override"

    def test_paired_override_uses_left_name(self):
        """Override keyed to the Left joint should restrict both sides of a pair."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            transform_max=0.2,
            joint_overrides={"LeftBrowBind.location": 0.01},
        )
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            left = frame_data["LeftBrowBind"]
            right = frame_data["RightBrowBind"]
            for v in left.location:
                assert -0.01 <= v <= 0.01
            for v in right.location:
                assert -0.01 <= v <= 0.01

    def test_scale_override(self):
        """Per-joint scale override should restrict scale deviation."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            scale_max=0.2,
            enable_scale=True,
            joint_overrides={"FaceBind.scale": 0.01},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for frame_data in result.values():
            sc = frame_data["FaceBind"].scale
            for v in sc:
                assert 0.99 <= v <= 1.01

    def test_per_axis_location_override(self):
        """FaceBind.location.y=0.01 should restrict Y but leave Z at global range."""
        cfg = VariationConfig(
            frame_count=100,
            seed=42,
            transform_max=0.2,
            joint_overrides={"FaceBind.location.y": 0.01},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        max_y = 0.0
        max_z = 0.0
        for frame_data in result.values():
            loc = frame_data["FaceBind"].location
            assert -0.01 <= loc[1] <= 0.01
            max_y = max(max_y, abs(loc[1]))
            max_z = max(max_z, abs(loc[2]))
        assert max_z > 0.05, "Z should still use global range"

    def test_per_axis_rotation_override(self):
        """Per-axis rotation override on paired joints."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            rotate_max=10.0,
            joint_overrides={"LeftBrowBind.rotation.x": 1.0},
        )
        result = generate_chaos_transforms(cfg, _MIXED_JOINTS)
        for frame_data in result.values():
            left = frame_data["LeftBrowBind"]
            right = frame_data["RightBrowBind"]
            assert -1.0 <= left.rotation[0] <= 1.0
            assert left.rotation[0] == pytest.approx(right.rotation[0])

    def test_axis_override_stacks_with_channel_override(self):
        """Axis key wins over channel key for its axis; other axes use channel key."""
        cfg = VariationConfig(
            frame_count=50,
            seed=42,
            transform_max=0.2,
            joint_overrides={
                "FaceBind.location": 0.05,
                "FaceBind.location.y": 0.005,
            },
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        for frame_data in result.values():
            loc = frame_data["FaceBind"].location
            assert loc[0] == 0.0  # center joint, always zero
            assert -0.005 <= loc[1] <= 0.005
            assert -0.05 <= loc[2] <= 0.05

    def test_per_axis_scale_override(self):
        """FaceBind.scale.x=0.01 should restrict X scale but allow Y/Z at global."""
        cfg = VariationConfig(
            frame_count=100,
            seed=42,
            scale_max=0.2,
            enable_scale=True,
            joint_overrides={"FaceBind.scale.x": 0.005},
        )
        result = generate_chaos_transforms(cfg, _CENTER_JOINTS)
        max_y_dev = 0.0
        for frame_data in result.values():
            sc = frame_data["FaceBind"].scale
            assert 0.995 <= sc[0] <= 1.005
            max_y_dev = max(max_y_dev, abs(sc[1] - 1.0))
        assert max_y_dev > 0.03, "Y scale should still use global range"

    def test_explicit_empty_overrides_deterministic(self):
        """Two configs with identical explicit empty overrides produce same output."""
        cfg_a = VariationConfig(frame_count=5, seed=42, joint_overrides={})
        cfg_b = VariationConfig(frame_count=5, seed=42, joint_overrides={})
        assert generate_chaos_transforms(cfg_a, _MIXED_JOINTS) == \
               generate_chaos_transforms(cfg_b, _MIXED_JOINTS)

    def test_config_defaults_to_default_overrides(self):
        cfg = VariationConfig()
        assert cfg.joint_overrides == DEFAULT_JOINT_OVERRIDES

    def test_default_overrides_are_independent_copies(self):
        cfg_a = VariationConfig()
        cfg_b = VariationConfig()
        assert cfg_a.joint_overrides is not cfg_b.joint_overrides

    def test_default_overrides_cover_all_chaos_joints(self):
        """Every joint in CHAOS_JOINT_NAMES should have at least one override."""
        overridden_joints = {
            key.split(".")[0] for key in DEFAULT_JOINT_OVERRIDES
        }
        for name in CHAOS_JOINT_NAMES:
            left_form = name
            if name.startswith("Right"):
                left_form = "Left" + name.removeprefix("Right")
            assert left_form in overridden_joints, (
                f"{name} (checked as {left_form}) has no entry in DEFAULT_JOINT_OVERRIDES"
            )

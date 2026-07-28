"""Tests for core eye-socket depth fit math."""

from synth_head.core.eye_fit import (
    EyeFitConfig,
    compute_depth_correction,
    get_transform_location_axis,
    percentile_mean,
    set_transform_location_axis,
)
from synth_head.core.variation import ChaosTransform


class TestComputeDepthCorrection:
    def test_eye_proud_of_rim_pulls_inward(self):
        # gap=0.01 means eye is 0.01 past rim; want -0.002 inset → error 0.012
        delta = compute_depth_correction(
            0.01, target_inset=0.002, max_correction=0.05, gain=1.0,
        )
        assert delta == -0.012

    def test_gain_scales_correction(self):
        delta = compute_depth_correction(
            0.01, target_inset=0.002, max_correction=0.05, gain=0.5,
        )
        assert delta == -0.006

    def test_max_correction_clamps(self):
        delta = compute_depth_correction(
            1.0, target_inset=0.0, max_correction=0.05, gain=1.0,
        )
        assert delta == -0.05

    def test_already_recessed_pushes_outward(self):
        # gap=-0.01, target_inset=0.002 → error=-0.008 → delta=+0.008
        delta = compute_depth_correction(
            -0.01, target_inset=0.002, max_correction=0.05, gain=1.0,
        )
        assert delta == 0.008


class TestPercentileMean:
    def test_empty(self):
        assert percentile_mean([], 0.9) is None

    def test_top_tail(self):
        vals = [0.0, 1.0, 2.0, 3.0, 4.0]
        assert percentile_mean(vals, 1.0) == 4.0
        assert percentile_mean(vals, 0.0) == sum(vals) / len(vals)


class TestTransformAxisHelpers:
    def test_set_and_get(self):
        xform = ChaosTransform(
            location=(0.1, 0.2, 0.3),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        updated = set_transform_location_axis(xform, "y", -0.05)
        assert get_transform_location_axis(updated, "y") == -0.05
        assert get_transform_location_axis(updated, "x") == 0.1
        assert xform.location[1] == 0.2


class TestEyeFitConfig:
    def test_from_dict_and_depth_params(self):
        cfg = EyeFitConfig.from_dict({
            "enabled": True,
            "depth_axis": "Y",
            "target_inset": 0.003,
        })
        assert cfg.depth_axis == "y"
        assert cfg.depth_param_left == "LeftEyeSocketBind.location.y"
        assert cfg.is_depth_param("LeftEyeSocketBind.location.y")
        assert not cfg.is_depth_param("JawBind.location.y")

    def test_invalid_axis_falls_back(self):
        cfg = EyeFitConfig.from_dict({"depth_axis": "w"})
        assert cfg.depth_axis == "y"

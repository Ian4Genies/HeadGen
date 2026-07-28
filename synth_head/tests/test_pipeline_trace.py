"""Tests for synth_head.core.pipeline_trace."""

from __future__ import annotations

from pathlib import Path

import pytest

from synth_head.core.config import PipelineConfig, load_config
from synth_head.core.pipeline_trace import (
    build_trace_catalog,
    collect_param_stages,
    rule_references_param,
    rule_writes_param,
    simulate_pipeline,
)

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "data" / "config"


@pytest.fixture
def cfg() -> PipelineConfig:
    return load_config(_CONFIG_DIR)


class TestRuleReferences:
    def test_target(self):
        rule = {"type": "scale_follow", "source": "A", "target": "B"}
        assert rule_references_param(rule, "B")
        assert rule_writes_param(rule, "B")
        assert rule_references_param(rule, "A")
        assert not rule_writes_param(rule, "A")

    def test_condition(self):
        rule = {"type": "conditional_clamp", "target": "T", "condition": {"param": "C"}}
        assert rule_references_param(rule, "C")
        assert not rule_writes_param(rule, "C")


class TestCatalog:
    def test_builds_groups(self, cfg: PipelineConfig):
        cat = build_trace_catalog(cfg)
        assert "joint" in cat["groups"]
        assert "variation_shapes" in cat["groups"]
        assert "bone_properties" in cat["groups"]
        assert len(cat["all_keys"]) > 0

    def test_joint_in_catalog(self, cfg: PipelineConfig):
        cat = build_trace_catalog(cfg)
        keys = {e["key"] for e in cat["groups"]["joint"]}
        assert "NoseBind.rotation.x" in keys


class TestCollectStages:
    def test_joint_stages(self, cfg: PipelineConfig):
        data = collect_param_stages(cfg, "NoseBind.rotation.x")
        assert data["metadata"]["kind"] == "joint"
        ids = [s["stage_id"] for s in data["stages"]]
        assert ids == ["generation", "attractor", "constraints", "rerandomize"]

    def test_eye_socket_depth_includes_eye_fit_stage(self, cfg: PipelineConfig):
        data = collect_param_stages(cfg, "LeftEyeSocketBind.location.y")
        ids = [s["stage_id"] for s in data["stages"]]
        assert ids == ["generation", "attractor", "constraints", "eye_fit", "rerandomize"]

    def test_variation_shape_has_lottery_note(self, cfg: PipelineConfig):
        shape = cfg.blendshapes.variation_shapes[0]
        data = collect_param_stages(cfg, shape)
        gen = data["stages"][0]
        assert gen["stage_id"] == "generation"
        assert any("lottery" in n.lower() for n in gen["notes"])

    def test_unknown_key_raises(self, cfg: PipelineConfig):
        with pytest.raises(KeyError):
            collect_param_stages(cfg, "not_a_param")


class TestSimulate:
    def test_randomize_face_deterministic(self, cfg: PipelineConfig):
        a = simulate_pipeline(cfg, "NoseBind.rotation.x", mode="randomize_face", seed=99)
        b = simulate_pipeline(cfg, "NoseBind.rotation.x", mode="randomize_face", seed=99)
        assert a["final"] == b["final"]
        assert len(a["steps"]) >= 2

    def test_steps_have_values(self, cfg: PipelineConfig):
        result = simulate_pipeline(cfg, "JawBind.scale.x", mode="randomize_face", seed=1)
        for step in result["steps"]:
            assert "value" in step
            assert "stage_id" in step
            assert step["label"]
        assert result["final"] == result["steps"][-1]["value"]

    def test_bone_property(self, cfg: PipelineConfig):
        key = next(iter(cfg.variation.bone_properties))
        result = simulate_pipeline(cfg, key, mode="randomize_face", seed=5)
        assert result["steps"][0]["stage_id"] == "generation"

    def test_rerandomize_mode(self, cfg: PipelineConfig):
        result = simulate_pipeline(cfg, "NoseBind.rotation.x", mode="rerandomize", seed=7)
        ids = [s["stage_id"] for s in result["steps"]]
        assert ids[0] == "read"
        assert "resample" in ids
        assert result.get("full_pipeline") is True

    def test_full_pipeline_flag(self, cfg: PipelineConfig):
        result = simulate_pipeline(cfg, "MouthBind.location.y", mode="randomize_face", seed=1)
        assert result["full_pipeline"] is True
        assert result["param_count"] > 100

    def test_constrain_substeps_on_forced_violation(self, cfg: PipelineConfig):
        from synth_head.core.pipeline_trace import _constrain_with_substeps, _generate_flat

        flat = _generate_flat(cfg, 0)
        flat["MouthBind.location.y"] = 999.0
        result, substeps = _constrain_with_substeps(flat, cfg, "MouthBind.location.y")
        assert result["MouthBind.location.y"] != 999.0
        assert any(s["type"] == "sandwich_clamp" for s in substeps)
        assert any(abs(s["delta"]) > 1e-9 for s in substeps)

    def test_random_mode_uses_seed(self, cfg: PipelineConfig):
        a = simulate_pipeline(cfg, "NoseBind.rotation.x", mode="randomize_face")
        b = simulate_pipeline(cfg, "NoseBind.rotation.x", mode="randomize_face")
        assert a["seed"] is not None
        assert b["seed"] is not None

    def test_starting_value_overrides_generation(self, cfg: PipelineConfig):
        result = simulate_pipeline(
            cfg, "MouthBind.location.y", mode="randomize_face",
            seed=1, starting_value=0.2,
        )
        gen = result["steps"][0]
        assert gen["value"] == 0.2
        assert result["starting_value"] == 0.2

    def test_starting_value_clamped_to_generation_range(self, cfg: PipelineConfig):
        result = simulate_pipeline(
            cfg, "MouthBind.location.y", mode="randomize_face",
            seed=1, starting_value=999.0,
        )
        vr = result["value_range"]
        assert result["starting_value"] == vr["max"]
        assert result["steps"][0]["value"] == vr["max"]

    def test_metadata_value_range(self, cfg: PipelineConfig):
        data = collect_param_stages(cfg, "MouthBind.location.y")
        vr = data["metadata"]["value_range"]
        assert "min" in vr and "max" in vr

    def test_scale_value_range_is_scene_space(self, cfg: PipelineConfig):
        data = collect_param_stages(cfg, "NoseBind.scale.x")
        vr = data["metadata"]["value_range"]
        assert vr["min"] == pytest.approx(0.8)
        assert vr["max"] == pytest.approx(0.9)

    def test_scale_starting_value_in_scene_space(self, cfg: PipelineConfig):
        result = simulate_pipeline(
            cfg, "NoseBind.scale.x", mode="randomize_face",
            seed=1, starting_value=0.9,
        )
        assert result["steps"][0]["value"] == pytest.approx(0.9)
        assert result["starting_value"] == pytest.approx(0.9)

    def test_constrain_matches_full_pipeline(self, cfg: PipelineConfig):
        from synth_head.core.pipeline_trace import run_full_randomize_face, _constrain_with_substeps

        pipe = run_full_randomize_face(cfg, 42)
        traced, _ = _constrain_with_substeps(dict(pipe["flat_attract"]), cfg, "JawBind.scale.x")
        assert traced["JawBind.scale.x"] == pipe["flat_constrain"]["JawBind.scale.x"]

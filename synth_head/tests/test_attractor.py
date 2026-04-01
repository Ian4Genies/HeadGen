"""Tests for synth_head.core.attractor."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pytest

from synth_head.core.variation import ChaosTransform
from synth_head.core.constraints import flatten_params
from synth_head.core.attractor import (
    AttractorConfig,
    PoolCache,
    attract,
    build_range_vectors,
    compute_attractor_target,
    find_nearest,
    normalize,
    nudge_params,
    snapshot_to_flat,
    update_manifest,
    _build_exclude_set,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JOINT_NAMES = ["JawBind", "NoseBind"]


def _make_snapshot(
    jaw_scale_x: float = 1.0,
    nose_rot_x: float = 0.0,
    bs_val: float = 0.0,
) -> dict:
    """Build a minimal good-head-style snapshot dict."""
    return {
        "chaos_joints": {
            "JawBind": {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                "scale": [jaw_scale_x, 1.0, 1.0],
            },
            "NoseBind": {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        "variation_shapes": {"test_shape_A": bs_val},
        "expression_shapes": {"TEST_EXPR_L": 0.0},
    }


def _save_snapshot(directory: Path, filename: str, snapshot: dict) -> None:
    path = directory / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f)


# ---------------------------------------------------------------------------
# snapshot_to_flat
# ---------------------------------------------------------------------------

class TestSnapshotToFlat:
    def test_basic_conversion(self):
        snap = _make_snapshot(jaw_scale_x=1.1)
        flat = snapshot_to_flat(snap, _JOINT_NAMES)
        assert "JawBind.scale.x" in flat
        assert flat["JawBind.scale.x"] == pytest.approx(1.1)
        assert "test_shape_A" in flat
        assert "TEST_EXPR_L" in flat

    def test_missing_joint_skipped(self):
        snap = _make_snapshot()
        flat = snapshot_to_flat(snap, ["JawBind", "NoseBind", "MissingBone"])
        assert "JawBind.scale.x" in flat
        assert "MissingBone.scale.x" not in flat

    def test_quaternion_identity_gives_zero_rotation(self):
        snap = _make_snapshot()
        flat = snapshot_to_flat(snap, _JOINT_NAMES)
        assert flat["JawBind.rotation.x"] == pytest.approx(0.0, abs=1e-6)
        assert flat["JawBind.rotation.y"] == pytest.approx(0.0, abs=1e-6)
        assert flat["JawBind.rotation.z"] == pytest.approx(0.0, abs=1e-6)

    def test_blendshapes_included(self):
        snap = _make_snapshot(bs_val=0.75)
        flat = snapshot_to_flat(snap, _JOINT_NAMES)
        assert flat["test_shape_A"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# _build_exclude_set
# ---------------------------------------------------------------------------

class TestBuildExcludeSet:
    def test_literal_key(self):
        keys = ["a.b.c", "d.e.f", "g"]
        excluded = _build_exclude_set(["a.b.c"], keys)
        assert "a.b.c" in excluded
        assert "d.e.f" not in excluded

    def test_glob_pattern(self):
        keys = [
            "JawBind.rotation.x",
            "JawBind.scale.x",
            "NoseBind.rotation.x",
        ]
        excluded = _build_exclude_set(["*.rotation.*"], keys)
        assert "JawBind.rotation.x" in excluded
        assert "NoseBind.rotation.x" in excluded
        assert "JawBind.scale.x" not in excluded

    def test_empty_patterns(self):
        excluded = _build_exclude_set([], ["a", "b", "c"])
        assert len(excluded) == 0


# ---------------------------------------------------------------------------
# PoolCache
# ---------------------------------------------------------------------------

class TestPoolCache:
    def test_sync_loads_files(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot(jaw_scale_x=0.9))
        _save_snapshot(tmp_path, "good2.json", _make_snapshot(jaw_scale_x=1.1))

        pool = PoolCache()
        report = pool.sync(tmp_path, _JOINT_NAMES)

        assert report["changed"] is True
        assert report["pool_size"] == 2
        assert set(report["added"]) == {"good1.json", "good2.json"}
        assert pool.pool_size == 2
        assert pool.matrix is not None
        assert pool.matrix.shape[0] == 2

    def test_sync_no_change_returns_false(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())

        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)
        report = pool.sync(tmp_path, _JOINT_NAMES)

        assert report["changed"] is False
        assert report["added"] == []
        assert report["removed"] == []

    def test_sync_incremental_add(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())
        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)
        assert pool.pool_size == 1

        _save_snapshot(tmp_path, "good2.json", _make_snapshot(jaw_scale_x=1.2))
        report = pool.sync(tmp_path, _JOINT_NAMES)
        assert report["changed"] is True
        assert report["added"] == ["good2.json"]
        assert pool.pool_size == 2

    def test_sync_incremental_remove(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())
        _save_snapshot(tmp_path, "good2.json", _make_snapshot())
        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)
        assert pool.pool_size == 2

        (tmp_path / "good1.json").unlink()
        report = pool.sync(tmp_path, _JOINT_NAMES)
        assert report["changed"] is True
        assert report["removed"] == ["good1.json"]
        assert pool.pool_size == 1

    def test_sync_ignores_underscore_files(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())
        _save_snapshot(tmp_path, "_manifest.json", {"files": [], "count": 0})

        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)
        assert pool.pool_size == 1

    def test_sync_nonexistent_dir(self):
        pool = PoolCache()
        report = pool.sync(Path("/nonexistent/dir"), _JOINT_NAMES)
        assert report["changed"] is False
        assert report["pool_size"] == 0

    def test_empty_directory(self, tmp_path):
        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)
        assert pool.pool_size == 0
        assert pool.matrix is None


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_simple_normalization(self):
        values = np.array([5.0, 0.5])
        mins = np.array([0.0, 0.0])
        maxs = np.array([10.0, 1.0])
        result = normalize(values, mins, maxs)
        np.testing.assert_allclose(result, [0.5, 0.5])

    def test_zero_range_safe(self):
        values = np.array([3.0, 0.0])
        mins = np.array([3.0, 0.0])
        maxs = np.array([3.0, 0.0])
        result = normalize(values, mins, maxs)
        assert np.all(np.isfinite(result))


# ---------------------------------------------------------------------------
# find_nearest
# ---------------------------------------------------------------------------

class TestFindNearest:
    def test_finds_closest(self):
        pool = np.array([
            [0.0, 0.0],
            [10.0, 10.0],
            [1.0, 1.0],
        ])
        current = np.array([0.5, 0.5])
        mins = np.array([0.0, 0.0])
        maxs = np.array([10.0, 10.0])

        indices = find_nearest(current, pool, 2, mins, maxs)
        assert len(indices) == 2
        assert 0 in indices
        assert 2 in indices

    def test_n_clamped_to_pool_size(self):
        pool = np.array([[1.0, 1.0], [2.0, 2.0]])
        current = np.array([1.5, 1.5])
        mins = np.array([0.0, 0.0])
        maxs = np.array([10.0, 10.0])

        indices = find_nearest(current, pool, 100, mins, maxs)
        assert len(indices) == 2


# ---------------------------------------------------------------------------
# compute_attractor_target
# ---------------------------------------------------------------------------

class TestComputeAttractorTarget:
    def test_weighted_average(self):
        pool = np.array([
            [0.0, 0.0],
            [10.0, 10.0],
        ])
        indices = np.array([0, 1])
        rng = random.Random(42)
        target = compute_attractor_target(pool, indices, rng)
        assert target.shape == (2,)
        assert 0.0 <= target[0] <= 10.0

    def test_single_head(self):
        pool = np.array([[5.0, 3.0]])
        indices = np.array([0])
        rng = random.Random(0)
        target = compute_attractor_target(pool, indices, rng)
        np.testing.assert_allclose(target, [5.0, 3.0])


# ---------------------------------------------------------------------------
# nudge_params
# ---------------------------------------------------------------------------

class TestNudgeParams:
    def test_moves_toward_target(self):
        current = {"a": 0.0, "b": 10.0}
        target = np.array([10.0, 0.0])
        keys = ["a", "b"]
        result = nudge_params(current, target, keys, 0.5, frozenset())
        assert result["a"] == pytest.approx(5.0)
        assert result["b"] == pytest.approx(5.0)

    def test_zero_influence_no_change(self):
        current = {"a": 3.0}
        target = np.array([10.0])
        result = nudge_params(current, target, ["a"], 0.0, frozenset())
        assert result["a"] == pytest.approx(3.0)

    def test_full_influence_reaches_target(self):
        current = {"a": 0.0}
        target = np.array([7.0])
        result = nudge_params(current, target, ["a"], 1.0, frozenset())
        assert result["a"] == pytest.approx(7.0)

    def test_excluded_params_untouched(self):
        current = {"a": 0.0, "b": 0.0}
        target = np.array([10.0, 10.0])
        result = nudge_params(current, target, ["a", "b"], 0.5, frozenset({"a"}))
        assert result["a"] == pytest.approx(0.0)
        assert result["b"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# attract (integration)
# ---------------------------------------------------------------------------

class TestAttract:
    def test_disabled_is_noop(self):
        flat = {"JawBind.scale.x": 1.0}
        cfg = AttractorConfig(enabled=False)
        pool = PoolCache()
        result, dbg = attract(flat, pool, cfg, None, None, random.Random(0))
        assert result == flat
        assert dbg is None

    def test_empty_pool_is_noop(self):
        flat = {"JawBind.scale.x": 1.0}
        cfg = AttractorConfig(enabled=True)
        pool = PoolCache()
        result, dbg = attract(flat, pool, cfg, None, None, random.Random(0))
        assert result == flat
        assert dbg is None

    def test_nudges_toward_pool(self, tmp_path):
        from synth_head.core.variation import VariationConfig
        from synth_head.core.blendshapes import BlendshapeConfig

        _save_snapshot(tmp_path, "good1.json", _make_snapshot(jaw_scale_x=1.2))
        _save_snapshot(tmp_path, "good2.json", _make_snapshot(jaw_scale_x=1.3))

        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)

        snap_current = _make_snapshot(jaw_scale_x=0.8)
        flat = snapshot_to_flat(snap_current, _JOINT_NAMES)
        original_jaw = flat["JawBind.scale.x"]

        cfg = AttractorConfig(
            enabled=True,
            min_attractors=2,
            max_attractors=2,
            max_influence=0.5,
        )
        var_cfg = VariationConfig()
        bs_cfg = BlendshapeConfig(
            variation_shapes=["test_shape_A"],
            expression_shapes=["TEST_EXPR_L"],
        )

        result, dbg = attract(flat, pool, cfg, var_cfg, bs_cfg, random.Random(42))

        assert result["JawBind.scale.x"] > original_jaw
        assert dbg is None  # debug=False by default

    def test_debug_info_returned_when_enabled(self, tmp_path):
        from synth_head.core.variation import VariationConfig
        from synth_head.core.blendshapes import BlendshapeConfig

        _save_snapshot(tmp_path, "good1.json", _make_snapshot(jaw_scale_x=1.2))
        _save_snapshot(tmp_path, "good2.json", _make_snapshot(jaw_scale_x=1.3))

        pool = PoolCache()
        pool.sync(tmp_path, _JOINT_NAMES)

        flat = snapshot_to_flat(_make_snapshot(jaw_scale_x=0.8), _JOINT_NAMES)

        cfg = AttractorConfig(
            enabled=True,
            debug=True,
            min_attractors=2,
            max_attractors=2,
            max_influence=0.5,
        )
        var_cfg = VariationConfig()
        bs_cfg = BlendshapeConfig(
            variation_shapes=["test_shape_A"],
            expression_shapes=["TEST_EXPR_L"],
        )

        result, dbg = attract(flat, pool, cfg, var_cfg, bs_cfg, random.Random(42))

        assert dbg is not None
        assert dbg["n_selected"] == 2
        assert len(dbg["selected_files"]) == 2
        assert dbg["mean_abs_delta"] >= 0.0
        assert all(f in {"good1.json", "good2.json"} for f in dbg["selected_files"])


# ---------------------------------------------------------------------------
# update_manifest
# ---------------------------------------------------------------------------

class TestUpdateManifest:
    def test_creates_manifest(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())
        _save_snapshot(tmp_path, "good2.json", _make_snapshot())

        update_manifest(tmp_path)

        manifest_path = tmp_path / "_manifest.json"
        assert manifest_path.exists()

        with manifest_path.open() as f:
            data = json.load(f)
        assert data["count"] == 2
        assert sorted(data["files"]) == ["good1.json", "good2.json"]

    def test_excludes_underscore_files(self, tmp_path):
        _save_snapshot(tmp_path, "good1.json", _make_snapshot())
        _save_snapshot(tmp_path, "_manifest.json", {"files": [], "count": 0})

        update_manifest(tmp_path)

        with (tmp_path / "_manifest.json").open() as f:
            data = json.load(f)
        assert data["count"] == 1
        assert data["files"] == ["good1.json"]


# ---------------------------------------------------------------------------
# AttractorConfig
# ---------------------------------------------------------------------------

class TestAttractorConfig:
    def test_from_dict_defaults(self):
        cfg = AttractorConfig.from_dict({})
        assert cfg.enabled is True
        assert cfg.min_attractors == 2
        assert cfg.max_attractors == 5
        assert cfg.max_influence == pytest.approx(0.2)
        assert cfg.exclude_params == []

    def test_from_dict_custom(self):
        cfg = AttractorConfig.from_dict({
            "enabled": False,
            "min_attractors": 1,
            "max_attractors": 3,
            "max_influence": 0.5,
            "exclude_params": ["*.rotation.*"],
        })
        assert cfg.enabled is False
        assert cfg.min_attractors == 1
        assert cfg.max_influence == pytest.approx(0.5)
        assert "*.rotation.*" in cfg.exclude_params

    def test_resolve_path(self, tmp_path):
        cfg = AttractorConfig(good_heads_dir="head-good")
        resolved = cfg.resolve(tmp_path)
        assert str(tmp_path / "head-good") in resolved.good_heads_dir

"""
Unified configuration loader — pure Python, no bpy.

Reads a config directory (default: data/config/) containing JSON files and
hydrates all pipeline dataclasses from them.  When no external config is
provided the dataclass defaults still work, so nothing breaks if you just
call ``VariationConfig()`` directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .variation import VariationConfig, CHAOS_JOINT_NAMES, DEFAULT_JOINT_OVERRIDES
from .blendshapes import (
    BlendshapeConfig,
    VARIATION_SHAPES,
    EXPRESSION_SHAPES,
    DEFAULT_VARIATION_OVERRIDES,
    DEFAULT_EXPRESSION_OVERRIDES,
)
from .constraints import ConstraintRules, ClampRange
from .modifiers import SmoothCorrectiveConfig
from .attractor import AttractorConfig


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class RunnerConfig:
    frame_count: int = 400
    seed: int | None = None
    fbx_path: str = ""
    save_blend_path: str = ""
    issues_dir: str = ""
    good_dir: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> RunnerConfig:
        paths = d.get("paths", {})
        return cls(
            frame_count=d.get("frame_count", 400),
            seed=d.get("seed"),
            fbx_path=paths.get("fbx", ""),
            save_blend_path=paths.get("save_blend", ""),
            issues_dir=paths.get("issues_dir", ""),
            good_dir=paths.get("good_dir", ""),
        )

    def resolve(self, base: Path) -> RunnerConfig:
        """Return a copy with all relative paths resolved against *base*."""
        return RunnerConfig(
            frame_count=self.frame_count,
            seed=self.seed,
            fbx_path=str((base / self.fbx_path).resolve()) if self.fbx_path else "",
            save_blend_path=str((base / self.save_blend_path).resolve()) if self.save_blend_path else "",
            issues_dir=str((base / self.issues_dir).resolve()) if self.issues_dir else "",
            good_dir=str((base / self.good_dir).resolve()) if self.good_dir else "",
        )


@dataclass
class PipelineConfig:
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    variation: VariationConfig = field(default_factory=VariationConfig)
    blendshapes: BlendshapeConfig = field(default_factory=BlendshapeConfig)
    constraints: ConstraintRules = field(default_factory=ConstraintRules)
    modifiers: SmoothCorrectiveConfig = field(default_factory=SmoothCorrectiveConfig)
    attractor: AttractorConfig = field(default_factory=AttractorConfig)
    chaos_joint_names: frozenset[str] = field(default_factory=lambda: frozenset(CHAOS_JOINT_NAMES))
    config_dir: Path = field(default_factory=lambda: Path("."))


def load_config(config_dir: str | Path) -> PipelineConfig:
    """Load an entire pipeline configuration from a directory of JSON files.

    Expected files (all optional — missing files fall back to dataclass defaults):
        runner.json, chaos_joints.json, blendshapes.json,
        constraints.json, modifiers.json
    """
    d = Path(config_dir)
    project_root = d.parent  # data/config/ → data/

    # --- runner ---
    runner_path = d / "runner.json"
    if runner_path.exists():
        runner = RunnerConfig.from_dict(_load_json(runner_path))
    else:
        runner = RunnerConfig()
    runner = runner.resolve(project_root)

    fc = runner.frame_count
    seed = runner.seed

    # --- chaos joints / variation ---
    chaos_path = d / "chaos_joints.json"
    if chaos_path.exists():
        chaos_data = _load_json(chaos_path)
        joint_names = frozenset(chaos_data.get("joint_names", CHAOS_JOINT_NAMES))
        variation = VariationConfig.from_dict(chaos_data, fc, seed)
    else:
        joint_names = frozenset(CHAOS_JOINT_NAMES)
        variation = VariationConfig(frame_count=fc, seed=seed)

    # --- blendshapes ---
    bs_path = d / "blendshapes.json"
    if bs_path.exists():
        blendshapes = BlendshapeConfig.from_dict(_load_json(bs_path), fc, seed)
    else:
        blendshapes = BlendshapeConfig(frame_count=fc, seed=seed)

    # --- constraints ---
    con_path = d / "constraints.json"
    if con_path.exists():
        constraints = ConstraintRules.from_dict(_load_json(con_path))
    else:
        constraints = ConstraintRules()

    # --- modifiers ---
    mod_path = d / "modifiers.json"
    if mod_path.exists():
        mod_data = _load_json(mod_path)
        modifiers = SmoothCorrectiveConfig.from_dict(
            mod_data.get("smooth_corrective", {}),
        )
    else:
        modifiers = SmoothCorrectiveConfig()

    # --- attractor ---
    attr_path = d / "attractor.json"
    if attr_path.exists():
        attractor = AttractorConfig.from_dict(_load_json(attr_path))
        attractor = attractor.resolve(project_root)
    else:
        attractor = AttractorConfig()

    return PipelineConfig(
        runner=runner,
        variation=variation,
        blendshapes=blendshapes,
        constraints=constraints,
        modifiers=modifiers,
        attractor=attractor,
        chaos_joint_names=joint_names,
        config_dir=d,
    )

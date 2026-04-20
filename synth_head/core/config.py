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
class MaterialsConfig:
    skin_material_blend_path: str = ""
    skin_material_name: str = "head_mat"
    eye_material_name: str = "eye_mat"
    final_color_randomness: float = 0.1

    @classmethod
    def from_dict(cls, d: dict) -> "MaterialsConfig":
        paths = d.get("paths", {})
        return cls(
            skin_material_blend_path=paths.get("skin_material_blend", ""),
            skin_material_name=d.get("skin_material_name", "head_mat"),
            eye_material_name=d.get("eye_material_name", "eye_mat"),
            final_color_randomness=float(d.get("final_color_randomness", 0.1)),
        )

    def resolve(self, base: Path) -> "MaterialsConfig":
        return MaterialsConfig(
            skin_material_blend_path=(
                str((base / self.skin_material_blend_path).resolve())
                if self.skin_material_blend_path else ""
            ),
            skin_material_name=self.skin_material_name,
            eye_material_name=self.eye_material_name,
            final_color_randomness=self.final_color_randomness,
        )

@dataclass
class CleanupConfig:
    assets_blend_path: str = "assets.blend"
    eye_wedge_R_name: str = ""
    eye_wedge_L_name: str = ""
    mouth_bag_group: str = ""
    mouth_sew_indices: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "CleanupConfig":
        paths = d.get("paths", {})
        return cls(
            assets_blend_path=paths.get("assets_blend_path", "assets.blend"),
            eye_wedge_R_name=d.get("eye_wedge_R_name", ""),
            eye_wedge_L_name=d.get("eye_wedge_L_name", ""),
            mouth_bag_group=d.get("mouth_bag_group", ""),
            mouth_sew_indices=d.get("mouth_sew_indices", {}),
        )

    def resolve(self, base: Path) -> "CleanupConfig":
        return CleanupConfig(
            assets_blend_path=str((base / self.assets_blend_path).resolve()) if self.assets_blend_path else "",
            eye_wedge_R_name=self.eye_wedge_R_name,
            eye_wedge_L_name=self.eye_wedge_L_name,
            mouth_bag_group=self.mouth_bag_group,
            mouth_sew_indices=self.mouth_sew_indices,
        )

@dataclass
class RunnerConfig:
    frame_count: int = 400
    seed: int | None = None
    fbx_path: str = ""
    gen13_blend_path: str = ""
    save_variation_blend_path: str = ""
    save_water_tight_blend_path: str = ""
    save_export_blend_path: str = ""
    issues_dir: str = ""
    good_dir: str = ""
    attractive_dir: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> RunnerConfig:
        paths = d.get("paths", {})
        return cls(
            frame_count=d.get("frame_count", 400),
            seed=d.get("seed"),
            fbx_path=paths.get("fbx", ""),
            gen13_blend_path=paths.get("gen13_blend", ""),
            save_variation_blend_path=paths.get("save_variation_blend", ""),
            save_water_tight_blend_path=paths.get("save_water_tight_blend", ""),
            save_export_blend_path=paths.get("save_export_blend", ""),
            issues_dir=paths.get("issues_dir", ""),
            good_dir=paths.get("good_dir", ""),
            attractive_dir=paths.get("attractive_dir", ""),
        )

    def resolve(self, base: Path) -> RunnerConfig:
        """Return a copy with all relative paths resolved against *base*."""
        return RunnerConfig(
            frame_count=self.frame_count,
            seed=self.seed,
            fbx_path=str((base / self.fbx_path).resolve()) if self.fbx_path else "",
            gen13_blend_path=str((base / self.gen13_blend_path).resolve()) if self.gen13_blend_path else "",
            save_variation_blend_path=str((base / self.save_variation_blend_path).resolve()) if self.save_variation_blend_path else "",
            save_water_tight_blend_path=str((base / self.save_water_tight_blend_path).resolve()) if self.save_water_tight_blend_path else "",
            save_export_blend_path=str((base / self.save_export_blend_path).resolve()) if self.save_export_blend_path else "",
            issues_dir=str((base / self.issues_dir).resolve()) if self.issues_dir else "",
            good_dir=str((base / self.good_dir).resolve()) if self.good_dir else "",
            attractive_dir=str((base / self.attractive_dir).resolve()) if self.attractive_dir else "",
        )


@dataclass
class PipelineConfig:
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    variation: VariationConfig = field(default_factory=VariationConfig)
    blendshapes: BlendshapeConfig = field(default_factory=BlendshapeConfig)
    constraints: ConstraintRules = field(default_factory=ConstraintRules)
    modifiers: SmoothCorrectiveConfig = field(default_factory=SmoothCorrectiveConfig)
    attractor: AttractorConfig = field(default_factory=AttractorConfig)
    materials: MaterialsConfig = field(default_factory=MaterialsConfig)
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

    # --- materials ---
    mat_path = d / "materials.json"
    if mat_path.exists():
        materials = MaterialsConfig.from_dict(_load_json(mat_path))
        materials = materials.resolve(project_root)
    else:
        materials = MaterialsConfig()

    # --- cleanup ---
    cleanup_path = d / "cleanup.json"
    if cleanup_path.exists():
        cleanup = CleanupConfig.from_dict(_load_json(cleanup_path))
        cleanup = cleanup.resolve(project_root)
    else:
        cleanup = CleanupConfig()

    return PipelineConfig(
        runner=runner,
        cleanup=cleanup,
        variation=variation,
        blendshapes=blendshapes,
        constraints=constraints,
        modifiers=modifiers,
        attractor=attractor,
        materials=materials,
        chaos_joint_names=joint_names,
        config_dir=d,
    )

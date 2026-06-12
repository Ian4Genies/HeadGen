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
from .texture_swap import TextureSwapConfig, TextureSwapSlot
from .rerandomize import RerandomizeConfig


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class MaterialsConfig:
    skin_material_blend_path: str = ""
    skin_material_name: str = "head_mat"
    eye_material_name: str = "eye_mat"
    final_color_randomness: float = 0.1
    hair_color_node: str = "hair-color"
    hair_color_randomness: float = 0.05
    hair_color_defaults: list = field(default_factory=list)
    lip_color_node: str = "lip-color"
    lip_color_randomness: float = 0.05
    lip_color_override: float = 0.2

    @classmethod
    def from_dict(cls, d: dict) -> "MaterialsConfig":
        paths = d.get("paths", {})
        return cls(
            skin_material_blend_path=paths.get("skin_material_blend", ""),
            skin_material_name=d.get("skin_material_name", "head_mat"),
            eye_material_name=d.get("eye_material_name", "eye_mat"),
            final_color_randomness=float(d.get("final_color_randomness", 0.1)),
            hair_color_node=d.get("hair-color-node", "hair-color"),
            hair_color_randomness=float(d.get("hair_color_randomness", 0.05)),
            hair_color_defaults=list(d.get("hair_color_defaults", [])),
            lip_color_node=d.get("lip-color-node", "lip-color"),
            lip_color_randomness=float(d.get("lip_color_randomness", 0.05)),
            lip_color_override=float(d.get("lip_color_override", 0.2)),
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
            hair_color_node=self.hair_color_node,
            hair_color_randomness=self.hair_color_randomness,
            hair_color_defaults=list(self.hair_color_defaults),
            lip_color_node=self.lip_color_node,
            lip_color_randomness=self.lip_color_randomness,
            lip_color_override=self.lip_color_override,
        )

@dataclass
class CleanupConfig:
    assets_blend_path: str = "assets.blend"
    eye_wedge_R_name: str = ""
    eye_wedge_L_name: str = ""
    mouth_bag_group: str = ""
    mouth_sew_indices: dict[str, int] = field(default_factory=dict)
    join_merge_distance: float = 0.001
    lip_sew_merge_distance: float = 1e-6
    seam_weld_distance: float = 1e-5

    @classmethod
    def from_dict(cls, d: dict) -> "CleanupConfig":
        paths = d.get("paths", {})
        return cls(
            assets_blend_path=paths.get("assets_blend_path", "assets.blend"),
            eye_wedge_R_name=d.get("eye_wedge_R_name", ""),
            eye_wedge_L_name=d.get("eye_wedge_L_name", ""),
            mouth_bag_group=d.get("mouth_bag_group", ""),
            mouth_sew_indices=d.get("mouth_sew_indices", {}),
            join_merge_distance=d.get("join_merge_distance", 0.001),
            lip_sew_merge_distance=d.get("lip_sew_merge_distance", 1e-6),
            seam_weld_distance=d.get("seam_weld_distance", 1e-5),
        )

    def resolve(self, base: Path) -> "CleanupConfig":
        return CleanupConfig(
            assets_blend_path=str((base / self.assets_blend_path).resolve()) if self.assets_blend_path else "",
            eye_wedge_R_name=self.eye_wedge_R_name,
            eye_wedge_L_name=self.eye_wedge_L_name,
            mouth_bag_group=self.mouth_bag_group,
            mouth_sew_indices=self.mouth_sew_indices,
            join_merge_distance=self.join_merge_distance,
            lip_sew_merge_distance=self.lip_sew_merge_distance,
            seam_weld_distance=self.seam_weld_distance,
        )

@dataclass
class BakeSettings:
    """All Blender bake settings that can be applied to a scene.

    Generalised so any named bake-settings struct in JSON (e.g. ``eye-bake-settings``,
    a future ``head-bake-settings``, etc.) can be loaded via ``from_dict`` and applied
    identically by ``scene.projection.apply_bake_settings``.
    """

    render_engine: str = "CYCLES"
    bake_type: str = "DIFFUSE"
    use_pass_direct: bool = False
    use_pass_indirect: bool = False
    use_pass_color: bool = True
    use_selected_to_active: bool = True
    use_cage: bool = False
    cage_extrusion: float = 0.05
    max_ray_distance: float = 0.2
    target: str = "IMAGE_TEXTURES"
    margin_type: str = "EXTEND"
    margin: int = 16
    use_clear: bool = True
    save_mode: str = "INTERNAL"

    @classmethod
    def from_dict(cls, d: dict) -> "BakeSettings":
        return cls(
            render_engine=str(d.get("render_engine", "CYCLES")),
            bake_type=str(d.get("bake_type", "DIFFUSE")),
            use_pass_direct=bool(d.get("use_pass_direct", False)),
            use_pass_indirect=bool(d.get("use_pass_indirect", False)),
            use_pass_color=bool(d.get("use_pass_color", True)),
            use_selected_to_active=bool(d.get("use_selected_to_active", True)),
            use_cage=bool(d.get("use_cage", False)),
            cage_extrusion=float(d.get("cage_extrusion", 0.05)),
            max_ray_distance=float(d.get("max_ray_distance", 0.2)),
            target=str(d.get("target", "IMAGE_TEXTURES")),
            margin_type=str(d.get("margin_type", "EXTEND")),
            margin=int(d.get("margin", 16)),
            use_clear=bool(d.get("use_clear", True)),
            save_mode=str(d.get("save_mode", "INTERNAL")),
        )


@dataclass
class ProjectionConfig:
    assets_blend_path: str = ""
    baked_sequence_R_path: str = ""
    baked_sequence_L_path: str = ""
    eye_wedge_R_bake_name: str = ""
    eye_wedge_L_bake_name: str = ""
    hd_eye_R_name: str = ""
    hd_eye_L_name: str = ""
    R_projector_name: str = ""
    L_projector_name: str = ""
    eye_baked_sequence_name: str = "baked-sequence"
    eye_bake_diffuse_name: str = "bake-diffuse"
    eye_bake_switch_name: str = "bake-switch"
    eye_color_name: str = "eye-color"
    eye_bake_settings: BakeSettings = field(default_factory=BakeSettings)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectionConfig":
        paths = d.get("paths", {})
        return cls(
            assets_blend_path=paths.get("assets_blend_path", ""),
            baked_sequence_R_path=paths.get("baked-sequence-R-path", ""),
            baked_sequence_L_path=paths.get("baked-sequence-L-path", ""),
            eye_wedge_R_bake_name=d.get("eye_wedge_R_bake_name", ""),
            eye_wedge_L_bake_name=d.get("eye_wedge_L_bake_name", ""),
            hd_eye_R_name=d.get("hd_eye_R_name", ""),
            hd_eye_L_name=d.get("hd_eye_L_name", ""),
            R_projector_name=d.get("R_projector_name", ""),
            L_projector_name=d.get("L_projector_name", ""),
            eye_baked_sequence_name=d.get("eye-baked-sequence-name", "baked-sequence"),
            eye_bake_diffuse_name=d.get("eye-bake-diffuse-name", "bake-diffuse"),
            eye_bake_switch_name=d.get("eye-bake-switch-name", "bake-switch"),
            eye_color_name=d.get("eye-color-name", "eye-color"),
            eye_bake_settings=BakeSettings.from_dict(d.get("eye-bake-settings", {})),
        )

    def resolve(self, base: Path) -> "ProjectionConfig":
        return ProjectionConfig(
            assets_blend_path=str((base / self.assets_blend_path).resolve()) if self.assets_blend_path else "",
            baked_sequence_R_path=str((base / self.baked_sequence_R_path).resolve()) if self.baked_sequence_R_path else "",
            baked_sequence_L_path=str((base / self.baked_sequence_L_path).resolve()) if self.baked_sequence_L_path else "",
            eye_wedge_R_bake_name=self.eye_wedge_R_bake_name,
            eye_wedge_L_bake_name=self.eye_wedge_L_bake_name,
            hd_eye_R_name=self.hd_eye_R_name,
            hd_eye_L_name=self.hd_eye_L_name,
            R_projector_name=self.R_projector_name,
            L_projector_name=self.L_projector_name,
            eye_baked_sequence_name=self.eye_baked_sequence_name,
            eye_bake_diffuse_name=self.eye_bake_diffuse_name,
            eye_bake_switch_name=self.eye_bake_switch_name,
            eye_color_name=self.eye_color_name,
            eye_bake_settings=self.eye_bake_settings,
        )


@dataclass
class RunnerConfig:
    frame_count: int = 400
    seed: int | None = None
    fbx_path: str = ""
    gen13_blend_path: str = ""
    save_variation_blend_path: str = ""
    save_eye_bake_blend_path: str = ""
    save_water_tight_blend_path: str = ""
    save_export_blend_path: str = ""
    issues_dir: str = ""
    good_dir: str = ""
    attractive_dir: str = ""
    final_output_dir: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> RunnerConfig:
        paths = d.get("paths", {})
        return cls(
            frame_count=d.get("frame_count", 400),
            seed=d.get("seed"),
            fbx_path=paths.get("fbx", ""),
            gen13_blend_path=paths.get("gen13_blend", ""),
            save_variation_blend_path=paths.get("save_variation_blend", ""),
            save_eye_bake_blend_path=paths.get("save_eye_bake_blend", ""),
            save_water_tight_blend_path=paths.get("save_water_tight_blend", ""),
            save_export_blend_path=paths.get("save_export_blend", ""),
            issues_dir=paths.get("issues_dir", ""),
            good_dir=paths.get("good_dir", ""),
            attractive_dir=paths.get("attractive_dir", ""),
            final_output_dir=paths.get("final_output_dir", ""),
        )

    def resolve(self, base: Path) -> RunnerConfig:
        """Return a copy with all relative paths resolved against *base*."""
        return RunnerConfig(
            frame_count=self.frame_count,
            seed=self.seed,
            fbx_path=str((base / self.fbx_path).resolve()) if self.fbx_path else "",
            gen13_blend_path=str((base / self.gen13_blend_path).resolve()) if self.gen13_blend_path else "",
            save_variation_blend_path=str((base / self.save_variation_blend_path).resolve()) if self.save_variation_blend_path else "",
            save_eye_bake_blend_path=str((base / self.save_eye_bake_blend_path).resolve()) if self.save_eye_bake_blend_path else "",
            save_water_tight_blend_path=str((base / self.save_water_tight_blend_path).resolve()) if self.save_water_tight_blend_path else "",
            save_export_blend_path=str((base / self.save_export_blend_path).resolve()) if self.save_export_blend_path else "",
            issues_dir=str((base / self.issues_dir).resolve()) if self.issues_dir else "",
            good_dir=str((base / self.good_dir).resolve()) if self.good_dir else "",
            attractive_dir=str((base / self.attractive_dir).resolve()) if self.attractive_dir else "",
            final_output_dir=str((base / self.final_output_dir).resolve()) if self.final_output_dir else "",
        )


@dataclass
class ExportConfig:
    """Settings for Pipeline 03 — per-frame static GLB + baked diffuse textures."""

    head_bake_resolution: int = 2048
    eye_wedge_bake_resolution: int = 512
    bake_samples: int = 4
    bake_margin: int = 8
    glb_format: str = "GLB"
    frame_range: tuple[int, int] | None = None

    head_bake_material_name: str = "head_mat"
    eye_wedge_R_material_name: str = "eye_mat.001"
    eye_wedge_L_material_name: str = "eye_mat.002"

    include_eyes: bool = True
    include_brows: bool = False
    include_lashes: bool = False

    bake_wedge_texture_direct: bool = False
    copy_eye_projection: bool = True
    bake_brow_texture_direct: bool = False
    bake_lash_texture_direct: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "ExportConfig":
        raw_range = d.get("frame_range")
        if raw_range is None:
            frame_range = None
        else:
            # Accept [start, end] or (start, end) from JSON.
            start, end = raw_range
            frame_range = (int(start), int(end))

        return cls(
            head_bake_resolution=int(d.get("head_bake_resolution", 2048)),
            eye_wedge_bake_resolution=int(d.get("eye_wedge_bake_resolution", 512)),
            bake_samples=int(d.get("bake_samples", 4)),
            bake_margin=int(d.get("bake_margin", 8)),
            glb_format=str(d.get("glb_format", "GLB")),
            frame_range=frame_range,
            head_bake_material_name=str(d.get("head_bake_material_name", "head_mat")),
            eye_wedge_R_material_name=str(d.get("eye_wedge_R_material_name", "eye_mat.001")),
            eye_wedge_L_material_name=str(d.get("eye_wedge_L_material_name", "eye_mat.002")),
            include_eyes=bool(d.get("include_eyes", True)),
            include_brows=bool(d.get("include_brows", False)),
            include_lashes=bool(d.get("include_lashes", False)),
            bake_wedge_texture_direct=bool(d.get("bake_wedge_texture_direct", True)),
            copy_eye_projection=bool(d.get("copy_eye_projection", False)),
            bake_brow_texture_direct=bool(d.get("bake_brow_texture_direct", False)),
            bake_lash_texture_direct=bool(d.get("bake_lash_texture_direct", False)),
        )


@dataclass
class DriverSpec:
    """One driver relationship: a source property drives a target property.

    Both sides address either a pose bone custom property (when *bone* is set)
    or an object-level custom property (when *bone* is None).

    The special string ``"ARMATURE"`` in *target_object* or *source_object*
    is resolved to the canonical armature at runtime.

    Fields:
        target_object:       Scene object name or ``"ARMATURE"``.
        target_bone:         Pose bone name, or None for an object-level property.
        target_property:     Custom property key on the target, or shape key name
                             when *target_is_shape_key* is True.
        target_is_shape_key: When True the driver is placed on the mesh's shape
                             key ``key_blocks["<target_property>"].value`` rather
                             than on an object custom property.
        source_object:       Scene object name or ``"ARMATURE"``.
        source_bone:         Pose bone name, or None for an object-level property.
        source_property:     Custom property key on the source, or shape key name
                             when *source_is_shape_key* is True.
        source_is_shape_key: When True the driver variable reads from the source
                             mesh's shape key ``key_blocks["<source_property>"].value``
                             rather than from a custom property.
        expression:          FCurve driver expression.  Defaults to ``"var"``
                             (passthrough).  Reserved for future function support.
    """

    target_object: str
    target_bone: str | None
    target_property: str
    source_object: str
    source_bone: str | None
    source_property: str
    expression: str = "var"
    target_is_shape_key: bool = False
    source_is_shape_key: bool = False


@dataclass
class DriversConfig:
    """Collection of driver specs loaded from ``drivers.json``."""

    drivers: list[DriverSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "DriversConfig":
        specs: list[DriverSpec] = []
        for entry in d.get("drivers", []):
            t = entry["target"]
            s = entry["source"]
            specs.append(DriverSpec(
                target_object=t["object"],
                target_bone=t.get("bone"),
                target_property=t["property"],
                target_is_shape_key=bool(t.get("shape_key", False)),
                source_object=s["object"],
                source_bone=s.get("bone"),
                source_property=s["property"],
                source_is_shape_key=bool(s.get("shape_key", False)),
                expression=entry.get("expression", "var"),
            ))
        return cls(drivers=specs)


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
    projection: ProjectionConfig = field(default_factory=ProjectionConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    texture_swap: TextureSwapConfig = field(default_factory=TextureSwapConfig)
    drivers: DriversConfig = field(default_factory=DriversConfig)
    rerandomize: RerandomizeConfig = field(default_factory=RerandomizeConfig)
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

    # --- texture swap ---
    tex_swap_path = d / "texture_swap.json"
    if tex_swap_path.exists():
        texture_swap = TextureSwapConfig.from_dict(
            _load_json(tex_swap_path),
            default_material=materials.skin_material_name,
        )
        texture_swap = texture_swap.resolve(project_root)
    else:
        texture_swap = TextureSwapConfig()

    # --- projection ---
    proj_path = d / "projection.json"
    if proj_path.exists():
        projection = ProjectionConfig.from_dict(_load_json(proj_path))
        projection = projection.resolve(project_root)
    else:
        projection = ProjectionConfig()

    # --- cleanup ---
    cleanup_path = d / "cleanup.json"
    if cleanup_path.exists():
        cleanup = CleanupConfig.from_dict(_load_json(cleanup_path))
        cleanup = cleanup.resolve(project_root)
    else:
        cleanup = CleanupConfig()

    # --- export ---
    export_path = d / "export.json"
    if export_path.exists():
        export = ExportConfig.from_dict(_load_json(export_path))
    else:
        export = ExportConfig()

    # --- drivers ---
    drivers_path = d / "drivers.json"
    if drivers_path.exists():
        drivers = DriversConfig.from_dict(_load_json(drivers_path))
    else:
        drivers = DriversConfig()

    # --- rerandomize ---
    rerandomize_path = d / "rerandomize.json"
    if rerandomize_path.exists():
        rerandomize = RerandomizeConfig.from_dict(_load_json(rerandomize_path))
    else:
        rerandomize = RerandomizeConfig()

    return PipelineConfig(
        runner=runner,
        cleanup=cleanup,
        variation=variation,
        blendshapes=blendshapes,
        constraints=constraints,
        modifiers=modifiers,
        attractor=attractor,
        materials=materials,
        projection=projection,
        export=export,
        texture_swap=texture_swap,
        drivers=drivers,
        rerandomize=rerandomize,
        chaos_joint_names=joint_names,
        config_dir=d,
    )

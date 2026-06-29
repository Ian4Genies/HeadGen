"""
Thin Blender operator layer for Synth Head.

Operators here delegate to scene/ and core/ — no business logic lives here.
"""

import bpy
from pathlib import Path

from .core.math import clamp
from .core.ref_keys import MESH, BODY_GEO, ARMATURE, HEAD_MAT, L_EYE, R_EYE, EYEBROWS, EYELASHES, EYE_MAT, EYE_WEDGE_R, EYE_WEDGE_L, EYE_WEDGE_R_BAKE, EYE_WEDGE_L_BAKE, HD_EYE_R, HD_EYE_L, R_PROJECTOR, L_PROJECTOR, EYE_BOOLEAN_L, EYE_BOOLEAN_R, WEDGE_PROJECTION
from .core.variation import (
    generate_chaos_transforms,
    generate_single_frame_transforms,
    generate_bone_property_values,
    generate_bone_property_values_all_frames,
)
from .scene.fbx_import import import_fbx_and_classify
from .scene.refs import get_ref, set_ref, get_material_ref, set_material_ref, set_flag, get_flag
from .core.blendshapes import (
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
)
from .core.constraints import flatten_params, unflatten_params, constrain
from .core.attractor import get_pool_cache, attract, update_manifest, AttractiveColors
from .scene.blendshapes import (
    apply_blendshape_keyframes,
    apply_blendshape_single_frame,
    _apply_weights_to_shape_keys,
)
from .scene.chaos_anim import (
    collect_chaos_joints,
    apply_chaos_keyframes,
    apply_chaos_single_frame,
    _apply_transforms_to_bones,
    apply_bone_property_values,
)
from .scene.armature import add_object_to_armature, remove_orphan_armatures, remove_non_canonical_armatures, attach_constrained_object_to_armature
from .scene.drivers import build_drivers
from .scene.blend_append import append_material_from_blend, append_object_from_blend, append_gen13_and_classify, append_eye_wedge_bake, append_HD_eyes_only
from .scene.materials import (
    assign_exclusive_material,
    randomize_head_material_color,
    read_material_color,
    apply_attractive_color,
    assign_eye_color,
    hex_to_linear_rgba,
    read_named_node_color,
    apply_named_node_color,
    random_saturated_color,
)
from .scene.modifiers import add_smooth_corrective
from .scene.reset import reset_frame
from .scene.mesh import clean_head_mesh_wedge, Clean_head_mesh_Simple, copy_modifiers_to_wedges, cut_and_sew, join_and_merge
from .scene.snapshot import (
    read_bone_transforms,
    read_shape_key_values,
    apply_bone_transforms,
    apply_shape_key_values,
    apply_material_color,
    read_bone_custom_props,
    apply_bone_custom_prop_values,
)
from .scene.export_bake import scope_bake_environment, bake_head_materials, bake_object_material
from .scene.projection import apply_bake_settings, bake_eye_side, bake_wedge_side, point_image_sequence_node
from .scene.export_glb import staging_scene, rewrite_head_material_slots, stamp_frame_names, export_glb
from .scene.export_pipeline import export_pipeline_generator
from .scene.progress_overlay import SYNTHHEAD_PG_ExportProgress, overlay_refresh, progress_props
from .core.export import frame_glb_name, frame_dir_name, frame_png_name, eye_bake_seq_png_name
from .core.snapshot import build_snapshot, save_snapshot, load_snapshot
from .core.config import load_config, PipelineConfig
from .core.rerandomize import resolve_targets, rerandomize_flat
from .scene.rerandomize import read_flat_params_at_frame, apply_rerandomized_frame
from .core.texture_swap import (
    ping_and_sync_sequence,
    load_manifest,
    pick_texture_index,
    calc_offset,
    name_from_current_offset,
    offset_from_name,
    sequence_prefix,
    sequence_filename,
)
from .scene.texture_swap import (
    point_texture_sequence_node,
    set_sequence_frames,
    key_sequence_offset,
    read_sequence_offset,
    clear_sequence_offset_keyframes,
)

import shutil
import types

import json
from pathlib import Path

_ADDON_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _ADDON_DIR.parent
_CONFIG_DIR = _PROJECT_DIR / "data" / "config"

DEBUG_CONFIG = True


def _get_config() -> PipelineConfig:
    """Load the pipeline config from the standard config directory."""
    cfg = load_config(_CONFIG_DIR)

    if DEBUG_CONFIG:
        _debug_config(cfg)

    return cfg


def _debug_config(cfg: PipelineConfig) -> None:
    """Print a full config dump to the system console."""
    def p(msg: str) -> None:
        print(f"[SynthHead] {msg}")

    p(f"Config loaded from: {_CONFIG_DIR}")
    p(f"Config dir exists:  {_CONFIG_DIR.exists()}")

    p("--- RUNNER ---")
    p(f"  frame_count:     {cfg.runner.frame_count}")
    p(f"  seed:            {cfg.runner.seed}")
    p(f"  fbx_path:        {cfg.runner.fbx_path}")
    p(f"  gen13_blend_path: {cfg.runner.gen13_blend_path}")
    p(f"  save_variation_blend_path:   {cfg.runner.save_variation_blend_path}")
    p(f"  save_water_tight_blend_path: {cfg.runner.save_water_tight_blend_path}")
    p(f"  save_export_blend_path:      {cfg.runner.save_export_blend_path}")
    p(f"  issues_dir:      {cfg.runner.issues_dir}")
    p(f"  good_dir:        {cfg.runner.good_dir}")
    p(f"  attractive_dir:  {cfg.runner.attractive_dir}")
    p(f"  final_output_dir: {cfg.runner.final_output_dir}")

    p(f"--- EXPORT ---")
    p(f"  head_bake_resolution:      {cfg.export.head_bake_resolution}")
    p(f"  eye_wedge_bake_resolution: {cfg.export.eye_wedge_bake_resolution}")
    p(f"  bake_samples:              {cfg.export.bake_samples}")
    p(f"  bake_margin:               {cfg.export.bake_margin}")
    p(f"  glb_format:                {cfg.export.glb_format}")
    p(f"  frame_range:               {cfg.export.frame_range}")
    p(f"  head_bake_material_name:        {cfg.export.head_bake_material_name}")
    p(f"  eye_wedge_R_material_name:     {cfg.export.eye_wedge_R_material_name}")
    p(f"  eye_wedge_L_material_name:     {cfg.export.eye_wedge_L_material_name}")
    p(f"  include_eyes:                  {cfg.export.include_eyes}")
    p(f"  include_brows:                 {cfg.export.include_brows}")
    p(f"  include_lashes:                {cfg.export.include_lashes}")
    p(f"  include_hd_eyes:               {cfg.export.include_hd_eyes}")
    p(f"  include_boolean_cutters:       {cfg.export.include_boolean_cutters}")
    p(f"  bake_wedge_texture_direct:     {cfg.export.bake_wedge_texture_direct}")
    p(f"  copy_eye_projection:           {cfg.export.copy_eye_projection}")
    p(f"  bake_brow_texture_direct:      {cfg.export.bake_brow_texture_direct}")
    p(f"  bake_lash_texture_direct:      {cfg.export.bake_lash_texture_direct}")
    p(f"  bake_hd_eye_texture_direct:    {cfg.export.bake_hd_eye_texture_direct}")
    p(f"  hd_eye_material_name:          {cfg.export.hd_eye_material_name}")
    p(f"  hd_eye_bake_resolution:        {cfg.export.hd_eye_bake_resolution}")

    p(f"--- CHAOS JOINTS ({len(cfg.chaos_joint_names)}) ---")
    p(f"  names:          {sorted(cfg.chaos_joint_names)}")
    p(f"  transform_max:  {cfg.variation.transform_max}")
    p(f"  rotate_max:     {cfg.variation.rotate_max}")
    p(f"  scale_max:      {cfg.variation.scale_max}")
    p(f"  enable_scale:   {cfg.variation.enable_scale}")
    p(f"  overrides ({len(cfg.variation.joint_overrides)}):")
    for k, v in sorted(cfg.variation.joint_overrides.items()):
        p(f"    {k}: {v}")

    p(f"--- BLENDSHAPES ---")
    p(f"  variation_shapes ({len(cfg.blendshapes.variation_shapes)}): {cfg.blendshapes.variation_shapes}")
    p(f"  max_var_shapes:  {cfg.blendshapes.max_var_shapes}")
    p(f"  max_variation:   {cfg.blendshapes.max_variation}")
    p(f"  variation_overrides: {cfg.blendshapes.variation_overrides}")
    p(f"  expression_shapes ({len(cfg.blendshapes.expression_shapes)}): {cfg.blendshapes.expression_shapes}")
    p(f"  expression_max:  {cfg.blendshapes.expression_max}")
    p(f"  expression_overrides: {cfg.blendshapes.expression_overrides}")

    p(f"--- CONSTRAINTS ---")
    p(f"  hard_clamps ({len(cfg.constraints.hard_clamps)}):")
    for k, v in cfg.constraints.hard_clamps.items():
        muted = " [MUTED]" if v.muted else ""
        p(f"    {k}: min={v.min}  max={v.max}{muted}")
    p(f"  relational_rules ({len(cfg.constraints.relational_rules)}):")
    for r in cfg.constraints.relational_rules:
        muted = " [MUTED]" if r.get("muted") else ""
        p(f"    {r.get('type', '?')}: {r.get('title', r.get('target', ''))}{muted}")

    p(f"--- MODIFIERS ---")
    p(f"  factor:           {cfg.modifiers.factor}")
    p(f"  iterations:       {cfg.modifiers.iterations}")
    p(f"  scale:            {cfg.modifiers.scale}")
    p(f"  smooth_type:      {cfg.modifiers.smooth_type}")
    p(f"  use_only_smooth:  {cfg.modifiers.use_only_smooth}")
    p(f"  use_pin_boundary: {cfg.modifiers.use_pin_boundary}")
    p(f"  rest_source:      {cfg.modifiers.rest_source}")

    p(f"--- MATERIALS ---")
    p(f"  skin_material_blend_path: {cfg.materials.skin_material_blend_path}")
    p(f"  skin_material_name:       {cfg.materials.skin_material_name}")
    p(f"  final_color_randomness:   {cfg.materials.final_color_randomness}")
    p(f"  hair_color_node:          {cfg.materials.hair_color_node}")
    p(f"  hair_color_randomness:    {cfg.materials.hair_color_randomness}")
    p(f"  hair_color_defaults:      {len(cfg.materials.hair_color_defaults)} entries")
    p(f"  lip_color_node:           {cfg.materials.lip_color_node}")
    p(f"  lip_color_randomness:     {cfg.materials.lip_color_randomness}")
    p(f"  lip_color_override:       {cfg.materials.lip_color_override}")

    p(f"--- ATTRACTOR ---")
    p(f"  enabled:              {cfg.attractor.enabled}")
    p(f"  debug:                {cfg.attractor.debug}")
    p(f"  attractive_heads_dir: {cfg.attractor.attractive_heads_dir}")
    p(f"  min_attractors:       {cfg.attractor.min_attractors}")
    p(f"  max_attractors:   {cfg.attractor.max_attractors}")
    p(f"  max_influence:    {cfg.attractor.max_influence}")
    p(f"  distance_weights: {cfg.attractor.distance_weights}")
    p(f"  exclude_params:   {cfg.attractor.exclude_params}")

    p(f"--- RERANDOMIZE ---")
    p(f"  enabled:  {cfg.rerandomize.enabled}")
    p(f"  seed:     {cfg.rerandomize.seed}")
    p(f"  reapply_constraints: {cfg.rerandomize.reapply_constraints}")
    p(f"  targets:  {cfg.rerandomize.targets}")

    p(f"--- CLEANUP ---")
    p(f"  assets_blend_path: {cfg.cleanup.assets_blend_path}")
    p(f"  eye_wedge_R_name: {cfg.cleanup.eye_wedge_R_name}")
    p(f"  eye_wedge_L_name: {cfg.cleanup.eye_wedge_L_name}")
    p(f"  mouth_bag_group: {cfg.cleanup.mouth_bag_group}")
    p(f"  mouth_sew_indices: {cfg.cleanup.mouth_sew_indices}")
    # p(f"  eye_wedge_R_indices: {cfg.cleanup.eye_wedge_R_indices}")
    # p(f"  eye_wedge_L_indices: {cfg.cleanup.eye_wedge_L_indices}")


def _blend_colors(
    base: list[float] | tuple[float, ...],
    rng_color: tuple[float, float, float, float],
    randomness: float,
) -> tuple[float, float, float, float]:
    """Lerp base toward rng_color by *randomness* (0 = pure base, 1 = pure rng)."""
    return (
        base[0] + randomness * (rng_color[0] - base[0]),
        base[1] + randomness * (rng_color[1] - base[1]),
        base[2] + randomness * (rng_color[2] - base[2]),
        base[3] + randomness * (rng_color[3] - base[3]),
    )


class SYNTHHEAD_PG_PipelineRefs(bpy.types.PropertyGroup):
    """Live object references managed by the variation pipeline.

    To add a new reference: add a PointerProperty here and a matching
    constant in core/ref_keys.py.  scene/refs.py needs no changes.
    """
    # Head geometry 
    mesh: bpy.props.PointerProperty(
        name="Head Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Body geometry
    body_geo: bpy.props.PointerProperty(
        name="Body Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Armature
    armature: bpy.props.PointerProperty(
        name="Armature",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
    # Eyes
    L_eye: bpy.props.PointerProperty(
        name="Left Eye",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    R_eye: bpy.props.PointerProperty(
        name="Right Eye",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eyebrows
    eyebrows: bpy.props.PointerProperty(
        name="Eyebrows",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eyelashes
    eyelashes: bpy.props.PointerProperty(
        name="Eyelashes",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Head material
    head_mat: bpy.props.PointerProperty(
        name="Head Material",
        type=bpy.types.Material,
    )
    # Eye material
    eye_mat: bpy.props.PointerProperty(
        name="Eye Material",
        type=bpy.types.Material,
    )
    # Eye wedge R
    eye_wedge_R: bpy.props.PointerProperty(
        name="Eye Wedge R",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eye wedge L
    eye_wedge_L: bpy.props.PointerProperty(
        name="Eye Wedge L",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eye wedge R bake
    eye_wedge_R_bake: bpy.props.PointerProperty(
        name="Eye Wedge R Bake",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eye wedge L bake
    eye_wedge_L_bake: bpy.props.PointerProperty(
        name="Eye Wedge L Bake",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # HD eye R
    hd_eye_R: bpy.props.PointerProperty(
        name="HD Eye R",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # HD eye L
    hd_eye_L: bpy.props.PointerProperty(
        name="HD Eye L",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # R projector
    R_projector: bpy.props.PointerProperty(
        name="R Projector",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # L projector
    L_projector: bpy.props.PointerProperty(
        name="L Projector",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Eye boolean cutters
    eye_boolean_L: bpy.props.PointerProperty(
        name="Eye Boolean L",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    eye_boolean_R: bpy.props.PointerProperty(
        name="Eye Boolean R",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Feature flags — written once by VariationPipeline, read by all downstream operators
    wedge_projection: bpy.props.BoolProperty(
        name="Wedge Projection",
        default=False,
    )


class SYNTHHEAD_OT_hello(bpy.types.Operator):
    """Smoke-test operator to verify the addon loads"""

    bl_idname = "synth_head.hello"
    bl_label = "Synth Head: Hello"
    bl_options = {"REGISTER"}

    def execute(self, context):
        self.report({"INFO"}, "Synth Head addon is loaded and working.")
        return {"FINISHED"}


class SYNTHHEAD_OT_ping(bpy.types.Operator):
    """Synth Head is loaded and ready — visible in F3 search as a smoke test"""

    bl_idname = "synth_head.ping"
    bl_label = "Synth Head: Ping"
    bl_description = "Smoke test — confirms Synth Head is active and F3-searchable"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        version = clamp(1.0)
        self.report({"INFO"}, f"Synth Head ping OK  (core.clamp check: {version})")
        return {"FINISHED"}


class SYNTHHEAD_OT_BatchConversion(bpy.types.Operator):
    """Import the Gen13 head and register all scene references — first step before batch operations."""

    bl_idname = "synth_head.batch_conversion"
    bl_label = "Synth Head: Batch Conversion"
    bl_description = "Import the Gen13 head from the configured .blend file and register all scene references"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()

        # # --- IMPORT & CLASSIFY ---
        #head_geo_obj, body_geo_obj, armature_obj, L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj = append_gen13_and_classify(cfg.runner.gen13_blend_path)

        # if not head_geo_obj:
        #     self.report({"ERROR"}, "headOnly_geo mesh not found — aborting")
        #     return {"CANCELLED"}
        # if not body_geo_obj:
        #     self.report({"ERROR"}, "bodyOnly_geo mesh not found — aborting")
        #     return {"CANCELLED"}
        # if not armature_obj:
        #     self.report({"ERROR"}, "Armature not found — aborting")
        #     return {"CANCELLED"}
        # if not L_eye_obj:
        #     self.report({"ERROR"}, "Left eye mesh not found — aborting")
        #     return {"CANCELLED"}
        # if not R_eye_obj:
        #     self.report({"ERROR"}, "Right eye mesh not found — aborting")
        #     return {"CANCELLED"}
        # if not eyebrows_obj:
        #     self.report({"WARNING"}, "Eyebrows mesh not found — continuing without it")
        # if not eyelashes_obj:
        #     self.report({"WARNING"}, "Eyelashes mesh not found — continuing without it")

        # # --- REGISTER REFS ---
        # set_ref(context, MESH, head_geo_obj)
        # set_ref(context, BODY_GEO, body_geo_obj)
        # set_ref(context, ARMATURE, armature_obj)
        # set_ref(context, L_EYE, L_eye_obj)
        # set_ref(context, R_EYE, R_eye_obj)
        # set_ref(context, EYEBROWS, eyebrows_obj)
        # set_ref(context, EYELASHES, eyelashes_obj)

        #import fbx from new string path


        head_geo_obj = bpy.ops.import_scene.fbx(filepath="data\conversion assets\Gen13_Head.fbx")

        # Grab the imported object (it will be selected after import)
        head_geo_obj = bpy.context.selected_objects[0]

        # 





        self.report({"INFO"}, f"Batch Conversion: Gen13 head imported — head='{head_geo_obj.name}'")
        return {"FINISHED"}


class SYNTHHEAD_OT_VariationPipeline(bpy.types.Operator):
    """Run the variation pipeline"""

    bl_idname = "synth_head.variation_pipeline"
    bl_label = "Synth Head: Variation Pipeline"
    bl_description = "Run the variation pipeline"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()
        set_flag(context, WEDGE_PROJECTION, cfg.feature_flags.wedge_projection)

        # --- 1. IMPORT & VALIDATE ---
        # head_geo_obj, body_geo_obj, armature_obj, L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj = import_fbx_and_classify(
        #     context, cfg.runner.fbx_path,
        # )

        (
            head_geo_obj, body_geo_obj, armature_obj,
            L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj,
            L_boolean_obj, R_boolean_obj,
        ) = append_gen13_and_classify(cfg.runner.gen13_blend_path)

        if not head_geo_obj:
            self.report({"ERROR"}, "headOnly_geo mesh not found in FBX — aborting")
            return {"CANCELLED"}
        if not body_geo_obj:
            self.report({"ERROR"}, "bodyOnly_geo mesh not found in FBX — aborting")
            return {"CANCELLED"}
        if not armature_obj:
            self.report({"ERROR"}, "Armature not found in FBX — aborting")
            return {"CANCELLED"}
        if not L_eye_obj:
            self.report({"ERROR"}, "Left eye mesh not found in FBX — aborting")
            return {"CANCELLED"}
        if not R_eye_obj:
            self.report({"ERROR"}, "Right eye mesh not found in FBX — aborting")
            return {"CANCELLED"}
        if not eyebrows_obj:
            self.report({"ERROR"}, "Eyebrows mesh not found in FBX — aborting")
            
        if not eyelashes_obj:
            self.report({"ERROR"}, "Eyelashes mesh not found in FBX — aborting")
        if not L_boolean_obj:
            self.report({"ERROR"}, "eye_L_boolean mesh not found — aborting")
            return {"CANCELLED"}
        if not R_boolean_obj:
            self.report({"ERROR"}, "eye_R_boolean mesh not found — aborting")
            return {"CANCELLED"}

        # set the head mesh and armature references
        set_ref(context, MESH, head_geo_obj)
        set_ref(context, BODY_GEO, body_geo_obj)    
        set_ref(context, ARMATURE, armature_obj)
        set_ref(context, L_EYE, L_eye_obj)
        set_ref(context, R_EYE, R_eye_obj)
        set_ref(context, EYEBROWS, eyebrows_obj)
        set_ref(context, EYELASHES, eyelashes_obj)
        set_ref(context, EYE_BOOLEAN_L, L_boolean_obj)
        set_ref(context, EYE_BOOLEAN_R, R_boolean_obj)
        #hide eyebrows and eyelashes


        
        self.report({"INFO"}, f"head geo: '{head_geo_obj.name}'")
        # --- 1b. APPEND & ASSIGN SKIN MATERIAL ---
        head_mat = get_material_ref(context, HEAD_MAT)
        eye_mat = get_material_ref(context, EYE_MAT)
        if head_mat is None:
            head_mat = append_material_from_blend(
                cfg.materials.skin_material_blend_path,
                cfg.materials.skin_material_name,
            )
            if head_mat is None:
                self.report({"ERROR"}, f"Material '{cfg.materials.skin_material_name}' not found in '{cfg.materials.skin_material_blend_path}' — aborting")
                return {"CANCELLED"}
            set_material_ref(context, HEAD_MAT, head_mat)
        if eye_mat is None:
            eye_mat = append_material_from_blend(
                cfg.materials.skin_material_blend_path,
                cfg.materials.eye_material_name,
            )
            if eye_mat is None:
                self.report({"ERROR"}, f"Material '{cfg.materials.eye_material_name}' not found in '{cfg.materials.skin_material_blend_path}' — aborting")
                return {"CANCELLED"}
            set_material_ref(context, EYE_MAT, eye_mat)
        assign_exclusive_material(head_geo_obj, head_mat)
        assign_exclusive_material(body_geo_obj, head_mat)  
        assign_exclusive_material(L_eye_obj, eye_mat)
        assign_exclusive_material(R_eye_obj, eye_mat)
        
        # --- 2. Eye Setup---
        #EYE WEDGES
        if (cfg.feature_flags.wedge_projection):
            eye_wedge_R_obj = append_object_from_blend(
                cfg.cleanup.assets_blend_path, 
                cfg.cleanup.eye_wedge_R_name)
            
            
            eye_wedge_L_obj = append_object_from_blend(
                cfg.cleanup.assets_blend_path, 
                cfg.cleanup.eye_wedge_L_name)

            add_object_to_armature(eye_wedge_R_obj, armature_obj)
            add_object_to_armature(eye_wedge_L_obj, armature_obj)
        
            set_ref(context, EYE_WEDGE_R, eye_wedge_R_obj)
            set_ref(context, EYE_WEDGE_L, eye_wedge_L_obj)

            eye_wedge_R_bake, eye_wedge_L_bake, hd_eye_R, hd_eye_L, R_projector, L_projector = append_eye_wedge_bake(
                cfg.projection.assets_blend_path,
                cfg.projection.eye_wedge_R_bake_name,
                cfg.projection.eye_wedge_L_bake_name,
                cfg.projection.hd_eye_R_name,
                cfg.projection.hd_eye_L_name,
                cfg.projection.R_projector_name,
                cfg.projection.L_projector_name)
            
            set_ref(context, EYE_WEDGE_R_BAKE, eye_wedge_R_bake)
            set_ref(context, EYE_WEDGE_L_BAKE, eye_wedge_L_bake)
            set_ref(context, HD_EYE_R, hd_eye_R)
            set_ref(context, HD_EYE_L, hd_eye_L)
            set_ref(context, R_PROJECTOR, R_projector)
            set_ref(context, L_PROJECTOR, L_projector)

            add_object_to_armature(eye_wedge_R_bake, armature_obj)
            add_object_to_armature(eye_wedge_L_bake, armature_obj)
            add_object_to_armature(hd_eye_R, armature_obj)
            add_object_to_armature(hd_eye_L, armature_obj)
            attach_constrained_object_to_armature(hd_eye_R, armature_obj)
            attach_constrained_object_to_armature(hd_eye_L, armature_obj)
            add_object_to_armature(R_projector, armature_obj)
            add_object_to_armature(L_projector, armature_obj)
            remove_non_canonical_armatures(armature_obj)

        #HD EYES ONLY
        else:
            hd_eye_R, hd_eye_L = append_HD_eyes_only(
                cfg.projection.assets_blend_path,
                cfg.projection.hd_eye_R_name,
                cfg.projection.hd_eye_L_name)
            set_ref(context, HD_EYE_R, hd_eye_R)
            set_ref(context, HD_EYE_L, hd_eye_L)

            add_object_to_armature(hd_eye_R, armature_obj)
            add_object_to_armature(hd_eye_L, armature_obj)
            attach_constrained_object_to_armature(hd_eye_R, armature_obj)
            attach_constrained_object_to_armature(hd_eye_L, armature_obj)
            remove_non_canonical_armatures(armature_obj)
            assign_exclusive_material(hd_eye_R, eye_mat)
            assign_exclusive_material(hd_eye_L, eye_mat)

        # --- 2b. RIG SETUP — rebuild drivers from config ---
        build_drivers(armature_obj, cfg.drivers)

        self.report({"INFO"}, f"Skin material assigned: '{head_mat.name}'")
        # --- 3. GENERATE RAW PARAMETERS ---
        armature = get_ref(context, ARMATURE)
        chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)
        self.report({"INFO"}, f"Chaos joints found: {[b.name for b in chaos_joints]}")

        joint_names = [b.name for b in chaos_joints]
        # generate_chaos_transforms generates a dict of joint names to transforms
        all_transforms = generate_chaos_transforms(cfg.variation, joint_names)
        # generate_blendshape_weights generates a dict of shape names to weights
        head_mesh = get_ref(context, MESH)
        all_bs_weights = generate_blendshape_weights(cfg.blendshapes)
        # generate bone property values (iris/pupil) to be applied to a chaos bone
        all_bone_prop_values = generate_bone_property_values_all_frames(cfg.variation)

        # --- 4. SYNC ATTRACTOR POOL---
        # get_pool_cache returns a PoolCache object
        # PoolCache is a dict of frame numbers to dicts of joint names to transforms
        # The dicts of joint names to transforms are the attractor pool
        pool = get_pool_cache()
        # if attractor is enabled, sync the pool
        if cfg.attractor.enabled:
            sync_report = pool.sync(cfg.attractor.attractive_heads_dir, joint_names)
            if pool.pool_size > 0:
                self.report({"INFO"}, f"Attractor pool: {pool.pool_size} attractive heads")
                if cfg.attractor.debug and sync_report["changed"]:
                    print(f"[SynthHead][Attractor] Pool synced — "
                          f"added: {sync_report['added']}, "
                          f"removed: {sync_report['removed']}, "
                          f"total: {sync_report['pool_size']}")
            else:
                self.report({"WARNING"}, "Attractor enabled but no good heads found")

        # --- 4b. TEXTURE SWAP — ping/rebuild sequences, configure nodes ---
        # frame_duration must exceed the timeline length so Blender's internal
        # clamp never fires before the per-frame offset is applied.
        fc = cfg.runner.frame_count
        tex_frame_duration = fc + 100
        slot_manifests: dict = {}
        for slot in cfg.texture_swap.slots:
            manifest = ping_and_sync_sequence(slot)
            slot_manifests[slot.key] = manifest
            mat = bpy.data.materials.get(slot.material_name)
            if mat:
                first_file = Path(slot.sequence_path) / sequence_filename(sequence_prefix(slot), 1)
                point_texture_sequence_node(mat, slot.node_name, first_file, 1, tex_frame_duration)
                set_sequence_frames(mat, slot.node_name, tex_frame_duration)
                clear_sequence_offset_keyframes(mat, slot.node_name)
        self.report({"INFO"}, f"Texture swap: {len(slot_manifests)} sequence(s) synced")

        import random as _random
        attractor_rng = _random.Random(cfg.runner.seed)
        # --- 5. CONSTRAIN EACH FRAME (attract → constrain → split) ---
        constrained_transforms: dict[int, dict] = {}
        constrained_bs: dict[int, dict[str, float]] = {}
        attractive_colors: dict[int, AttractiveColors] = {}
        
        for frame in range(1, fc + 1):
            # merge bone property values into blendshape weights so they travel
            # through the attractor / constraint pipeline together
            combined_bs = {**all_bs_weights[frame], **all_bone_prop_values[frame]}
            # flat is a dict of param names to values
            flat = flatten_params(all_transforms[frame], combined_bs)
            # attract nudges the flat params toward the attractor pool and returns
            # an attractive color blended from the same pool heads and weights
            flat, colors, dbg = attract(flat, pool, cfg.attractor, cfg.variation, cfg.blendshapes, attractor_rng)
            attractive_colors[frame] = colors
            # print debug info if it exists
            if dbg is not None:
                print(f"[SynthHead][Attractor] frame {frame:03d}: "
                      f"n={dbg['n_selected']}  "
                      f"mean_delta={dbg['mean_abs_delta']:.5f}  "
                      f"files={[f.replace('good_frame', 'f') for f in dbg['selected_files']]}")
            # constrain enforces hard clamps and relational rules
            flat = constrain(flat, cfg.constraints)
            # unflatten_params converts the flat params back into a dict of joint names to transforms and a dict of shape names to weights
            xforms, weights = unflatten_params(flat, joint_names)
            # store the constrained transforms and weights for this frame
            constrained_transforms[frame] = xforms
            # store the constrained weights for this frame
            constrained_bs[frame] = weights
        # --- 6. BAKE TO SCENE (pose bones + shape keys + material color + texture offsets per frame) ---
        color_rng = _random.Random(cfg.runner.seed + 1 if cfg.runner.seed is not None else None)
        texture_rng = _random.Random(cfg.runner.seed + 2 if cfg.runner.seed is not None else None)
        hair_rng = _random.Random(cfg.runner.seed + 3 if cfg.runner.seed is not None else None)
        lip_rng = _random.Random(cfg.runner.seed + 4 if cfg.runner.seed is not None else None)
        for frame in range(1, fc + 1):
            context.scene.frame_set(frame)
            if (cfg.feature_flags.wedge_projection):
                reset_frame(chaos_joints, [head_mesh, eye_wedge_R_obj, eye_wedge_L_obj, eyebrows_obj, eyelashes_obj], frame)
            else:
                reset_frame(chaos_joints, [head_mesh, hd_eye_R, hd_eye_L, eyebrows_obj, eyelashes_obj], frame)
            
            #Core Head Parts
            _apply_transforms_to_bones(chaos_joints, constrained_transforms[frame], frame)
            _apply_weights_to_shape_keys(head_mesh, constrained_bs[frame], frame)
            #Eye Wedge Parts
            if (cfg.feature_flags.wedge_projection):
                _apply_weights_to_shape_keys(eye_wedge_R_obj, constrained_bs[frame], frame)
                _apply_weights_to_shape_keys(eye_wedge_L_obj, constrained_bs[frame], frame)
                _apply_weights_to_shape_keys(eye_wedge_R_bake, constrained_bs[frame], frame)
                _apply_weights_to_shape_keys(eye_wedge_L_bake, constrained_bs[frame], frame)
                _apply_weights_to_shape_keys(R_projector, constrained_bs[frame], frame)
                _apply_weights_to_shape_keys(L_projector, constrained_bs[frame], frame)
            

            #Eyebrows and Eyelashes
            _apply_weights_to_shape_keys(eyebrows_obj, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(eyelashes_obj, constrained_bs[frame], frame)
            # add eye boolean cutters

            #Bone custom properties (iris/pupil) — routed to blendshapes via driver system
            apply_bone_property_values(armature, constrained_bs[frame], cfg.variation.bone_properties, frame)
            #Skin / Body Color
            colors = attractive_colors[frame]
            rng_color = (color_rng.random(), color_rng.random(), color_rng.random(), 1.0)
            randomize_head_material_color(head_mesh, rng_color, frame)
            #add color to eye wedge bake meshes
            if (cfg.feature_flags.wedge_projection):
                assign_eye_color(eye_wedge_R_bake, cfg.projection.eye_wedge_R_bake_name, cfg.projection.eye_color_name, rng_color, frame)
                assign_eye_color(eye_wedge_L_bake, cfg.projection.eye_wedge_L_bake_name, cfg.projection.eye_color_name, rng_color, frame)
            else:
                assign_eye_color(hd_eye_R, eye_mat.name, cfg.projection.eye_color_name, rng_color, frame)
                assign_eye_color(hd_eye_L, eye_mat.name, cfg.projection.eye_color_name, rng_color, frame)
            attr_color = colors.body
            if attr_color is not None:
                final_skin_color = _blend_colors(attr_color, rng_color, cfg.materials.final_color_randomness)
                apply_attractive_color(head_mesh, attr_color, rng_color, cfg.materials.final_color_randomness, frame)
            else:
                final_skin_color = rng_color
            #Hair Color
            attractive_hair = colors.hair
            if attractive_hair is None:
                if cfg.materials.hair_color_defaults:
                    base_hair = hex_to_linear_rgba(hair_rng.choice(cfg.materials.hair_color_defaults))
                else:
                    base_hair = [0.02, 0.01, 0.005, 1.0]
            else:
                base_hair = attractive_hair
            rng_hair = (hair_rng.random(), hair_rng.random(), hair_rng.random(), 1.0)
            final_hair = _blend_colors(base_hair, rng_hair, cfg.materials.hair_color_randomness)
            apply_named_node_color(head_mesh, cfg.materials.hair_color_node, final_hair, frame)
            #Lip Color
            if lip_rng.random() < cfg.materials.lip_color_override:
                final_lip = random_saturated_color(lip_rng)
            else:
                attractive_lip = colors.lip
                base_lip: list[float] | tuple[float, ...] = attractive_lip if attractive_lip is not None else final_skin_color
                rng_lip = (lip_rng.random(), lip_rng.random(), lip_rng.random(), 1.0)
                final_lip = _blend_colors(base_lip, rng_lip, cfg.materials.lip_color_randomness)
            apply_named_node_color(head_mesh, cfg.materials.lip_color_node, final_lip, frame)
            # Texture overlay offset keying
            for slot in cfg.texture_swap.slots:
                slot_manifest = slot_manifests.get(slot.key)
                if slot_manifest is None:
                    continue
                mat = bpy.data.materials.get(slot.material_name)
                if mat is None:
                    continue
                idx = 1 if not slot.enabled else pick_texture_index(slot_manifest, slot.percentage, texture_rng)
                key_sequence_offset(mat, slot.node_name, calc_offset(idx, frame), frame)
        self.report({"INFO"}, f"Applied {fc} frames (reset + joints + blendshapes + material color + texture offsets)")
        # --- 7. cleanup

        
        # --- 7. POST-PROCESS & SAVE --
        #add_smooth_corrective(head_mesh, cfg.modifiers)


        
        eyebrows_obj.hide_viewport = True
        eyelashes_obj.hide_viewport = True

        if (cfg.feature_flags.wedge_projection):
            #eye_wedge_R_obj.hide_viewport = True
            #eye_wedge_L_obj.hide_viewport = True
            #eye_wedge_R_bake.hide_set(True)
            #eye_wedge_L_bake.hide_set(True)
            eye_wedge_L_obj.hide_set(True)
            eye_wedge_R_obj.hide_set(True)

            R_projector.hide_viewport = True
            L_projector.hide_viewport = True
            hd_eye_R.hide_viewport = True
            hd_eye_L.hide_viewport = True

        L_eye_obj.hide_viewport = True
        R_eye_obj.hide_viewport = True
        


        Path(cfg.runner.save_variation_blend_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_variation_blend_path)
        return {"FINISHED"}


class SYNTHHEAD_OT_RandomizeFace(bpy.types.Operator):
    """Re-randomize chaos joint transforms on the current frame"""

    bl_idname = "synth_head.randomize_face"
    bl_label = "Synth Head: Randomize Face"
    bl_description = "Generate new random chaos transforms on the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()
        wedge_projection = get_flag(context, WEDGE_PROJECTION)

        armature = get_ref(context, ARMATURE)
        if not armature:
            self.report({"ERROR"}, "No armature stored — run Variation Pipeline first")
            return {"CANCELLED"}

        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        if wedge_projection:
            eye_wedge_R_obj = get_ref(context, EYE_WEDGE_R)
            if not eye_wedge_R_obj:
                self.report({"ERROR"}, "No eye wedge R mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_L_obj = get_ref(context, EYE_WEDGE_L)
            if not eye_wedge_L_obj:
                self.report({"ERROR"}, "No eye wedge L mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_R_bake = get_ref(context, EYE_WEDGE_R_BAKE)
            if not eye_wedge_R_bake:
                self.report({"ERROR"}, "No eye wedge R bake mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_L_bake = get_ref(context, EYE_WEDGE_L_BAKE)
            if not eye_wedge_L_bake:
                self.report({"ERROR"}, "No eye wedge L bake mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            R_projector = get_ref(context, R_PROJECTOR)
            if not R_projector:
                self.report({"ERROR"}, "No R projector mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            L_projector = get_ref(context, L_PROJECTOR)
            if not L_projector:
                self.report({"ERROR"}, "No L projector mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
        else:
            eye_mat = get_material_ref(context, EYE_MAT)
            if not eye_mat:
                self.report({"ERROR"}, "No eye material stored — run Variation Pipeline first")
                return {"CANCELLED"}

        hd_eye_R = get_ref(context, HD_EYE_R)
        if not hd_eye_R:
            self.report({"ERROR"}, "No HD eye R stored — run Variation Pipeline first")
            return {"CANCELLED"}
        hd_eye_L = get_ref(context, HD_EYE_L)
        if not hd_eye_L:
            self.report({"ERROR"}, "No HD eye L stored — run Variation Pipeline first")
            return {"CANCELLED"}

        eyebrows_obj = get_ref(context, EYEBROWS)
        if not eyebrows_obj:
            self.report({"ERROR"}, "No eyebrows mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}
        eyelashes_obj = get_ref(context, EYELASHES)
        if not eyelashes_obj:
            self.report({"ERROR"}, "No eyelashes mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}
        body_geo_obj = get_ref(context, BODY_GEO)
        if not body_geo_obj:
            self.report({"ERROR"}, "No body mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}




        chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)
        if not chaos_joints:
            self.report({"ERROR"}, "No chaos joints found on armature")
            return {"CANCELLED"}

        joint_names = [b.name for b in chaos_joints]
        transforms = generate_single_frame_transforms(cfg.variation, joint_names)
        bs_weights = generate_single_frame_blendshape_weights(cfg.blendshapes)
        bone_prop_values = generate_bone_property_values(cfg.variation)
        bs_weights = {**bs_weights, **bone_prop_values}

        pool = get_pool_cache()
        if cfg.attractor.enabled:
            sync_report = pool.sync(cfg.attractor.attractive_heads_dir, joint_names)
            if cfg.attractor.debug and sync_report["changed"]:
                print(f"[SynthHead][Attractor] Pool synced — "
                      f"added: {sync_report['added']}, "
                      f"removed: {sync_report['removed']}, "
                      f"total: {sync_report['pool_size']}")

        import random as _random
        attractor_rng = _random.Random()

        flat = flatten_params(transforms, bs_weights)
        flat, colors, dbg = attract(flat, pool, cfg.attractor, cfg.variation, cfg.blendshapes, attractor_rng)
        if dbg is not None:
            print(f"[SynthHead][Attractor] RandomizeFace: "
                  f"n={dbg['n_selected']}  "
                  f"mean_delta={dbg['mean_abs_delta']:.5f}  "
                  f"files={[f.replace('good_frame', 'f') for f in dbg['selected_files']]}")
        flat = constrain(flat, cfg.constraints)
        transforms, bs_weights = unflatten_params(flat, joint_names)

        frame = context.scene.frame_current

        if wedge_projection:
            reset_frame(chaos_joints, [head_mesh, eye_wedge_R_obj, eye_wedge_L_obj, eyebrows_obj, eyelashes_obj], frame)
        else:
            reset_frame(chaos_joints, [head_mesh, hd_eye_R, hd_eye_L, eyebrows_obj, eyelashes_obj], frame)
        _apply_transforms_to_bones(chaos_joints, transforms, frame)
        _apply_weights_to_shape_keys(head_mesh, bs_weights, frame)
        if wedge_projection:
            _apply_weights_to_shape_keys(eye_wedge_R_obj, bs_weights, frame)
            _apply_weights_to_shape_keys(eye_wedge_L_obj, bs_weights, frame)
            _apply_weights_to_shape_keys(eye_wedge_R_bake, bs_weights, frame)
            _apply_weights_to_shape_keys(eye_wedge_L_bake, bs_weights, frame)
            _apply_weights_to_shape_keys(R_projector, bs_weights, frame)
            _apply_weights_to_shape_keys(L_projector, bs_weights, frame)
        _apply_weights_to_shape_keys(eyebrows_obj, bs_weights, frame)
        _apply_weights_to_shape_keys(eyelashes_obj, bs_weights, frame)

        #See properties in chaos_joints.json and drivers in drivers.json for linkedges
        apply_bone_property_values(armature, bs_weights, cfg.variation.bone_properties, frame)

        #Skin / Body Color
        rng_color = (attractor_rng.random(), attractor_rng.random(), attractor_rng.random(), 1.0)
        randomize_head_material_color(head_mesh, rng_color, frame)
        if wedge_projection:
            assign_eye_color(eye_wedge_R_bake, cfg.projection.eye_wedge_R_bake_name, cfg.projection.eye_color_name, rng_color, frame)
            assign_eye_color(eye_wedge_L_bake, cfg.projection.eye_wedge_L_bake_name, cfg.projection.eye_color_name, rng_color, frame)
        else:
            assign_eye_color(hd_eye_R, eye_mat.name, cfg.projection.eye_color_name, rng_color, frame)
            assign_eye_color(hd_eye_L, eye_mat.name, cfg.projection.eye_color_name, rng_color, frame)
        attr_color = colors.body
        if attr_color is not None:
            final_skin_color = _blend_colors(attr_color, rng_color, cfg.materials.final_color_randomness)
            apply_attractive_color(head_mesh, attr_color, rng_color, cfg.materials.final_color_randomness, frame)
        else:
            final_skin_color = rng_color
        #Hair Color
        attractive_hair = colors.hair
        if attractive_hair is None:
            if cfg.materials.hair_color_defaults:
                base_hair = hex_to_linear_rgba(attractor_rng.choice(cfg.materials.hair_color_defaults))
            else:
                base_hair = [0.02, 0.01, 0.005, 1.0]
        else:
            base_hair = attractive_hair
        rng_hair = (attractor_rng.random(), attractor_rng.random(), attractor_rng.random(), 1.0)
        final_hair = _blend_colors(base_hair, rng_hair, cfg.materials.hair_color_randomness)
        apply_named_node_color(head_mesh, cfg.materials.hair_color_node, final_hair, frame)
        #Lip Color
        if attractor_rng.random() < cfg.materials.lip_color_override:
            final_lip = random_saturated_color(attractor_rng)
        else:
            attractive_lip = colors.lip
            base_lip: list[float] | tuple[float, ...] = attractive_lip if attractive_lip is not None else final_skin_color
            rng_lip = (attractor_rng.random(), attractor_rng.random(), attractor_rng.random(), 1.0)
            final_lip = _blend_colors(base_lip, rng_lip, cfg.materials.lip_color_randomness)
        apply_named_node_color(head_mesh, cfg.materials.lip_color_node, final_lip, frame)

        # Texture overlay — read existing manifests, pick and key offsets
        import random as _tex_random
        texture_rng = _tex_random.Random()
        for slot in cfg.texture_swap.slots:
            slot_manifest = load_manifest(slot.sequence_path)
            if slot_manifest is None:
                self.report({"WARNING"}, f"No texture manifest for '{slot.key}' — skipping overlay")
                continue
            mat = bpy.data.materials.get(slot.material_name)
            if mat is None:
                continue
            idx = 1 if not slot.enabled else pick_texture_index(slot_manifest, slot.percentage, texture_rng)
            key_sequence_offset(mat, slot.node_name, calc_offset(idx, frame), frame)

        self.report({"INFO"}, f"Randomized {len(chaos_joints)} joints + blendshapes on frame {frame}")
        return {"FINISHED"}


def _guard_rerandomize_refs(operator, context) -> bool:
    """Return True when all refs required for selective rerandomize are present."""
    wedge_projection = get_flag(context, WEDGE_PROJECTION)

    checks = [
        (ARMATURE, "No armature stored — run Variation Pipeline first"),
        (MESH, "No mesh stored — run Variation Pipeline first"),
        (HD_EYE_R, "No HD eye R stored — run Variation Pipeline first"),
        (HD_EYE_L, "No HD eye L stored — run Variation Pipeline first"),
        (EYEBROWS, "No eyebrows mesh stored — run Variation Pipeline first"),
        (EYELASHES, "No eyelashes mesh stored — run Variation Pipeline first"),
    ]
    if wedge_projection:
        checks += [
            (EYE_WEDGE_R, "No eye wedge R mesh stored — run Variation Pipeline first"),
            (EYE_WEDGE_L, "No eye wedge L mesh stored — run Variation Pipeline first"),
            (EYE_WEDGE_R_BAKE, "No eye wedge R bake mesh stored — run Variation Pipeline first"),
            (EYE_WEDGE_L_BAKE, "No eye wedge L bake mesh stored — run Variation Pipeline first"),
            (R_PROJECTOR, "No R projector mesh stored — run Variation Pipeline first"),
            (L_PROJECTOR, "No L projector mesh stored — run Variation Pipeline first"),
        ]

    for ref_key, message in checks:
        if not get_ref(context, ref_key):
            operator.report({"ERROR"}, message)
            return False
    return True


def _execute_rerandomize(operator, context, frames: list[int]) -> set[str]:
    """Shared selective rerandomize logic for one or more frames."""
    import random as _random

    if not _guard_rerandomize_refs(operator, context):
        return {"CANCELLED"}

    cfg = _get_config()
    rr = cfg.rerandomize

    if not rr.enabled:
        operator.report({"INFO"}, "Rerandomize disabled in rerandomize.json")
        return {"FINISHED"}

    if not rr.targets:
        operator.report({"ERROR"}, "rerandomize.json targets list is empty")
        return {"CANCELLED"}

    resolved, errors = resolve_targets(rr.targets, cfg)
    for msg in errors:
        operator.report({"ERROR"}, msg)
        return {"CANCELLED"}

    if not resolved:
        operator.report({"ERROR"}, "No targets resolved — check rerandomize.json")
        return {"CANCELLED"}

    rng = _random.Random(rr.seed) if rr.seed is not None else _random.Random()

    for frame in frames:
        flat = read_flat_params_at_frame(context, cfg, frame)
        if not flat:
            operator.report({"ERROR"}, f"Could not read parameters at frame {frame}")
            return {"CANCELLED"}
        flat, apply_keys = rerandomize_flat(flat, resolved, rng, cfg)
        apply_rerandomized_frame(context, cfg, frame, flat, apply_keys)

    operator.report(
        {"INFO"},
        f"Rerandomized {len(resolved)} parameter(s) on {len(frames)} frame(s)",
    )
    return {"FINISHED"}


class SYNTHHEAD_OT_RerandomizeSelected(bpy.types.Operator):
    """Re-randomize configured parameters across all variation frames"""

    bl_idname = "synth_head.rerandomize_selected"
    bl_label = "Synth Head: Rerandomize Selected"
    bl_description = (
        "Re-sample parameters listed in rerandomize.json across every frame "
        "in runner.frame_count"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()
        frames = list(range(1, cfg.runner.frame_count + 1))
        return _execute_rerandomize(self, context, frames)


class SYNTHHEAD_OT_RerandomizeSelectedFrame(bpy.types.Operator):
    """Re-randomize configured parameters on the current frame only"""

    bl_idname = "synth_head.rerandomize_selected_frame"
    bl_label = "Synth Head: Rerandomize Selected Frame"
    bl_description = (
        "Re-sample parameters listed in rerandomize.json on the current frame only"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_rerandomize(self, context, [context.scene.frame_current])


def _load_config_dir_raw(cfg: PipelineConfig) -> dict:
    """Read every JSON file in the config directory for embedding in snapshots."""
    raw: dict = {}
    if cfg.config_dir.is_dir():
        for p in sorted(cfg.config_dir.glob("*.json")):
            with p.open("r", encoding="utf-8") as f:
                raw[p.stem] = json.load(f)
    return raw


def _save_head_snapshot(operator, context, label: str, directory: Path) -> set[str]:
    """Shared logic for Save Head Issue / Save Good Head operators."""
    armature = get_ref(context, ARMATURE)
    if not armature:
        operator.report({"ERROR"}, "No armature stored — run Variation Pipeline first")
        return {"CANCELLED"}

    head_mesh = get_ref(context, MESH)
    if not head_mesh:
        operator.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
        return {"CANCELLED"}

    cfg = _get_config()

    joint_data = read_bone_transforms(armature, cfg.chaos_joint_names)
    var_shapes, expr_shapes = read_shape_key_values(
        head_mesh,
        cfg.blendshapes.variation_shapes + list(cfg.blendshapes.independent_shapes.keys()),
        cfg.blendshapes.expression_shapes,
    )
    bone_prop_data = read_bone_custom_props(armature, cfg.variation.bone_properties)
    skin_color = read_material_color(head_mesh)
    hair_color = read_named_node_color(head_mesh, cfg.materials.hair_color_node)
    lip_color = read_named_node_color(head_mesh, cfg.materials.lip_color_node)

    config_raw = _load_config_dir_raw(cfg)

    # Capture active texture overlay names from image sequence nodes
    snap_frame = context.scene.frame_current
    texture_overlays: dict[str, str] = {}
    for slot in cfg.texture_swap.slots:
        slot_manifest = load_manifest(slot.sequence_path)
        mat = bpy.data.materials.get(slot.material_name)
        if slot_manifest is None or mat is None:
            continue
        offset = read_sequence_offset(mat, slot.node_name)
        if offset is None:
            continue
        texture_overlays[slot.key] = name_from_current_offset(offset, snap_frame, slot_manifest)

    snapshot = build_snapshot(
        chaos_joints=joint_data,
        variation_shapes=var_shapes,
        expression_shapes=expr_shapes,
        bone_properties=bone_prop_data,
        config_snapshot=config_raw,
        frame=snap_frame,
        label=label,
        note=operator.note,
        skin_color=skin_color,
        hair_color=hair_color,
        lip_color=lip_color,
        texture_overlays=texture_overlays if texture_overlays else None,
    )

    saved = save_snapshot(snapshot, directory)
    update_manifest(directory)
    operator.report({"INFO"}, f"Saved {label} snapshot → {saved.name}")
    return {"FINISHED"}


class SYNTHHEAD_OT_SaveHeadIssue(bpy.types.Operator):
    """Save current head state as an issue snapshot"""

    bl_idname = "synth_head.save_head_issue"
    bl_label = "Synth Head: Save Head Issue"
    bl_description = "Snapshot all tracked head data to data/head-issues/"
    bl_options = {"REGISTER"}

    note: bpy.props.StringProperty(
        name="Note",
        description="Optional description of the issue",
        default="",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        self.layout.prop(self, "note", text="Note")

    def execute(self, context):
        cfg = _get_config()
        return _save_head_snapshot(self, context, "issue", Path(cfg.runner.issues_dir))


class SYNTHHEAD_OT_SaveGoodHead(bpy.types.Operator):
    """Save current head state as a good-head reference snapshot"""

    bl_idname = "synth_head.save_good_head"
    bl_label = "Synth Head: Save Good Head"
    bl_description = "Snapshot all tracked head data to data/head-good/"
    bl_options = {"REGISTER"}

    note: bpy.props.StringProperty(
        name="Note",
        description="Optional note about this head",
        default="",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        self.layout.prop(self, "note", text="Note")

    def execute(self, context):
        cfg = _get_config()
        return _save_head_snapshot(self, context, "good", Path(cfg.runner.good_dir))


class SYNTHHEAD_OT_SaveHeadAttractive(bpy.types.Operator):
    """Save current head state as an attractive snapshot"""
    bl_idname = "synth_head.save_head_attractive"
    bl_label = "Synth Head: Save Head Attractive"
    bl_description = "Snapshot all tracked head data to data/head-attractive/"
    bl_options = {"REGISTER"}

    note: bpy.props.StringProperty(
        name="Note",
        description="Optional description of the attractive",
        default="",
    )   
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    def draw(self, context):
        self.layout.prop(self, "note", text="Note")
    def execute(self, context):
        cfg = _get_config()
        return _save_head_snapshot(self, context, "attractive", Path(cfg.runner.attractive_dir))


class SYNTHHEAD_OT_LoadHeadData(bpy.types.Operator):
    """Load a saved head snapshot and apply it on the current frame"""

    bl_idname = "synth_head.load_head_data"
    bl_label = "Synth Head: Load Head Data"
    bl_description = "Load a snapshot JSON and apply transforms + shape keys"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        data_dir = _PROJECT_DIR / "data"
        self.filepath = str(data_dir) + "\\"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        wedge_projection = get_flag(context, WEDGE_PROJECTION)

        armature = get_ref(context, ARMATURE)
        if not armature:
            self.report({"ERROR"}, "No armature stored — run Variation Pipeline first")
            return {"CANCELLED"}

        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        hd_eye_R = get_ref(context, HD_EYE_R)
        if not hd_eye_R:
            self.report({"ERROR"}, "No HD eye R stored — run Variation Pipeline first")
            return {"CANCELLED"}
        hd_eye_L = get_ref(context, HD_EYE_L)
        if not hd_eye_L:
            self.report({"ERROR"}, "No HD eye L stored — run Variation Pipeline first")
            return {"CANCELLED"}

        if wedge_projection:
            eye_wedge_R_obj = get_ref(context, EYE_WEDGE_R)
            if not eye_wedge_R_obj:
                self.report({"ERROR"}, "No eye wedge R mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_L_obj = get_ref(context, EYE_WEDGE_L)
            if not eye_wedge_L_obj:
                self.report({"ERROR"}, "No eye wedge L mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_R_bake = get_ref(context, EYE_WEDGE_R_BAKE)
            if not eye_wedge_R_bake:
                self.report({"ERROR"}, "No eye wedge R bake mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            eye_wedge_L_bake = get_ref(context, EYE_WEDGE_L_BAKE)
            if not eye_wedge_L_bake:
                self.report({"ERROR"}, "No eye wedge L bake mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            R_projector = get_ref(context, R_PROJECTOR)
            if not R_projector:
                self.report({"ERROR"}, "No R projector mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
            L_projector = get_ref(context, L_PROJECTOR)
            if not L_projector:
                self.report({"ERROR"}, "No L projector mesh stored — run Variation Pipeline first")
                return {"CANCELLED"}
        else:
            eye_mat = get_material_ref(context, EYE_MAT)
            if not eye_mat:
                self.report({"ERROR"}, "No eye material stored — run Variation Pipeline first")
                return {"CANCELLED"}

        eyebrows_obj = get_ref(context, EYEBROWS)
        if not eyebrows_obj:
            self.report({"ERROR"}, "No eyebrows mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}
        eyelashes_obj = get_ref(context, EYELASHES)
        if not eyelashes_obj:
            self.report({"ERROR"}, "No eyelashes mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        cfg = _get_config()
        snapshot = load_snapshot(self.filepath)
        frame = context.scene.frame_current

        chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)

        if wedge_projection:
            reset_frame(chaos_joints, [head_mesh, eye_wedge_R_obj, eye_wedge_L_obj, eye_wedge_R_bake, eye_wedge_L_bake, R_projector, L_projector, hd_eye_R, hd_eye_L, eyebrows_obj, eyelashes_obj], frame)
        else:
            reset_frame(chaos_joints, [head_mesh, hd_eye_R, hd_eye_L, eyebrows_obj, eyelashes_obj], frame)
        apply_bone_transforms(armature, snapshot.get("chaos_joints", {}), frame)

        all_shapes: dict[str, float] = {}
        all_shapes.update(snapshot.get("variation_shapes", {}))
        all_shapes.update(snapshot.get("expression_shapes", {}))
        apply_shape_key_values(head_mesh, all_shapes, frame)
        if wedge_projection:
            apply_shape_key_values(eye_wedge_R_obj, all_shapes, frame)
            apply_shape_key_values(eye_wedge_L_obj, all_shapes, frame)
            apply_shape_key_values(eye_wedge_R_bake, all_shapes, frame)
            apply_shape_key_values(eye_wedge_L_bake, all_shapes, frame)
            apply_shape_key_values(R_projector, all_shapes, frame)
            apply_shape_key_values(L_projector, all_shapes, frame)
        apply_shape_key_values(eyebrows_obj, all_shapes, frame)
        apply_shape_key_values(eyelashes_obj, all_shapes, frame)
        apply_bone_custom_prop_values(armature, snapshot.get("bone_properties", {}), cfg.variation.bone_properties, frame)

        skin_color = snapshot.get("skin_color")
        if skin_color is not None:
            apply_material_color(head_mesh, skin_color, frame)
            if wedge_projection:
                assign_eye_color(eye_wedge_R_bake, cfg.projection.eye_wedge_R_bake_name, cfg.projection.eye_color_name, skin_color, frame)
                assign_eye_color(eye_wedge_L_bake, cfg.projection.eye_wedge_L_bake_name, cfg.projection.eye_color_name, skin_color, frame)
            else:
                assign_eye_color(hd_eye_R, eye_mat.name, cfg.projection.eye_color_name, skin_color, frame)
                assign_eye_color(hd_eye_L, eye_mat.name, cfg.projection.eye_color_name, skin_color, frame)

        hair_color = snapshot.get("hair_color")
        if hair_color:
            apply_named_node_color(head_mesh, cfg.materials.hair_color_node, hair_color, frame)

        lip_color = snapshot.get("lip_color")
        if lip_color:
            apply_named_node_color(head_mesh, cfg.materials.lip_color_node, lip_color, frame)

        # Restore texture overlays from snapshot
        overlays = snapshot.get("texture_overlays", {})
        if not overlays:
            self.report({"WARNING"}, "Snapshot has no texture_overlays — texture offsets unchanged")
        else:
            for slot in cfg.texture_swap.slots:
                name = overlays.get(slot.key)
                if name is None:
                    self.report({"WARNING"}, f"No texture overlay for '{slot.key}' in snapshot — skipping")
                    continue
                slot_manifest = load_manifest(slot.sequence_path)
                if slot_manifest is None:
                    self.report({"WARNING"}, f"No texture manifest for '{slot.key}' — skipping")
                    continue
                mat = bpy.data.materials.get(slot.material_name)
                if mat is None:
                    continue
                tex_offset = offset_from_name(name, frame, slot_manifest)
                if tex_offset is None:
                    self.report({"WARNING"}, f"Texture '{name}' not found in '{slot.key}' manifest — skipping")
                    continue
                key_sequence_offset(mat, slot.node_name, tex_offset, frame)

        src = Path(self.filepath).name
        self.report({"INFO"}, f"Loaded snapshot '{src}' on frame {frame}")
        return {"FINISHED"}

class SYNTHHEAD_OT_CleanMesh(bpy.types.Operator):
    """Combine eye wedges and body into the head mesh, sew the lips, and remove the mouth bag"""

    bl_idname = "synth_head.clean_mesh"
    bl_label = "Synth Head: Clean Mesh"
    bl_description = (
        "Sew lip borders, delete mouth bag, ingest eye wedges and body geo "
        "into the head mesh (preserving shape keys), then weld all seams"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        wedge_projection = get_flag(context, WEDGE_PROJECTION)
        cfg = _get_config()

        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        if wedge_projection:
            wedge_R = get_ref(context, EYE_WEDGE_R)
            if not wedge_R:
                self.report({"ERROR"}, "No eye wedge R stored — run Variation Pipeline first")
                return {"CANCELLED"}
            wedge_L = get_ref(context, EYE_WEDGE_L)
            if not wedge_L:
                self.report({"ERROR"}, "No eye wedge L stored — run Variation Pipeline first")
                return {"CANCELLED"}

        body = get_ref(context, BODY_GEO)
        if not body:
            self.report({"ERROR"}, "No body geo stored — run Variation Pipeline first")
            return {"CANCELLED"}

        if wedge_projection:
            copy_modifiers_to_wedges(head_mesh, wedge_R, wedge_L)
            clean_head_mesh_wedge(head_mesh, wedge_R, wedge_L, body, cfg.cleanup)
        else:
            Clean_head_mesh_Simple(head_mesh, body, cfg.cleanup)

        if wedge_projection:
            set_ref(context, MESH, wedge_R)
            set_ref(context, EYE_WEDGE_R, None)
            set_ref(context, EYE_WEDGE_L, None)
            set_ref(context, BODY_GEO, None)
            if len(wedge_R.material_slots) >= 2:
                wedge_R.active_material_index = 1
                with context.temp_override(object=wedge_R):
                    bpy.ops.object.material_slot_move(direction='UP')
        else:
            set_ref(context, BODY_GEO, None)

        self.report({"INFO"}, "Mesh cleaned: lips sewn, mouth bag removed, wedges and body merged")
        Path(cfg.runner.save_water_tight_blend_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_water_tight_blend_path)
        return {"FINISHED"}


def _ref_or_scene_object(
    context,
    key: str,
    scene_name: str,
) -> bpy.types.Object | None:
    """Return a pipeline ref, falling back to a scene object by name."""
    obj = get_ref(context, key)
    if obj is not None:
        return obj
    obj = bpy.data.objects.get(scene_name)
    if obj is not None:
        print(f"[Export] WARNING: {key!r} ref unset — using scene object {scene_name!r}")
    return obj


def _gather_export_refs(context) -> types.SimpleNamespace:
    """Collect all source-scene refs that the export pipeline needs.

    Returns a namespace with: head_geo, L_eye, R_eye, eyebrows, eyelashes,
    hd_eye_R, hd_eye_L, eye_boolean_L, eye_boolean_R.  Missing refs come
    through as None — staging_scene handles them based on the include_* flags
    in ExportConfig.  body_geo is deliberately omitted: it was sewn into
    head_geo during Clean Mesh.
    """
    return types.SimpleNamespace(
        head_geo=get_ref(context, MESH),
        body_geo=get_ref(context, BODY_GEO),
        L_eye=get_ref(context, L_EYE),
        R_eye=get_ref(context, R_EYE),
        eyebrows=get_ref(context, EYEBROWS),
        eyelashes=get_ref(context, EYELASHES),
        hd_eye_R=get_ref(context, HD_EYE_R),
        hd_eye_L=get_ref(context, HD_EYE_L),
        eye_boolean_L=_ref_or_scene_object(context, EYE_BOOLEAN_L, "eye_L_boolean"),
        eye_boolean_R=_ref_or_scene_object(context, EYE_BOOLEAN_R, "eye_R_boolean"),
    )


def _write_export_snapshot(
    context,
    cfg: PipelineConfig,
    out_dir: Path,
    frame: int,
    label: str = "final",
) -> Path | None:
    """Build + save a snapshot JSON for the current frame into *out_dir*.

    Mirrors the data captured by ``_save_head_snapshot`` but skips the attractor
    manifest update — the final-output folder is a handoff artifact, not a
    pool the attractor consumes.
    """
    armature = get_ref(context, ARMATURE)
    head_mesh = get_ref(context, MESH)
    if armature is None or head_mesh is None:
        return None

    joint_data = read_bone_transforms(armature, cfg.chaos_joint_names)
    var_shapes, expr_shapes = read_shape_key_values(
        head_mesh,
        cfg.blendshapes.variation_shapes + list(cfg.blendshapes.independent_shapes.keys()),
        cfg.blendshapes.expression_shapes,
    )
    bone_prop_data = read_bone_custom_props(armature, cfg.variation.bone_properties)
    skin_color = read_material_color(head_mesh)
    hair_color = read_named_node_color(head_mesh, cfg.materials.hair_color_node)
    lip_color = read_named_node_color(head_mesh, cfg.materials.lip_color_node)
    config_raw = _load_config_dir_raw(cfg)

    # Capture active texture overlay names from image sequence nodes
    texture_overlays: dict[str, str] = {}
    for slot in cfg.texture_swap.slots:
        slot_manifest = load_manifest(slot.sequence_path)
        mat = bpy.data.materials.get(slot.material_name)
        if slot_manifest is None or mat is None:
            continue
        offset = read_sequence_offset(mat, slot.node_name)
        if offset is None:
            continue
        texture_overlays[slot.key] = name_from_current_offset(offset, frame, slot_manifest)

    snapshot = build_snapshot(
        chaos_joints=joint_data,
        variation_shapes=var_shapes,
        expression_shapes=expr_shapes,
        bone_properties=bone_prop_data,
        config_snapshot=config_raw,
        frame=frame,
        label=label,
        note="",
        skin_color=skin_color,
        hair_color=hair_color,
        lip_color=lip_color,
        texture_overlays=texture_overlays if texture_overlays else None,
    )
    return save_snapshot(snapshot, out_dir)


class SYNTHHEAD_OT_ExportPipeline(bpy.types.Operator):
    """Run Pipeline 03 (Export): per-frame static GLB + baked diffuse textures + snapshot."""

    bl_idname = "synth_head.export_pipeline"
    bl_label = "Synth Head: Export Pipeline"
    bl_description = (
        "For every frame in the range: bake head_geo diffuse textures, freeze "
        "all enabled meshes, and export a self-contained static GLB into "
        "data/final-output/ with a snapshot JSON sidecar."
    )
    bl_options = {"REGISTER"}

    _timer = None
    _gen = None
    _frame_start: int = 0
    _frame_end: int = 0
    _out_dir: Path | None = None

    def invoke(self, context, event):
        cfg = _get_config()
        wedge_projection = get_flag(context, WEDGE_PROJECTION)
        refs = _gather_export_refs(context)

        if refs.head_geo is None:
            self.report({"ERROR"}, "No head mesh stored — run Variation Pipeline + Clean Mesh first")
            return {"CANCELLED"}

        if not cfg.runner.final_output_dir:
            self.report({"ERROR"}, "runner.final_output_dir is not configured")
            return {"CANCELLED"}

        out_dir = Path(cfg.runner.final_output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        fr = cfg.export.frame_range or (1, cfg.runner.frame_count)
        start, end = int(fr[0]), int(fr[1])
        self._frame_start = start
        self._frame_end = end
        self._out_dir = out_dir

        self.report({"INFO"}, f"Export pipeline: frames {start}..{end} → {out_dir}")

        self._gen = export_pipeline_generator(
            context,
            cfg,
            refs,
            wedge_projection=wedge_projection,
            out_dir=out_dir,
            start=start,
            end=end,
            write_snapshot=_write_export_snapshot,
        )

        try:
            next(self._gen)
        except StopIteration:
            self.report({"INFO"}, f"Exported {end - start + 1} frames → {out_dir}")
            return {"FINISHED"}

        wm = context.window_manager
        progress_props(context).cancel_requested = False
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        pg = context.window_manager.synth_head_export_progress

        if event.type == "ESC" and event.value == "PRESS":
            pg.cancel_requested = True
            pg.phase = "Cancelling after current step…"
            overlay_refresh(context)
            return {"RUNNING_MODAL"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        try:
            next(self._gen)
        except StopIteration:
            self._stop_timer(context)
            if pg.cancel_requested:
                self.report({"WARNING"}, "Export cancelled")
                return {"CANCELLED"}
            n = self._frame_end - self._frame_start + 1
            self.report({"INFO"}, f"Exported {n} frames → {self._out_dir}")
            return {"FINISHED"}

        overlay_refresh(context)
        return {"RUNNING_MODAL"}

    def _stop_timer(self, context) -> None:
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def execute(self, context):
        return self.invoke(context, None)


class SYNTHHEAD_OT_LoadEyeBakeSettings(bpy.types.Operator):
    """Apply eye-bake-settings from projection.json to the current scene"""

    bl_idname = "synth_head.load_eye_bake_settings"
    bl_label = "Synth Head: Load Eye Bake Settings"
    bl_description = "Read eye-bake-settings from projection.json and apply them to the current scene's bake properties"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()
        apply_bake_settings(context.scene, cfg.projection.eye_bake_settings)
        self.report({"INFO"}, "Eye bake settings applied from projection.json")
        return {"FINISHED"}

def _eye_bake_png(frame: int, side: str) -> Path:
    """Return the filename (not full path) for one frame's eye-bake PNG."""
    return Path(f"frame_{frame:04d}_{side}_eye_wedge_diffuse.png")


class SYNTHHEAD_OT_BakeEyes(bpy.types.Operator):
    """Per-frame eye bake: bake both wedges across the frame range and wire image sequences."""

    bl_idname = "synth_head.bake_eyes"
    bl_label = "Synth Head: Bake Eyes"
    bl_description = (
        "For every frame in the range: bake eye textures from the projection "
        "source to both eye wedges, write PNGs to disk, then wire the baked "
        "image sequences back into each wedge's material."
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        cfg = _get_config()

        bake_R = get_ref(context, EYE_WEDGE_R_BAKE)
        bake_L = get_ref(context, EYE_WEDGE_L_BAKE)
        wedge_R = get_ref(context, EYE_WEDGE_R)
        wedge_L = get_ref(context, EYE_WEDGE_L)

        missing = []
        if bake_R is None:  missing.append("EYE_WEDGE_R_BAKE")
        if bake_L is None:  missing.append("EYE_WEDGE_L_BAKE")
        if wedge_R is None: missing.append("EYE_WEDGE_R")
        if wedge_L is None: missing.append("EYE_WEDGE_L")
        if missing:
            self.report({"ERROR"}, f"Missing scene refs: {', '.join(missing)}")
            return {"CANCELLED"}

        apply_bake_settings(context.scene, cfg.projection.eye_bake_settings)

        out_dir_R = Path(cfg.projection.baked_sequence_R_path)
        out_dir_L = Path(cfg.projection.baked_sequence_L_path)
        out_dir_R.mkdir(parents=True, exist_ok=True)
        out_dir_L.mkdir(parents=True, exist_ok=True)

        fr = cfg.export.frame_range or (1, cfg.runner.frame_count)
        start, end = int(fr[0]), int(fr[1])
        resolution = cfg.export.eye_wedge_bake_resolution
        diffuse_node = cfg.projection.eye_bake_diffuse_name

        self.report({"INFO"}, f"Eye bake: frames {start}..{end} → R: {out_dir_R}, L: {out_dir_L}")

        for frame in range(start, end + 1):
            context.scene.frame_set(frame)

            bake_wedge_side(
                context, bake_R, diffuse_node,
                out_dir_R / _eye_bake_png(frame, "R"), resolution,
                cfg.projection.eye_bake_settings,
            )
            bake_wedge_side(
                context, bake_L, diffuse_node,
                out_dir_L / _eye_bake_png(frame, "L"), resolution,
                cfg.projection.eye_bake_settings,
            )

            print(f"[SynthHead][BakeEyes] frame {frame}/{end} done")

        frame_count = end - start + 1
        point_image_sequence_node(
            wedge_R, cfg.projection.eye_baked_sequence_name,
            out_dir_R / _eye_bake_png(start, "R"), start, frame_count,
        )
        point_image_sequence_node(
            wedge_L, cfg.projection.eye_baked_sequence_name,
            out_dir_L / _eye_bake_png(start, "L"), start, frame_count,
        )

        #cleanup
        #hide bake wedges
        bake_R.hide_set(True)
        bake_L.hide_set(True)
        #reveal wedges
        wedge_R.hide_set(False)
        wedge_L.hide_set(False)

        #save blend file
        Path(cfg.runner.save_eye_bake_blend_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_eye_bake_blend_path)

        Path(cfg.runner.save_variation_blend_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_variation_blend_path)
 
        self.report({"INFO"}, f"Eye bake complete: {frame_count} frames per side")
        return {"FINISHED"}


class SYNTHHEAD_OT_RebakeEyeFrame(bpy.types.Operator):
    """Re-bake eye wedge textures for the current frame only"""

    bl_idname = "synth_head.rebake_eye_frame"
    bl_label = "Synth Head: Rebake Eye Frame"
    bl_description = (
        "Bake eye textures from the projection source to both wedges "
        "on the current frame only, writing the PNGs to disk."
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        cfg = _get_config()

        bake_R = get_ref(context, EYE_WEDGE_R_BAKE)
        bake_L = get_ref(context, EYE_WEDGE_L_BAKE)

        missing = []
        if bake_R is None: missing.append("EYE_WEDGE_R_BAKE")
        if bake_L is None: missing.append("EYE_WEDGE_L_BAKE")
        if missing:
            self.report({"ERROR"}, f"Missing scene refs: {', '.join(missing)}")
            return {"CANCELLED"}

        apply_bake_settings(context.scene, cfg.projection.eye_bake_settings)

        out_dir_R = Path(cfg.projection.baked_sequence_R_path)
        out_dir_L = Path(cfg.projection.baked_sequence_L_path)
        out_dir_R.mkdir(parents=True, exist_ok=True)
        out_dir_L.mkdir(parents=True, exist_ok=True)

        resolution = cfg.export.eye_wedge_bake_resolution
        diffuse_node = cfg.projection.eye_bake_diffuse_name
        frame = context.scene.frame_current

        bake_wedge_side(
            context, bake_R, diffuse_node,
            out_dir_R / _eye_bake_png(frame, "R"), resolution,
            cfg.projection.eye_bake_settings,
        )
        bake_wedge_side(
            context, bake_L, diffuse_node,
            out_dir_L / _eye_bake_png(frame, "L"), resolution,
            cfg.projection.eye_bake_settings,
        )

        self.report({"INFO"}, f"Eye rebake complete for frame {frame}")
        return {"FINISHED"}


class SYNTHHEAD_MT_main_menu(bpy.types.Menu):
    bl_idname = "SYNTHHEAD_MT_main_menu"
    bl_label = "Synth Head"

    def draw(self, _context):
        layout = self.layout
        layout.operator(SYNTHHEAD_OT_hello.bl_idname)
        layout.operator(SYNTHHEAD_OT_ping.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_BatchConversion.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_VariationPipeline.bl_idname)
        layout.operator(SYNTHHEAD_OT_CleanMesh.bl_idname)
        layout.operator(SYNTHHEAD_OT_ExportPipeline.bl_idname)
        layout.operator(SYNTHHEAD_OT_RandomizeFace.bl_idname)
        layout.operator(SYNTHHEAD_OT_RerandomizeSelected.bl_idname)
        layout.operator(SYNTHHEAD_OT_RerandomizeSelectedFrame.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_SaveHeadIssue.bl_idname)
        layout.operator(SYNTHHEAD_OT_SaveGoodHead.bl_idname)
        layout.operator(SYNTHHEAD_OT_SaveHeadAttractive.bl_idname)
        layout.operator(SYNTHHEAD_OT_LoadHeadData.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_LoadEyeBakeSettings.bl_idname)
        layout.operator(SYNTHHEAD_OT_BakeEyes.bl_idname)
        layout.operator(SYNTHHEAD_OT_RebakeEyeFrame.bl_idname)


def _draw_menu(self, _context):
    self.layout.menu(SYNTHHEAD_MT_main_menu.bl_idname)


CLASSES = [
    SYNTHHEAD_PG_PipelineRefs,
    SYNTHHEAD_PG_ExportProgress,
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_BatchConversion,
    SYNTHHEAD_OT_VariationPipeline,
    SYNTHHEAD_OT_CleanMesh,
    SYNTHHEAD_OT_ExportPipeline,
    SYNTHHEAD_OT_RandomizeFace,
    SYNTHHEAD_OT_RerandomizeSelected,
    SYNTHHEAD_OT_RerandomizeSelectedFrame,
    SYNTHHEAD_OT_SaveHeadIssue,
    SYNTHHEAD_OT_SaveGoodHead,
    SYNTHHEAD_OT_SaveHeadAttractive,
    SYNTHHEAD_OT_LoadHeadData,
    SYNTHHEAD_OT_LoadEyeBakeSettings,
    SYNTHHEAD_OT_BakeEyes,
    SYNTHHEAD_OT_RebakeEyeFrame,
    SYNTHHEAD_MT_main_menu,
]

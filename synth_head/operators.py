"""
Thin Blender operator layer for Synth Head.

Operators here delegate to scene/ and core/ — no business logic lives here.
"""

import bpy
from pathlib import Path

from .core.math import clamp
from .core.ref_keys import MESH, BODY_GEO, ARMATURE, HEAD_MAT, L_EYE, R_EYE, EYEBROWS, EYELASHES, EYE_MAT, EYE_WEDGE_R, EYE_WEDGE_L, EYE_WEDGE_R_BAKE, EYE_WEDGE_L_BAKE, HD_EYE_R, HD_EYE_L, R_PROJECTOR, L_PROJECTOR
from .core.variation import (
    generate_chaos_transforms,
    generate_single_frame_transforms,
)
from .scene.fbx_import import import_fbx_and_classify
from .scene.refs import get_ref, set_ref, get_material_ref, set_material_ref
from .core.blendshapes import (
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
)
from .core.constraints import flatten_params, unflatten_params, constrain
from .core.attractor import get_pool_cache, attract, update_manifest
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
)
from .scene.armature import add_object_to_armature, remove_orphan_armatures
from .scene.blend_append import append_material_from_blend, append_object_from_blend, append_gen13_and_classify, append_eye_wedge_bake
from .scene.materials import assign_exclusive_material, randomize_head_material_color, read_material_color, apply_attractive_color
from .scene.modifiers import add_smooth_corrective
from .scene.reset import reset_frame
from .scene.mesh import clean_head_mesh
from .scene.snapshot import (
    read_bone_transforms,
    read_shape_key_values,
    apply_bone_transforms,
    apply_shape_key_values,
    apply_material_color,
)
from .scene.export_bake import scope_bake_environment, bake_head_materials
from .scene.projection import apply_bake_settings
from .scene.export_glb import staging_scene, rewrite_head_material_slots, stamp_frame_names, export_glb
from .core.export import frame_glb_name, frame_dir_name
from .core.snapshot import build_snapshot, save_snapshot, load_snapshot
from .core.config import load_config, PipelineConfig

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
    p(f"  include_eyes:              {cfg.export.include_eyes}")
    p(f"  include_brows:             {cfg.export.include_brows}")
    p(f"  include_lashes:            {cfg.export.include_lashes}")

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
        p(f"    {k}: min={v.min}  max={v.max}")
    p(f"  relational_rules ({len(cfg.constraints.relational_rules)}):")
    for r in cfg.constraints.relational_rules:
        p(f"    {r}")

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

    p(f"--- ATTRACTOR ---")
    p(f"  enabled:              {cfg.attractor.enabled}")
    p(f"  debug:                {cfg.attractor.debug}")
    p(f"  attractive_heads_dir: {cfg.attractor.attractive_heads_dir}")
    p(f"  min_attractors:       {cfg.attractor.min_attractors}")
    p(f"  max_attractors:   {cfg.attractor.max_attractors}")
    p(f"  max_influence:    {cfg.attractor.max_influence}")
    p(f"  distance_weights: {cfg.attractor.distance_weights}")
    p(f"  exclude_params:   {cfg.attractor.exclude_params}")

    p(f"--- CLEANUP ---")
    p(f"  assets_blend_path: {cfg.cleanup.assets_blend_path}")
    p(f"  eye_wedge_R_name: {cfg.cleanup.eye_wedge_R_name}")
    p(f"  eye_wedge_L_name: {cfg.cleanup.eye_wedge_L_name}")
    p(f"  mouth_bag_group: {cfg.cleanup.mouth_bag_group}")
    p(f"  mouth_sew_indices: {cfg.cleanup.mouth_sew_indices}")
    # p(f"  eye_wedge_R_indices: {cfg.cleanup.eye_wedge_R_indices}")
    # p(f"  eye_wedge_L_indices: {cfg.cleanup.eye_wedge_L_indices}")


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


class SYNTHHEAD_OT_VariationPipeline(bpy.types.Operator):
    """Run the variation pipeline"""

    bl_idname = "synth_head.variation_pipeline"
    bl_label = "Synth Head: Variation Pipeline"
    bl_description = "Run the variation pipeline"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cfg = _get_config()
        # --- 1. IMPORT & VALIDATE ---
        # head_geo_obj, body_geo_obj, armature_obj, L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj = import_fbx_and_classify(
        #     context, cfg.runner.fbx_path,
        # )

        head_geo_obj, body_geo_obj, armature_obj, L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj  = append_gen13_and_classify(cfg.runner.gen13_blend_path)


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
            


        # set the head mesh and armature references
        set_ref(context, MESH, head_geo_obj)
        set_ref(context, BODY_GEO, body_geo_obj)    
        set_ref(context, ARMATURE, armature_obj)
        set_ref(context, L_EYE, L_eye_obj)
        set_ref(context, R_EYE, R_eye_obj)
        set_ref(context, EYEBROWS, eyebrows_obj)
        set_ref(context, EYELASHES, eyelashes_obj)
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
        
        # --- 2. CLEANUP PREP---
        
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
        add_object_to_armature(R_projector, armature_obj)
        add_object_to_armature(L_projector, armature_obj)
        remove_orphan_armatures()

        
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

        import random as _random
        attractor_rng = _random.Random(cfg.runner.seed)
        # --- 5. CONSTRAIN EACH FRAME (attract → constrain → split) ---
        constrained_transforms: dict[int, dict] = {}
        constrained_bs: dict[int, dict[str, float]] = {}
        attractive_colors: dict[int, list[float] | None] = {}
        fc = cfg.runner.frame_count
        for frame in range(1, fc + 1):
            # flat is a dict of param names to values
            flat = flatten_params(all_transforms[frame], all_bs_weights[frame])
            # attract nudges the flat params toward the attractor pool and returns
            # an attractive color blended from the same pool heads and weights
            flat, attractive_color, dbg = attract(flat, pool, cfg.attractor, cfg.variation, cfg.blendshapes, attractor_rng)
            attractive_colors[frame] = attractive_color
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
        # --- 6. BAKE TO SCENE (pose bones + shape keys + material color per frame) ---
        color_rng = _random.Random(cfg.runner.seed + 1 if cfg.runner.seed is not None else None)
        for frame in range(1, fc + 1):
            context.scene.frame_set(frame)
            reset_frame(chaos_joints, [head_mesh, eye_wedge_R_obj, eye_wedge_L_obj, eyebrows_obj, eyelashes_obj], frame)
            #Core Head Parts
            _apply_transforms_to_bones(chaos_joints, constrained_transforms[frame], frame)
            _apply_weights_to_shape_keys(head_mesh, constrained_bs[frame], frame)
            #Eye Wedge Parts
            _apply_weights_to_shape_keys(eye_wedge_R_obj, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(eye_wedge_L_obj, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(eye_wedge_R_bake, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(eye_wedge_L_bake, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(R_projector, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(L_projector, constrained_bs[frame], frame)

            #Eyebrows and Eyelashes
            _apply_weights_to_shape_keys(eyebrows_obj, constrained_bs[frame], frame)
            _apply_weights_to_shape_keys(eyelashes_obj, constrained_bs[frame], frame)
            #Material Color
            rng_color = (color_rng.random(), color_rng.random(), color_rng.random(), 1.0)
            randomize_head_material_color(head_mesh, rng_color, frame)
            attr_color = attractive_colors[frame]
            if attr_color is not None:
                apply_attractive_color(head_mesh, attr_color, rng_color, cfg.materials.final_color_randomness, frame)
        self.report({"INFO"}, f"Applied {fc} frames (reset + joints + blendshapes + material color)")
        # --- 7. cleanup

        
        # --- 7. POST-PROCESS & SAVE --
        #add_smooth_corrective(head_mesh, cfg.modifiers)



        eyebrows_obj.hide_viewport = True
        eyelashes_obj.hide_viewport = True

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
        armature = get_ref(context, ARMATURE)
        if not armature:
            self.report({"ERROR"}, "No armature stored — run Variation Pipeline first")
            return {"CANCELLED"}

        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        eye_wedge_R_obj = get_ref(context, EYE_WEDGE_R)
        if not eye_wedge_R_obj:
            self.report({"ERROR"}, "No eye wedge R mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}
        eye_wedge_L_obj = get_ref(context, EYE_WEDGE_L)
        if not eye_wedge_L_obj:
            self.report({"ERROR"}, "No eye wedge L mesh stored — run Variation Pipeline first")
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

        cfg = _get_config()

        chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)
        if not chaos_joints:
            self.report({"ERROR"}, "No chaos joints found on armature")
            return {"CANCELLED"}

        joint_names = [b.name for b in chaos_joints]
        transforms = generate_single_frame_transforms(cfg.variation, joint_names)
        bs_weights = generate_single_frame_blendshape_weights(cfg.blendshapes)

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
        flat, attractive_color, dbg = attract(flat, pool, cfg.attractor, cfg.variation, cfg.blendshapes, attractor_rng)
        if dbg is not None:
            print(f"[SynthHead][Attractor] RandomizeFace: "
                  f"n={dbg['n_selected']}  "
                  f"mean_delta={dbg['mean_abs_delta']:.5f}  "
                  f"files={[f.replace('good_frame', 'f') for f in dbg['selected_files']]}")
        flat = constrain(flat, cfg.constraints)
        transforms, bs_weights = unflatten_params(flat, joint_names)

        frame = context.scene.frame_current

        reset_frame(chaos_joints, [head_mesh, eye_wedge_R_obj, eye_wedge_L_obj, eyebrows_obj, eyelashes_obj], frame)
        _apply_transforms_to_bones(chaos_joints, transforms, frame)
        _apply_weights_to_shape_keys(head_mesh, bs_weights, frame)
        _apply_weights_to_shape_keys(eye_wedge_R_obj, bs_weights, frame)
        _apply_weights_to_shape_keys(eye_wedge_L_obj, bs_weights, frame)
        _apply_weights_to_shape_keys(eyebrows_obj, bs_weights, frame)
        _apply_weights_to_shape_keys(eyelashes_obj, bs_weights, frame)

        rng_color = (attractor_rng.random(), attractor_rng.random(), attractor_rng.random(), 1.0)
        randomize_head_material_color(head_mesh, rng_color, frame)
        if attractive_color is not None:
            apply_attractive_color(head_mesh, attractive_color, rng_color, cfg.materials.final_color_randomness, frame)

        self.report({"INFO"}, f"Randomized {len(chaos_joints)} joints + blendshapes on frame {frame}")
        return {"FINISHED"}


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
        cfg.blendshapes.variation_shapes,
        cfg.blendshapes.expression_shapes,
    )
    skin_color = read_material_color(head_mesh)

    config_raw = _load_config_dir_raw(cfg)

    snapshot = build_snapshot(
        chaos_joints=joint_data,
        variation_shapes=var_shapes,
        expression_shapes=expr_shapes,
        config_snapshot=config_raw,
        frame=context.scene.frame_current,
        label=label,
        note=operator.note,
        skin_color=skin_color,
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
        armature = get_ref(context, ARMATURE)
        if not armature:
            self.report({"ERROR"}, "No armature stored — run Variation Pipeline first")
            return {"CANCELLED"}

        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

        cfg = _get_config()
        snapshot = load_snapshot(self.filepath)
        frame = context.scene.frame_current

        chaos_joints = collect_chaos_joints(armature, cfg.chaos_joint_names)

        reset_frame(chaos_joints, head_mesh, frame)
        apply_bone_transforms(armature, snapshot.get("chaos_joints", {}), frame)

        all_shapes: dict[str, float] = {}
        all_shapes.update(snapshot.get("variation_shapes", {}))
        all_shapes.update(snapshot.get("expression_shapes", {}))
        apply_shape_key_values(head_mesh, all_shapes, frame)

        skin_color = snapshot.get("skin_color")
        if skin_color is not None:
            apply_material_color(head_mesh, skin_color, frame)

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
        head_mesh = get_ref(context, MESH)
        if not head_mesh:
            self.report({"ERROR"}, "No mesh stored — run Variation Pipeline first")
            return {"CANCELLED"}

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

        cfg = _get_config()

        clean_head_mesh(head_mesh, wedge_R, wedge_L, body, cfg.cleanup)

        # Clear refs for the objects that were deleted by clean_head_mesh
        set_ref(context, EYE_WEDGE_R, None)
        set_ref(context, EYE_WEDGE_L, None)
        set_ref(context, BODY_GEO, None)

        self.report({"INFO"}, "Mesh cleaned: lips sewn, mouth bag removed, wedges and body merged")
        Path(cfg.runner.save_water_tight_blend_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_water_tight_blend_path)
        return {"FINISHED"}


def _gather_export_refs(context) -> types.SimpleNamespace:
    """Collect all source-scene refs that the export pipeline needs.

    Returns a namespace with: head_geo, L_eye, R_eye, eyebrows, eyelashes.
    Missing refs come through as None — staging_scene handles them based on
    the include_* flags in ExportConfig.  body_geo is deliberately omitted:
    it was sewn into head_geo during Clean Mesh and no longer exists as a
    standalone object.
    """
    return types.SimpleNamespace(
        head_geo=get_ref(context, MESH),
        L_eye=get_ref(context, L_EYE),
        R_eye=get_ref(context, R_EYE),
        eyebrows=get_ref(context, EYEBROWS),
        eyelashes=get_ref(context, EYELASHES),
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
        cfg.blendshapes.variation_shapes,
        cfg.blendshapes.expression_shapes,
    )
    skin_color = read_material_color(head_mesh)
    config_raw = _load_config_dir_raw(cfg)

    snapshot = build_snapshot(
        chaos_joints=joint_data,
        variation_shapes=var_shapes,
        expression_shapes=expr_shapes,
        config_snapshot=config_raw,
        frame=frame,
        label=label,
        note="",
        skin_color=skin_color,
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

    def execute(self, context):
        cfg = _get_config()
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

        self.report({"INFO"}, f"Export pipeline: frames {start}..{end} → {out_dir}")

        with scope_bake_environment(refs.head_geo, cfg.export) as bake_ctx:
            for frame in range(start, end + 1):
                context.scene.frame_set(frame)

                # Every artifact for this frame (GLB, snapshot, PNGs) lives
                # in the same per-frame folder.
                frame_dir = out_dir / frame_dir_name(frame)
                frame_dir.mkdir(parents=True, exist_ok=True)

                png_paths = bake_head_materials(
                    refs.head_geo,
                    bake_ctx,
                    frame_dir=frame_dir,
                    samples=cfg.export.bake_samples,
                    margin=cfg.export.bake_margin,
                )

                with staging_scene(refs, cfg.export) as stage:
                    rewrite_head_material_slots(stage.head_geo, png_paths)
                    stamp_frame_names(stage.objects, frame)
                    export_glb(
                        stage.objects,
                        frame_dir / frame_glb_name(frame),
                        format=cfg.export.glb_format,
                    )

                _write_export_snapshot(context, cfg, frame_dir, frame, label="final")

                print(f"[SynthHead][Export] frame {frame}/{end} done")

        if cfg.runner.save_export_blend_path:
            Path(cfg.runner.save_export_blend_path).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_export_blend_path)

        self.report({"INFO"}, f"Exported {end - start + 1} frames → {out_dir}")
        return {"FINISHED"}


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


class SYNTHHEAD_MT_main_menu(bpy.types.Menu):
    bl_idname = "SYNTHHEAD_MT_main_menu"
    bl_label = "Synth Head"

    def draw(self, _context):
        layout = self.layout
        layout.operator(SYNTHHEAD_OT_hello.bl_idname)
        layout.operator(SYNTHHEAD_OT_ping.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_VariationPipeline.bl_idname)
        layout.operator(SYNTHHEAD_OT_CleanMesh.bl_idname)
        layout.operator(SYNTHHEAD_OT_ExportPipeline.bl_idname)
        layout.operator(SYNTHHEAD_OT_RandomizeFace.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_SaveHeadIssue.bl_idname)
        layout.operator(SYNTHHEAD_OT_SaveGoodHead.bl_idname)
        layout.operator(SYNTHHEAD_OT_SaveHeadAttractive.bl_idname)
        layout.operator(SYNTHHEAD_OT_LoadHeadData.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_LoadEyeBakeSettings.bl_idname)


def _draw_menu(self, _context):
    self.layout.menu(SYNTHHEAD_MT_main_menu.bl_idname)


CLASSES = [
    SYNTHHEAD_PG_PipelineRefs,
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
    SYNTHHEAD_OT_CleanMesh,
    SYNTHHEAD_OT_ExportPipeline,
    SYNTHHEAD_OT_RandomizeFace,
    SYNTHHEAD_OT_SaveHeadIssue,
    SYNTHHEAD_OT_SaveGoodHead,
    SYNTHHEAD_OT_SaveHeadAttractive,
    SYNTHHEAD_OT_LoadHeadData,
    SYNTHHEAD_OT_LoadEyeBakeSettings,
    SYNTHHEAD_MT_main_menu,
]

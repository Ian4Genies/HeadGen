"""
Thin Blender operator layer for Synth Head.

Operators here delegate to scene/ and core/ — no business logic lives here.
"""

import bpy

from .core.math import clamp
from .core.ref_keys import MESH, ARMATURE
from .core.variation import (
    CHAOS_JOINT_NAMES,
    VariationConfig,
    generate_chaos_transforms,
    generate_single_frame_transforms,
)
from .scene.fbx_import import import_fbx_and_classify
from .scene.refs import get_ref, set_ref
from .core.blendshapes import (
    BlendshapeConfig,
    generate_blendshape_weights,
    generate_single_frame_blendshape_weights,
)
from .core.constraints import load_rules, flatten_params, unflatten_params, constrain
from .core.modifiers import SmoothCorrectiveConfig
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
from .scene.modifiers import add_smooth_corrective
from .scene.reset import reset_frame
from .scene.snapshot import (
    read_bone_transforms,
    read_shape_key_values,
    apply_bone_transforms,
    apply_shape_key_values,
)
from .core.snapshot import build_snapshot, save_snapshot, load_snapshot
from .core.blendshapes import VARIATION_SHAPES, EXPRESSION_SHAPES

import json
from pathlib import Path

_FBX_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/genericGenie-0013-unified_rig.fbx"
_SAVE_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/gen13_genie_chaos.blend"
_RULES_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/constraint_rules.json"
_DATA_DIR = Path("C:/Genies/01_Repo/02_Blender/HeadGen/data")
_ISSUES_DIR = _DATA_DIR / "head-issues"
_GOOD_DIR = _DATA_DIR / "head-good"


class SYNTHHEAD_PG_PipelineRefs(bpy.types.PropertyGroup):
    """Live object references managed by the variation pipeline.

    To add a new reference: add a PointerProperty here and a matching
    constant in core/ref_keys.py.  scene/refs.py needs no changes.
    """

    mesh: bpy.props.PointerProperty(
        name="Head Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    armature: bpy.props.PointerProperty(
        name="Armature",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
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
        head_geo_obj, armature_obj = import_fbx_and_classify(context, _FBX_PATH)

        if not head_geo_obj:
            self.report({"ERROR"}, "headOnly_geo mesh not found in FBX — aborting")
            return {"CANCELLED"}

        if not armature_obj:
            self.report({"ERROR"}, "Armature not found in FBX — aborting")
            return {"CANCELLED"}

        set_ref(context, MESH, head_geo_obj)
        set_ref(context, ARMATURE, armature_obj)
        self.report({"INFO"}, f"head geo: '{head_geo_obj.name}'")

        armature = get_ref(context, ARMATURE)
        chaos_joints = collect_chaos_joints(armature, CHAOS_JOINT_NAMES)
        self.report({"INFO"}, f"Chaos joints found: {[b.name for b in chaos_joints]}")

        chaos_config = VariationConfig()
        joint_names = [b.name for b in chaos_joints]
        all_transforms = generate_chaos_transforms(chaos_config, joint_names)

        head_mesh = get_ref(context, MESH)
        bs_config = BlendshapeConfig(frame_count=chaos_config.frame_count)
        all_bs_weights = generate_blendshape_weights(bs_config)

        rules = load_rules(_RULES_PATH)
        constrained_transforms: dict[int, dict] = {}
        constrained_bs: dict[int, dict[str, float]] = {}
        for frame in range(1, chaos_config.frame_count + 1):
            flat = flatten_params(all_transforms[frame], all_bs_weights[frame])
            flat = constrain(flat, rules)
            xforms, weights = unflatten_params(flat, joint_names)
            constrained_transforms[frame] = xforms
            constrained_bs[frame] = weights

        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        for frame in range(1, chaos_config.frame_count + 1):
            context.scene.frame_set(frame)
            reset_frame(chaos_joints, head_mesh, frame)
            _apply_transforms_to_bones(chaos_joints, constrained_transforms[frame], frame)
            _apply_weights_to_shape_keys(head_mesh, constrained_bs[frame], frame)

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, f"Applied {chaos_config.frame_count} frames (reset + joints + blendshapes)")

        add_smooth_corrective(head_mesh, SmoothCorrectiveConfig())

        bpy.ops.wm.save_as_mainfile(filepath=_SAVE_PATH)
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

        chaos_joints = collect_chaos_joints(armature, CHAOS_JOINT_NAMES)
        if not chaos_joints:
            self.report({"ERROR"}, "No chaos joints found on armature")
            return {"CANCELLED"}

        chaos_config = VariationConfig()
        joint_names = [b.name for b in chaos_joints]
        transforms = generate_single_frame_transforms(chaos_config, joint_names)

        bs_config = BlendshapeConfig()
        bs_weights = generate_single_frame_blendshape_weights(bs_config)

        rules = load_rules(_RULES_PATH)
        flat = flatten_params(transforms, bs_weights)
        flat = constrain(flat, rules)
        transforms, bs_weights = unflatten_params(flat, joint_names)

        frame = context.scene.frame_current
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        reset_frame(chaos_joints, head_mesh, frame)
        _apply_transforms_to_bones(chaos_joints, transforms, frame)
        _apply_weights_to_shape_keys(head_mesh, bs_weights, frame)

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, f"Randomized {len(chaos_joints)} joints + blendshapes on frame {frame}")
        return {"FINISHED"}


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

    joint_data = read_bone_transforms(armature, CHAOS_JOINT_NAMES)
    var_shapes, expr_shapes = read_shape_key_values(
        head_mesh, list(VARIATION_SHAPES), list(EXPRESSION_SHAPES),
    )

    rules_raw: dict = {}
    rules_path = Path(_RULES_PATH)
    if rules_path.exists():
        with rules_path.open("r", encoding="utf-8") as f:
            rules_raw = json.load(f)

    snapshot = build_snapshot(
        chaos_joints=joint_data,
        variation_shapes=var_shapes,
        expression_shapes=expr_shapes,
        rules_raw=rules_raw,
        frame=context.scene.frame_current,
        label=label,
        note=operator.note,
    )

    saved = save_snapshot(snapshot, directory)
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
        return _save_head_snapshot(self, context, "issue", _ISSUES_DIR)


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
        return _save_head_snapshot(self, context, "good", _GOOD_DIR)


class SYNTHHEAD_OT_LoadHeadData(bpy.types.Operator):
    """Load a saved head snapshot and apply it on the current frame"""

    bl_idname = "synth_head.load_head_data"
    bl_label = "Synth Head: Load Head Data"
    bl_description = "Load a snapshot JSON and apply transforms + shape keys"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        self.filepath = str(_DATA_DIR) + "\\"
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

        snapshot = load_snapshot(self.filepath)
        frame = context.scene.frame_current

        chaos_joints = collect_chaos_joints(armature, CHAOS_JOINT_NAMES)

        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        reset_frame(chaos_joints, head_mesh, frame)
        apply_bone_transforms(armature, snapshot.get("chaos_joints", {}), frame)

        all_shapes: dict[str, float] = {}
        all_shapes.update(snapshot.get("variation_shapes", {}))
        all_shapes.update(snapshot.get("expression_shapes", {}))
        apply_shape_key_values(head_mesh, all_shapes, frame)

        bpy.ops.object.mode_set(mode="OBJECT")

        src = Path(self.filepath).name
        self.report({"INFO"}, f"Loaded snapshot '{src}' on frame {frame}")
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
        layout.operator(SYNTHHEAD_OT_RandomizeFace.bl_idname)
        layout.separator()
        layout.operator(SYNTHHEAD_OT_SaveHeadIssue.bl_idname)
        layout.operator(SYNTHHEAD_OT_SaveGoodHead.bl_idname)
        layout.operator(SYNTHHEAD_OT_LoadHeadData.bl_idname)


def _draw_menu(self, _context):
    self.layout.menu(SYNTHHEAD_MT_main_menu.bl_idname)


CLASSES = [
    SYNTHHEAD_PG_PipelineRefs,
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
    SYNTHHEAD_OT_RandomizeFace,
    SYNTHHEAD_OT_SaveHeadIssue,
    SYNTHHEAD_OT_SaveGoodHead,
    SYNTHHEAD_OT_LoadHeadData,
    SYNTHHEAD_MT_main_menu,
]

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
from .scene.blendshapes import apply_blendshape_keyframes, apply_blendshape_single_frame
from .scene.chaos_anim import collect_chaos_joints, apply_chaos_keyframes, apply_chaos_single_frame
from .scene.modifiers import add_smooth_corrective

_FBX_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/genericGenie-0013-unified_rig.fbx"
_SAVE_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/gen13_genie_chaos.blend"
_RULES_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/constraint_rules.json"


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

        apply_chaos_keyframes(context, armature, chaos_joints, constrained_transforms)
        apply_blendshape_keyframes(context, head_mesh, constrained_bs)
        self.report({"INFO"}, f"Blendshape keys applied for {bs_config.frame_count} frames")

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

        apply_chaos_single_frame(context, armature, chaos_joints, transforms)
        apply_blendshape_single_frame(context, head_mesh, bs_weights)

        frame = context.scene.frame_current
        self.report({"INFO"}, f"Randomized {len(chaos_joints)} joints + blendshapes on frame {frame}")
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


def _draw_menu(self, _context):
    self.layout.menu(SYNTHHEAD_MT_main_menu.bl_idname)


CLASSES = [
    SYNTHHEAD_PG_PipelineRefs,
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
    SYNTHHEAD_OT_RandomizeFace,
    SYNTHHEAD_MT_main_menu,
]

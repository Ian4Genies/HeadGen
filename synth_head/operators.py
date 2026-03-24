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
from .core.modifiers import SmoothCorrectiveConfig
from .scene.chaos_anim import collect_chaos_joints, apply_chaos_keyframes, apply_chaos_single_frame
from .scene.modifiers import add_smooth_corrective

_FBX_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/genericGenie-0013-unified_rig.fbx"
_SAVE_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/gen13_genie_chaos.blend"


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

        config = VariationConfig()
        transforms = generate_chaos_transforms(config, [b.name for b in chaos_joints])
        apply_chaos_keyframes(context, armature, chaos_joints, transforms)

        add_smooth_corrective(get_ref(context, MESH), SmoothCorrectiveConfig())

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

        chaos_joints = collect_chaos_joints(armature, CHAOS_JOINT_NAMES)
        if not chaos_joints:
            self.report({"ERROR"}, "No chaos joints found on armature")
            return {"CANCELLED"}

        config = VariationConfig()
        transforms = generate_single_frame_transforms(
            config, [b.name for b in chaos_joints],
        )
        apply_chaos_single_frame(context, armature, chaos_joints, transforms)

        frame = context.scene.frame_current
        self.report({"INFO"}, f"Randomized {len(chaos_joints)} joints on frame {frame}")
        return {"FINISHED"}


CLASSES = [
    SYNTHHEAD_PG_PipelineRefs,
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
    SYNTHHEAD_OT_RandomizeFace,
]

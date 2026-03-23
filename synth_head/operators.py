"""
Thin Blender operator layer for Synth Head.

Operators here delegate to scene/ and core/ — no business logic lives here.
"""

import bpy

from .core.math import clamp
from .core.variation import CHAOS_JOINT_NAMES, VariationConfig, generate_chaos_transforms
from .scene.fbx_import import import_fbx_and_classify
from .core.modifiers import SmoothCorrectiveConfig
from .scene.chaos_anim import collect_chaos_joints, apply_chaos_keyframes
from .scene.modifiers import add_smooth_corrective

_FBX_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/genericGenie-0013-unified_rig.fbx"
_SAVE_PATH = "C:/Genies/01_Repo/02_Blender/HeadGen/data/gen13_genie_chaos.blend"


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
        head_geo_name, armature_name = import_fbx_and_classify(context, _FBX_PATH)

        if not head_geo_name:
            self.report({"ERROR"}, "headOnly_geo mesh not found in FBX — aborting")
            return {"CANCELLED"}

        if not armature_name:
            self.report({"ERROR"}, "Armature not found in FBX — aborting")
            return {"CANCELLED"}

        context.scene["mesh"] = head_geo_name
        self.report({"INFO"}, f"head geo: '{head_geo_name}'")

        armature = bpy.data.objects[armature_name]
        chaos_joints = collect_chaos_joints(armature, CHAOS_JOINT_NAMES)
        self.report({"INFO"}, f"Chaos joints found: {[b.name for b in chaos_joints]}")

        config = VariationConfig()
        transforms = generate_chaos_transforms(config, [b.name for b in chaos_joints])
        apply_chaos_keyframes(context, armature, chaos_joints, transforms)

        head_mesh = bpy.data.objects[head_geo_name]
        add_smooth_corrective(head_mesh, SmoothCorrectiveConfig())

        bpy.ops.wm.save_as_mainfile(filepath=_SAVE_PATH)
        return {"FINISHED"}

#test
CLASSES = [
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
]

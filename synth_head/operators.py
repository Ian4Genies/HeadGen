"""
Thin Blender operator layer for Synth Head.

Operators here should delegate to core.py for logic.
Keep this file as thin as possible so the bulk of the
codebase is testable without a live Blender session.
"""

import random

import bpy

from . import core


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
        version = core.clamp(1.0)
        self.report({"INFO"}, f"Synth Head ping OK  (core.clamp check: {version})")
        return {"FINISHED"}


class SYNTHHEAD_OT_VariationPipeline (bpy.types.Operator):
    """Run the variation pipeline"""
    bl_idname = "synth_head.variation_pipeline"
    bl_label = "Synth Head: Variation Pipeline"
    bl_description = "Run the variation pipeline"
    bl_options = {"REGISTER", "UNDO"}

    CHAOS_JOINT_NAMES = {
        "JawBind", "MouthBind","MouthInnerBind", "NoseBind",
        "LeftBrowBind", "RightBrowBind",
        "RightEyeSocketBind", "LeftEyeSocketBind",
        "FaceBind", "NeckBind",
        "LeftShoulderBind", "RightShoulderBind",
        "Spine2Bind",
    }

    def execute(self, context):
        # --- 1. Import FBX, capture what arrived by name before any deletions ---
        before_names = {obj.name for obj in bpy.data.objects}

        bpy.ops.import_scene.fbx(
            filepath="C:/Genies/01_Repo/02_Blender/HeadGen/data/genericGenie-0013-unified_rig.fbx"
        )

        after_names = {obj.name for obj in bpy.data.objects}
        new_names = after_names - before_names

        # Classify by type using names (safe — no stale wrappers)
        head_geo_name = next(
            (n for n in new_names if bpy.data.objects[n].type == 'MESH' and n.startswith("headOnly_geo")),
            None,
        )
        armature_name = next(
            (n for n in new_names if bpy.data.objects[n].type == 'ARMATURE'),
            None,
        )

        # --- 2. Delete unwanted imported objects (everything except headOnly_geo and the armature) ---
        keep = {n for n in (head_geo_name, armature_name) if n}
        to_delete_names = new_names - keep

        bpy.ops.object.select_all(action='DESELECT')
        for name in to_delete_names:
            bpy.data.objects[name].select_set(True)
        if to_delete_names:
            bpy.ops.object.delete()

        for block in bpy.data.meshes:
            if block.users == 0:
                bpy.data.meshes.remove(block)

        # --- 3. Store head geo name on the scene ---
        if head_geo_name:
            context.scene["mesh"] = head_geo_name
            self.report({"INFO"}, f"head geo: '{head_geo_name}'")
        else:
            self.report({"WARNING"}, "headOnly_geo mesh not found in FBX")

        # --- 4. Collect chaos joints from the armature ---
        if not armature_name:
            self.report({"ERROR"}, "Armature not found in FBX")
            return {"CANCELLED"}

        armature = bpy.data.objects[armature_name]
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')

        chaos_joints = [
            bone for bone in armature.pose.bones
            if bone.name in self.CHAOS_JOINT_NAMES
        ]
        self.report({"INFO"}, f"Chaos joints found: {[b.name for b in chaos_joints]}")

        # --- 5. Key chaos joints randomly across frameCount frames ---
        frame_count = 400
        transform_max = 0.2
        rotate_max = 10.0
        scale_max = 0.2

        for frame in range(1, frame_count + 1):
            context.scene.frame_set(frame)
            for bone in chaos_joints:
                bone.location.x = random.uniform(-transform_max, transform_max)
                bone.location.y = random.uniform(-transform_max, transform_max)
                bone.location.z = random.uniform(-transform_max, transform_max)
                bone.rotation_euler.x = random.uniform(-rotate_max, rotate_max)
                bone.rotation_euler.y = random.uniform(-rotate_max, rotate_max)
                bone.rotation_euler.z = random.uniform(-rotate_max, rotate_max)
                bone.scale.x = 1.0 + random.uniform(-scale_max, scale_max)
                bone.scale.y = 1.0 + random.uniform(-scale_max, scale_max)
                bone.scale.z = 1.0 + random.uniform(-scale_max, scale_max)
                bone.keyframe_insert(data_path="location", frame=frame)
                bone.keyframe_insert(data_path="rotation_euler", frame=frame)
                bone.keyframe_insert(data_path="scale", frame=frame)

        bpy.ops.object.mode_set(mode='OBJECT')

        # --- 6. Save result ---
        bpy.ops.wm.save_as_mainfile(
            filepath="C:/Genies/01_Repo/02_Blender/HeadGen/data/gen13_genie_chaos.blend"
        )
        return {"FINISHED"}


CLASSES = [
    SYNTHHEAD_OT_hello,
    SYNTHHEAD_OT_ping,
    SYNTHHEAD_OT_VariationPipeline,
]

"""
Thin Blender operator layer for Synth Head.

Operators here should delegate to core.py for logic.
Keep this file as thin as possible so the bulk of the
codebase is testable without a live Blender session.
"""

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


CLASSES = [
    SYNTHHEAD_OT_hello,
]

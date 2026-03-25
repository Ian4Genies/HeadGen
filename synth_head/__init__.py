import importlib

if "bpy" in locals():
    from . import core, operators
    from .core import math, modifiers as core_modifiers, variation, ref_keys, constraints
    from .core import blendshapes as core_blendshapes
    from . import scene
    from .scene import fbx_import, chaos_anim, modifiers as scene_modifiers, refs as scene_refs
    from .scene import blendshapes as scene_blendshapes

    importlib.reload(math)
    importlib.reload(core_modifiers)
    importlib.reload(constraints)
    importlib.reload(variation)
    importlib.reload(ref_keys)
    importlib.reload(core_blendshapes)
    importlib.reload(core)
    importlib.reload(fbx_import)
    importlib.reload(chaos_anim)
    importlib.reload(scene_modifiers)
    importlib.reload(scene_refs)
    importlib.reload(scene_blendshapes)
    importlib.reload(scene)
    importlib.reload(operators)

import bpy
from . import core, operators, scene

bl_info = {
    "name": "Synth Head",
    "author": "Genies",
    "version": (0, 1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Synth Head",
    "description": "Procedural head generation with shape key control",
    "category": "Mesh",
}


classes = operators.CLASSES


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.synth_head = bpy.props.PointerProperty(
        type=operators.SYNTHHEAD_PG_PipelineRefs,
    )


def unregister():
    del bpy.types.Scene.synth_head
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

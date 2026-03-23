import importlib

if "bpy" in locals():
    from . import core, operators
    from .core import math, variation
    from . import scene
    from .scene import fbx_import, chaos_anim

    importlib.reload(math)
    importlib.reload(variation)
    importlib.reload(core)
    importlib.reload(fbx_import)
    importlib.reload(chaos_anim)
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


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

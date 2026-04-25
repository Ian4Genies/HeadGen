"""
Scene operations for armature management.

All functions here touch the live Blender scene (bpy) and must be tested
interactively via Blender: Start rather than with pytest.
"""

from __future__ import annotations

import bpy


def add_object_to_armature(
    obj: bpy.types.Object,
    armature: bpy.types.Object,
) -> None:
    """Parent *obj* to *armature* with an Armature modifier, cleanly replacing
    any existing armature relationship.

    If *obj* is already parented to another armature, that parent and any
    existing Armature modifiers on *obj* are removed before the new
    relationship is created.

    Args:
        obj:      The mesh object to attach.
        armature: The target armature object.
    """
    if armature.type != "ARMATURE":
        raise ValueError(f"'{armature.name}' is not an armature object (type={armature.type!r})")
    #check if the object is already parented to another armature
    if obj.parent is not None:
        _detach_from_armature(obj)

    obj.parent = armature
    obj.parent_type = "OBJECT"
    obj.matrix_parent_inverse = armature.matrix_world.inverted()

    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature
    mod.use_vertex_groups = True


def _detach_from_armature(obj: bpy.types.Object) -> None:
    """Remove any existing armature parent and Armature modifiers from *obj*."""
    if obj.parent is not None and obj.parent.type == "ARMATURE":
        import mathutils  # available in Blender's bundled Python
        world_matrix = obj.matrix_world.copy()
        parent = obj.parent
        obj.parent = None
        #delete old parent
        bpy.data.objects.remove(parent)
        obj.matrix_world = world_matrix

    mods_to_remove = [m for m in obj.modifiers if m.type == "ARMATURE"]
    for mod in mods_to_remove:
        obj.modifiers.remove(mod)

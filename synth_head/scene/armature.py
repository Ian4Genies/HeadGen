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
    """Remove any existing armature parent and Armature modifiers from *obj*.

    Does NOT delete the old armature — other objects may still be parented to
    it (e.g. multiple objects brought in together by a single append).  Call
    remove_orphan_armatures() once all objects have been reparented.
    """
    if obj.parent is not None and obj.parent.type == "ARMATURE":
        world_matrix = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world_matrix

    mods_to_remove = [m for m in obj.modifiers if m.type == "ARMATURE"]
    for mod in mods_to_remove:
        obj.modifiers.remove(mod)


def attach_constrained_object_to_armature(
    obj: bpy.types.Object,
    armature: bpy.types.Object,
) -> None:
    """Re-parent a constraint-driven object to *armature* without adding an
    Armature modifier, then redirect any armature-targeting constraints.

    Use this for objects like HD eye targets that follow the rig entirely via
    object constraints (e.g. COPY_TRANSFORMS to a bone).  Adding an Armature
    modifier to them would drive vertex deformation on top of the constraint,
    producing incorrect transforms.

    The constraint retarget is done here, before the caller removes orphan
    armatures, while the old armature object is still alive for the type-check.

    Args:
        obj:      The constraint-driven object to attach.
        armature: The canonical armature to become the new parent and
                  constraint target.
    """
    # if armature.type != "ARMATURE":
    #     raise ValueError(f"'{armature.name}' is not an armature object (type={armature.type!r})")

    # if obj.parent is not None:
    #     _detach_from_armature(obj)
    # obj.matrix_parent_inverse = armature.matrix_world.inverted()
    # obj.parent = armature
    # obj.parent_type = "OBJECT"
    # obj.matrix_parent_inverse = armature.matrix_world.inverted()

    for con in obj.constraints:
        if hasattr(con, "target") and con.target is not None and con.target.type == "ARMATURE":
            con.target = armature


def remove_orphan_armatures() -> None:
    """Remove armature objects that have no children remaining.

    Call this once after all objects from a batch append have been reparented
    to the canonical armature.  The imported armatures that Blender forces in
    as append artifacts will by then be childless and safe to delete.
    """
    orphans = [
        obj for obj in bpy.data.objects
        if obj.type == "ARMATURE" and not obj.children
    ]
    for orphan in orphans:
        bpy.data.objects.remove(orphan)

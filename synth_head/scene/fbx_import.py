"""
FBX import and cleanup helpers.

All functions here touch the live Blender scene (bpy) and must be tested
interactively via Blender: Start rather than with pytest.
"""

import bpy


def import_fbx_and_classify(
    context: bpy.types.Context,
    filepath: str,
) -> tuple[bpy.types.Object | None, bpy.types.Object | None]:
    """Import an FBX file and return the head mesh and armature objects.

    Any objects that are neither the head geo nor the armature are deleted
    immediately after import. Orphaned mesh data-blocks are also purged.

    Returns:
        (head_geo, armature) — either may be None if not found.
    """
    before_names = {obj.name for obj in bpy.data.objects}

    bpy.ops.import_scene.fbx(filepath=filepath)

    after_names = {obj.name for obj in bpy.data.objects}
    new_names = after_names - before_names

    new_objects = [bpy.data.objects[n] for n in new_names]

    head_geo = next(
        (o for o in new_objects if o.type == "MESH" and o.name.startswith("headOnly_geo")),
        None,
    )
    armature = next(
        (o for o in new_objects if o.type == "ARMATURE"),
        None,
    )

    keep = {o.name for o in (head_geo, armature) if o}
    to_delete = new_names - keep

    bpy.ops.object.select_all(action="DESELECT")
    for name in to_delete:
        bpy.data.objects[name].select_set(True)
    if to_delete:
        bpy.ops.object.delete()

    purge_orphan_meshes()

    return head_geo, armature


def purge_orphan_meshes() -> None:
    """Remove mesh data-blocks that have no users."""
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)

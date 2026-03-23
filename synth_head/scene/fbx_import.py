"""
FBX import and cleanup helpers.

All functions here touch the live Blender scene (bpy) and must be tested
interactively via Blender: Start rather than with pytest.
"""

import bpy


def import_fbx_and_classify(
    context: bpy.types.Context,
    filepath: str,
) -> tuple[str | None, str | None]:
    """Import an FBX file and return the names of the head mesh and armature.

    Any objects that are neither the head geo nor the armature are deleted
    immediately after import. Orphaned mesh data-blocks are also purged.

    Returns:
        (head_geo_name, armature_name) — either may be None if not found.
    """
    before_names = {obj.name for obj in bpy.data.objects}

    bpy.ops.import_scene.fbx(filepath=filepath)

    after_names = {obj.name for obj in bpy.data.objects}
    new_names = after_names - before_names

    head_geo_name = next(
        (
            n for n in new_names
            if bpy.data.objects[n].type == "MESH" and n.startswith("headOnly_geo")
        ),
        None,
    )
    armature_name = next(
        (n for n in new_names if bpy.data.objects[n].type == "ARMATURE"),
        None,
    )

    keep = {n for n in (head_geo_name, armature_name) if n}
    to_delete = new_names - keep

    bpy.ops.object.select_all(action="DESELECT")
    for name in to_delete:
        bpy.data.objects[name].select_set(True)
    if to_delete:
        bpy.ops.object.delete()

    purge_orphan_meshes()

    return head_geo_name, armature_name


def purge_orphan_meshes() -> None:
    """Remove mesh data-blocks that have no users."""
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)

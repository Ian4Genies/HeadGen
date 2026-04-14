"""
Helpers for appending data-blocks from external .blend files.

All functions here touch the live Blender scene (bpy) and must be tested
interactively via Blender: Start rather than with pytest.
"""

import bpy


def append_material_from_blend(
    blend_path: str,
    material_name: str,
) -> bpy.types.Material | None:
    """Append a material by name from an external .blend file.

    If a material with *material_name* already exists in bpy.data.materials
    the append is skipped and the existing material is returned, avoiding
    duplicate data-blocks across pipeline re-runs.

    Args:
        blend_path:    Absolute path to the source .blend file.
        material_name: Name of the material inside the .blend file.

    Returns:
        The appended (or already-loaded) material, or None on failure.
    """
    existing = bpy.data.materials.get(material_name)
    if existing is not None:
        return existing

    directory = blend_path + "/Material/"
    bpy.ops.wm.append(
        filepath=blend_path + "/Material/" + material_name,
        directory=directory,
        filename=material_name,
        link=False,
        do_reuse_local_id=False,
    )

    return bpy.data.materials.get(material_name)


def append_object_from_blend(
    blend_path: str,
    object_name: str,
) -> bpy.types.Object | None:
    """Append a mesh object by name from an external .blend file.

    Appends the Object data-block (not the raw Mesh) so the result is
    linked into the active collection and visible in the scene.

    If an object with *mesh_name* already exists in bpy.data.objects
    the append is skipped and the existing object is returned, avoiding
    duplicate data-blocks across pipeline re-runs.
    """
    existing = bpy.data.objects.get(object_name)
    if existing is not None:
        return existing
    directory = blend_path + "/Object/"
    bpy.ops.wm.append(
        filepath=blend_path + "/Object/" + object_name,
        directory=directory,
        filename=object_name,
        link=False,
        do_reuse_local_id=False,
    )
    return bpy.data.objects.get(object_name)

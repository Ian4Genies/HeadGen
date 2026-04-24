"""
Helpers for appending data-blocks from external .blend files.

All functions here touch the live Blender scene (bpy) and must be tested
interactively via Blender: Start rather than with pytest.
"""

import bpy
#import armeture methods
from .armature import add_object_to_armature


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


def append_gen13_and_classify(
    blend_path: str,
) -> None:
    """Append the gen13.blend file and classify the objects."""
    head_geo_obj = append_object_from_blend(blend_path, "headOnly_geo")
    #find get the parent of head_geo_obj wich will be the armature
    armature_obj = head_geo_obj.parent
    body_geo_obj = append_object_from_blend(blend_path, "bodyOnly_geo")
    add_object_to_armature(body_geo_obj, armature_obj)
    L_eye_obj = append_object_from_blend(blend_path, "eye_L_geo")
    add_object_to_armature(L_eye_obj, armature_obj)
    R_eye_obj = append_object_from_blend(blend_path, "eye_R_geo")
    add_object_to_armature(R_eye_obj, armature_obj)
    eyebrows_obj = append_object_from_blend(blend_path, "eyebrows_geo")
    add_object_to_armature(eyebrows_obj, armature_obj)
    eyelashes_obj = append_object_from_blend(blend_path, "eyelashes_geo")
    add_object_to_armature(eyelashes_obj, armature_obj)

    return head_geo_obj, body_geo_obj, armature_obj, L_eye_obj, R_eye_obj, eyebrows_obj, eyelashes_obj 


def append_eye_wedge_bake(
    blend_path: str,
    R_bake_name: str,
    L_bake_name: str,
    hd_eye_R_name: str,
    hd_eye_L_name: str,
    R_projector_name: str,
    L_projector_name: str,
) -> bpy.types.Object | None:
    R_bake = append_object_from_blend(blend_path, R_bake_name)
    L_bake = append_object_from_blend(blend_path, L_bake_name)
    #Projector and hd eye are already in the scene, because the are linked to bake objects
    #we need to find them by name
    R_projector = bpy.data.objects.get(R_projector_name)
    L_projector = bpy.data.objects.get(L_projector_name)
    hd_eye_R = bpy.data.objects.get(hd_eye_R_name)
    hd_eye_L = bpy.data.objects.get(hd_eye_L_name)
    return R_bake, L_bake, hd_eye_R, hd_eye_L, R_projector, L_projector
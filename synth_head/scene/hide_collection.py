"""Move configured objects into a hidden viewport collection."""

import bpy

_HIDE_COLLECTION_NAME = "hideCollection"


def _ensure_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(_HIDE_COLLECTION_NAME)
    if col is None:
        col = bpy.data.collections.new(_HIDE_COLLECTION_NAME)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def hide_objects_in_collection(scene: bpy.types.Scene, object_names: list[str]) -> None:
    """Move *object_names* into hideCollection and hide them in the viewport."""
    if not object_names:
        return
    col = _ensure_collection(scene)
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        for user_col in list(obj.users_collection):
            user_col.objects.unlink(obj)
        if obj.name not in col.objects:
            col.objects.link(obj)
        obj.hide_viewport = True

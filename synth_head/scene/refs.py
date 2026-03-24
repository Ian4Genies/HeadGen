"""
Generic get/set for pipeline object references.

All references are stored as PointerProperties on SYNTHHEAD_PG_PipelineRefs,
which lives on bpy.context.scene.synth_head.  Use the string constants from
core.ref_keys as keys — never pass bare strings from call sites.

To add a new reference:
  1. Add a PointerProperty to SYNTHHEAD_PG_PipelineRefs in operators.py.
  2. Add a matching constant to core/ref_keys.py.
  No changes needed here.
"""

from __future__ import annotations

import bpy


def set_ref(context: bpy.types.Context, key: str, obj: bpy.types.Object) -> None:
    """Store *obj* under *key* in the pipeline reference group.

    Raises KeyError if *key* does not match a declared PointerProperty.
    """
    refs = context.scene.synth_head
    if not hasattr(refs, key):
        raise KeyError(f"Unknown pipeline ref key: {key!r}")
    setattr(refs, key, obj)


def get_ref(context: bpy.types.Context, key: str) -> bpy.types.Object | None:
    """Return the object stored under *key*, or None if unset or deleted.

    Raises KeyError if *key* does not match a declared PointerProperty.
    """
    refs = context.scene.synth_head
    if not hasattr(refs, key):
        raise KeyError(f"Unknown pipeline ref key: {key!r}")
    return getattr(refs, key)

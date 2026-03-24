"""Public API for synth_head.scene — bpy-heavy scene operations."""

from .fbx_import import import_fbx_and_classify, purge_orphan_meshes
from .chaos_anim import collect_chaos_joints, apply_chaos_keyframes
from .modifiers import add_smooth_corrective
from .refs import get_ref, set_ref

__all__ = [
    "import_fbx_and_classify",
    "purge_orphan_meshes",
    "collect_chaos_joints",
    "apply_chaos_keyframes",
    "add_smooth_corrective",
    "get_ref",
    "set_ref",
]

"""
Texture overlay swap — bpy scene operations.

Handles reading and writing image sequence node properties on materials,
including fallback path wiring and per-frame offset keyframing.
All functions here touch the live Blender scene.
"""

from __future__ import annotations

from pathlib import Path

import bpy


# ---------------------------------------------------------------------------
# Node access
# ---------------------------------------------------------------------------

def get_sequence_node(
    material: bpy.types.Material,
    node_name: str,
) -> bpy.types.ShaderNodeTexImage | None:
    """Return the named image-sequence node from *material*, or ``None``."""
    if material is None or material.node_tree is None:
        return None
    return material.node_tree.nodes.get(node_name)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Sequence wiring (fallback safety)
# ---------------------------------------------------------------------------

def point_texture_sequence_node(
    material: bpy.types.Material,
    node_name: str,
    first_file_path: Path | str,
    start_frame: int,
    frame_count: int,
) -> None:
    """Fallback safety: wire *first_file_path* into the node when needed.

    The nodes in the head material are expected to arrive already pointing at
    the existing ``prefix_0001.png`` in the sequence directory.  This function
    only acts when:

      - The node has no image set (first ever run), or
      - The node's image directory does not match *first_file_path*'s directory
        (i.e. the sequence was moved or rebuilt to a new location).

    When the directory changed, ``image.reload()`` is called so Blender picks
    up the updated pool-file sequence.  ``frame_start`` and ``frame_duration``
    are always synced to the current manifest values.
    """
    node = get_sequence_node(material, node_name)
    if node is None:
        return

    first = Path(first_file_path)
    expected_dir = first.parent.resolve()

    if node.image is not None:
        try:
            existing_dir = Path(bpy.path.abspath(node.image.filepath)).parent.resolve()
        except Exception:
            existing_dir = None

        if existing_dir == expected_dir:
            # Directory already correct — just update frame settings
            node.image_user.frame_start = start_frame
            node.image_user.frame_duration = frame_count
            return

        # Directory changed — update and reload
        node.image.filepath = str(first)
        node.image.source = "SEQUENCE"
        node.image.reload()
        node.image_user.frame_start = start_frame
        node.image_user.frame_duration = frame_count
        return

    # No image set — load fresh
    image = bpy.data.images.load(filepath=str(first))
    image.source = "SEQUENCE"
    node.image = image
    node.image_user.frame_start = start_frame
    node.image_user.frame_duration = frame_count


# ---------------------------------------------------------------------------
# Frame count / start frame
# ---------------------------------------------------------------------------

def set_sequence_frames(
    material: bpy.types.Material,
    node_name: str,
    frame_count: int,
) -> None:
    """Set ``frame_duration`` (and enforce ``frame_start = 1``) on the node.

    ``frame_start`` is always 1 for the texture swap system per the design
    constraint that the selective-paging offset formula uses a fixed anchor.
    """
    node = get_sequence_node(material, node_name)
    if node is None:
        return
    node.image_user.frame_duration = frame_count
    node.image_user.frame_start = 1


# ---------------------------------------------------------------------------
# Per-frame offset keyframing
# ---------------------------------------------------------------------------

def key_sequence_offset(
    material: bpy.types.Material,
    node_name: str,
    offset: int,
    frame: int,
) -> None:
    """Set and keyframe ``frame_offset`` on the named node's ``image_user``.

    The keyframe is inserted on *frame* so the Blender timeline plays back
    the correct pool texture for each variation frame.
    """
    node = get_sequence_node(material, node_name)
    if node is None:
        return
    node.image_user.frame_offset = offset
    node.image_user.keyframe_insert(data_path="frame_offset", frame=frame)


def read_sequence_offset(
    material: bpy.types.Material,
    node_name: str,
) -> int | None:
    """Return the current ``frame_offset`` from the named node, or ``None``."""
    node = get_sequence_node(material, node_name)
    if node is None:
        return None
    return node.image_user.frame_offset


def clear_sequence_offset_keyframes(
    material: bpy.types.Material,
    node_name: str,
) -> None:
    """Remove all ``frame_offset`` fcurves for *node_name* from the node tree's action.

    Called before a fresh variation bake to prevent stale keyframes from a
    prior pipeline run from conflicting with the new offset values.
    """
    if material.node_tree is None:
        return
    anim = material.node_tree.animation_data
    if anim is None or anim.action is None:
        return
    data_path = f'nodes["{node_name}"].image_user.frame_offset'
    for layer in anim.action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                to_remove = [fc for fc in channelbag.fcurves if fc.data_path == data_path]
                for fc in to_remove:
                    channelbag.fcurves.remove(fc)

import bpy
import random

# ---------------------------------------------------------------------------
# Per-shader-type color keying helpers
# Each entry: shader node.type → callable(node, node_tree, color, frame) → bool
# Add new shader types here as needed.
# ---------------------------------------------------------------------------

def _key_color_bsdf_principled(
    node: bpy.types.Node,
    node_tree: bpy.types.NodeTree,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe Base Color on a Principled BSDF node. Returns True if applied."""
    inp = node.inputs.get("Base Color")
    if inp is None or inp.type != "RGBA":
        return False
    if inp.is_linked:
        for link in inp.links:
            node_tree.links.remove(link)
    inp.default_value = color
    inp.keyframe_insert("default_value", frame=frame)
    return True


# Map node.type → handler. Extend this dict to support additional shaders.
_SHADER_COLOR_HANDLERS: dict[str, callable] = {
    "BSDF_PRINCIPLED": _key_color_bsdf_principled,
    # "BSDF_DIFFUSE":  _key_color_bsdf_diffuse,   # example placeholder
    # "EMISSION":      _key_color_emission,         # example placeholder
}

# Label used to locate the skin color RGB node inside head_mat.
_HEAD_COLOR_NODE_LABEL = "head_color"


def _find_node_by_label(
    node_tree: bpy.types.NodeTree,
    label: str,
) -> bpy.types.Node | None:
    """Return the first node whose label matches *label* (case-sensitive)."""
    return next((n for n in node_tree.nodes if n.label == label), None)


def _key_color_rgb_node(
    node: bpy.types.Node,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe the color output of an RGB node. Returns True if applied."""
    # RGB nodes expose their color via the 'Color' output socket's default value,
    # but the editable property is node.color — for an RGB node it is node.outputs[0].default_value.
    output = node.outputs[0] if node.outputs else None
    if output is None or output.type != "RGBA":
        return False
    output.default_value = color
    node.outputs[0].keyframe_insert("default_value", frame=frame)
    return True


# ---------------------------------------------------------------------------
# Public material helpers
# ---------------------------------------------------------------------------

def assign_exclusive_material(
    mesh_obj: bpy.types.Object,
    mat: bpy.types.Material,
) -> None:
    """Clear all material slots on mesh_obj and assign mat as the sole material."""
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    mesh_obj.active_material_index = 0


def key_material_color(
    mat: bpy.types.Material,
    color: tuple[float, float, float, float],
    frame: int,
) -> bool:
    """Set and keyframe the skin color on mat.

    Targets the RGB node labelled _HEAD_COLOR_NODE_LABEL first.
    Falls back to the first supported shader type in _SHADER_COLOR_HANDLERS
    if no labelled node is found.
    Returns True if a color was applied.
    """
    if mat is None or not mat.use_nodes:
        return False

    node = _find_node_by_label(mat.node_tree, _HEAD_COLOR_NODE_LABEL)
    if node is not None:
        return _key_color_rgb_node(node, color, frame)

    # Fallback: dispatch by shader type
    for n in mat.node_tree.nodes:
        handler = _SHADER_COLOR_HANDLERS.get(n.type)
        if handler is not None:
            return handler(n, mat.node_tree, color, frame)

    return False


# ---------------------------------------------------------------------------
# Public operator-facing helpers
# ---------------------------------------------------------------------------

def randomize_head_material_color(
    mesh_obj: bpy.types.Object,
    color: tuple[float, float, float, float],
    frame: int,
) -> None:
    """Set and keyframe *color* on the first material slot of mesh_obj."""
    if not mesh_obj.material_slots:
        return
    mat = mesh_obj.material_slots[0].material
    key_material_color(mat, color, frame)


def apply_attractive_color(
    mesh_obj: bpy.types.Object,
    attractive_color: list[float],
    rng_color: tuple[float, float, float, float],
    randomness: float,
    frame: int,
) -> None:
    """Blend the attractive color with the RNG color and keyframe the result.

    The final color is:
        final = attractive_color + randomness * (rng_color - attractive_color)

    At randomness=0.0 the result is purely the attractive color.
    At randomness=1.0 the result is purely the RNG color.
    The blended color overwrites whatever color is currently keyframed on the material.
    """
    if not mesh_obj.material_slots:
        return
    mat = mesh_obj.material_slots[0].material
    if mat is None:
        return

    r = attractive_color[0] + randomness * (rng_color[0] - attractive_color[0])
    g = attractive_color[1] + randomness * (rng_color[1] - attractive_color[1])
    b = attractive_color[2] + randomness * (rng_color[2] - attractive_color[2])
    a = attractive_color[3] + randomness * (rng_color[3] - attractive_color[3])

    key_material_color(mat, (r, g, b, a), frame)


def read_material_color(
    mesh_obj: bpy.types.Object,
) -> list[float] | None:
    """Read the current skin color from the first material slot of mesh_obj.

    Targets the RGB node labelled _HEAD_COLOR_NODE_LABEL first.
    Falls back to the Base Color input of the first supported shader type.
    Returns [r, g, b, a] as a plain list, or None if no color could be read.
    """
    if not mesh_obj.material_slots:
        return None

    mat = mesh_obj.material_slots[0].material
    if mat is None or not mat.use_nodes:
        return None

    node = _find_node_by_label(mat.node_tree, _HEAD_COLOR_NODE_LABEL)
    if node is not None:
        output = node.outputs[0] if node.outputs else None
        if output is not None and output.type == "RGBA":
            return list(output.default_value)

    # Fallback: read Base Color from the first supported shader node
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            inp = n.inputs.get("Base Color")
            if inp is not None and inp.type == "RGBA":
                return list(inp.default_value)

    return None

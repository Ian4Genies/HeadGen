"""
Scene operations for FCurve driver wiring.

Builds or rebuilds scripted drivers from a DriversConfig, mapping source
bone/object custom properties to target properties.

Supported target types
----------------------
- Object custom property  (default)
- Pose bone custom property  (when ``target_bone`` is set)
- Mesh shape key value  (when ``target_is_shape_key`` is True)

For shape key targets the driver is placed on the mesh's ``Key`` data block
(``obj.data.shape_keys``) at path ``key_blocks["<name>"].value``, which is
the correct Blender data path for driving shape key weights via FCurves.

All functions here touch the live Blender scene and must be tested
interactively via Blender: Start rather than with pytest.
"""

from __future__ import annotations

import bpy


_ARMATURE_TOKEN = "ARMATURE"


def _resolve_object(
    name: str,
    armature: bpy.types.Object,
) -> bpy.types.Object | None:
    """Return the scene object for *name*, substituting *armature* for the
    ``"ARMATURE"`` token.  Returns None if the object is not found."""
    if name == _ARMATURE_TOKEN:
        return armature
    return bpy.data.objects.get(name)


def _build_prop_path(bone: str | None, prop: str) -> str:
    """Build a Blender data path for a custom property (object or bone)."""
    if bone:
        return f'pose.bones["{bone}"]["{prop}"]'
    return f'["{prop}"]'


def build_drivers(
    armature: bpy.types.Object,
    drivers_config,
) -> None:
    """Clear and rebuild all FCurve drivers defined in *drivers_config*.

    Each entry in the config describes one driver relationship.  Any driver
    already present on the target data path is removed first so stale drivers
    from the imported .blend file do not survive the pipeline setup.

    The special object name ``"ARMATURE"`` resolves to *armature* at runtime.

    Shape key targets
    -----------------
    When ``spec.target_is_shape_key`` is True the driver is placed on the
    mesh's ``Key`` data block (``obj.data.shape_keys``) rather than on the
    object itself.  The data path becomes
    ``key_blocks["<target_property>"].value``.

    Args:
        armature:       The canonical armature object.
        drivers_config: A ``DriversConfig`` instance (from ``core/config.py``).
    """
    for spec in drivers_config.drivers:
        target_obj = _resolve_object(spec.target_object, armature)
        source_obj = _resolve_object(spec.source_object, armature)

        if target_obj is None:
            print(
                f"[SynthHead][Drivers] WARNING: target object "
                f"'{spec.target_object}' not found — skipping "
                f"driver for '{spec.target_property}'"
            )
            continue

        if source_obj is None:
            print(
                f"[SynthHead][Drivers] WARNING: source object "
                f"'{spec.source_object}' not found — skipping "
                f"driver for '{spec.target_property}'"
            )
            continue

        source_path = _build_prop_path(spec.source_bone, spec.source_property)

        if spec.target_is_shape_key:
            shape_keys = getattr(getattr(target_obj, "data", None), "shape_keys", None)
            if shape_keys is None:
                print(
                    f"[SynthHead][Drivers] WARNING: object '{spec.target_object}' "
                    f"has no shape keys — skipping driver for '{spec.target_property}'"
                )
                continue

            key_block = shape_keys.key_blocks.get(spec.target_property)
            if key_block is None:
                print(
                    f"[SynthHead][Drivers] WARNING: shape key '{spec.target_property}' "
                    f"not found on '{spec.target_object}' — skipping"
                )
                continue

            # Shape key drivers are added on the key_block itself at path "value".
            key_block.driver_remove("value")
            fcurve = key_block.driver_add("value")
        else:
            target_path = _build_prop_path(spec.target_bone, spec.target_property)
            target_obj.driver_remove(target_path)
            fcurve = target_obj.driver_add(target_path)
        driver = fcurve.driver
        driver.type = "SCRIPTED"
        driver.expression = spec.expression

        var = driver.variables.new()
        var.name = "var"
        var.type = "SINGLE_PROP"
        var.targets[0].id = source_obj
        var.targets[0].data_path = source_path

        if spec.target_is_shape_key:
            target_label = f"{spec.target_object}.shape_keys['{spec.target_property}']"
        elif spec.target_bone:
            target_label = f"{spec.target_object}.{spec.target_bone}.{spec.target_property}"
        else:
            target_label = f"{spec.target_object}.{spec.target_property}"

        source_label = (
            f"{spec.source_object}.{spec.source_bone}.{spec.source_property}"
            if spec.source_bone
            else f"{spec.source_object}.{spec.source_property}"
        )
        print(f"[SynthHead][Drivers] Wired: {source_label} → {target_label}  expr='{spec.expression}'")

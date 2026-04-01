"""Math primitives — pure Python, no bpy scene dependency."""

import math as _math

from mathutils import Euler, Quaternion


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def euler_degrees_to_quaternion(
    rotation_deg: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    """Convert an XYZ Euler rotation in degrees to a (w, x, y, z) quaternion."""
    euler = Euler(
        (
            _math.radians(rotation_deg[0]),
            _math.radians(rotation_deg[1]),
            _math.radians(rotation_deg[2]),
        ),
        'XYZ',
    )
    q = euler.to_quaternion()
    return (q.w, q.x, q.y, q.z)


def quaternion_to_euler_degrees(
    wxyz: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    """Convert a (w, x, y, z) quaternion to an XYZ Euler rotation in degrees."""
    q = Quaternion((wxyz[0], wxyz[1], wxyz[2], wxyz[3]))
    euler = q.to_euler('XYZ')
    return (
        _math.degrees(euler.x),
        _math.degrees(euler.y),
        _math.degrees(euler.z),
    )

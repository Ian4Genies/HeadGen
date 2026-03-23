"""Math primitives — pure Python, no bpy scene dependency."""

import math as _math

from mathutils import Euler


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

"""Math primitives — pure Python, no bpy dependency."""


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))

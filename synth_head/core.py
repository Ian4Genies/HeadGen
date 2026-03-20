"""
Pure Python business logic for Synth Head.

Keep bpy usage to an absolute minimum here. Functions in this module
should be testable with plain pytest against the bpy pip package,
without needing a live Blender session.
"""


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))

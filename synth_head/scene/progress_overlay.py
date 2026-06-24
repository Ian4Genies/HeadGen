"""Fullscreen export progress overlay — gpu draw handler + WM state."""

from __future__ import annotations

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

_HANDLES: list[tuple[bpy.types.Space, int]] = []
_SHADER = None


def _shader():
    global _SHADER
    if _SHADER is None:
        _SHADER = gpu.shader.from_builtin("UNIFORM_COLOR")
    return _SHADER


class SYNTHHEAD_PG_ExportProgress(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(name="Active", default=False)
    title: bpy.props.StringProperty(name="Title", default="")
    phase: bpy.props.StringProperty(name="Phase", default="")
    detail: bpy.props.StringProperty(name="Detail", default="")
    step: bpy.props.IntProperty(name="Step", default=0, min=0)
    total: bpy.props.IntProperty(name="Total", default=1, min=1)
    frame: bpy.props.IntProperty(name="Frame", default=0, min=0)
    frame_end: bpy.props.IntProperty(name="Frame End", default=0, min=0)
    pct: bpy.props.IntProperty(name="Percent", default=0, min=0, max=100)
    cancel_requested: bpy.props.BoolProperty(name="Cancel", default=False)


def progress_props(context: bpy.types.Context) -> SYNTHHEAD_PG_ExportProgress:
    return context.window_manager.synth_head_export_progress


def _rect_batch(x: float, y: float, w: float, h: float):
    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    return batch_for_shader(_shader(), "TRI_FAN", {"pos": verts})


def _fill(x: float, y: float, w: float, h: float, color: tuple[float, float, float, float]) -> None:
    shader = _shader()
    shader.bind()
    shader.uniform_float("color", color)
    _rect_batch(x, y, w, h).draw(shader)


def _text(font_id: int, x: float, y: float, text: str, size: int, color: tuple[float, float, float, float]) -> None:
    if not text:
        return
    blf.size(font_id, size)
    blf.color(font_id, *color)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def _draw_overlay() -> None:
    ctx = bpy.context
    pg = ctx.window_manager.synth_head_export_progress
    if not pg.active:
        return

    region = ctx.region
    if region is None:
        return

    w, h = region.width, region.height
    if w < 64 or h < 64:
        return

    gpu.state.blend_set("ALPHA")
    _fill(0, 0, w, h, (0.03, 0.03, 0.07, 0.88))

    card_w = min(840, w - 48)
    card_h = min(320, int(h * 0.38))
    cx = (w - card_w) * 0.5
    cy = (h - card_h) * 0.5

    _fill(cx, cy, card_w, card_h, (0.08, 0.08, 0.12, 0.96))
    _fill(cx, cy + card_h - 3, card_w, 3, (0.45, 0.28, 0.85, 1.0))

    font = 0
    pad = 22
    tx = cx + pad
    ty = cy + card_h - pad

    _text(font, tx, ty, pg.title or "Synth Head", 28, (0.95, 0.94, 1.0, 1.0))
    ty -= 42
    _text(font, tx, ty, pg.phase or "Working…", 20, (0.72, 0.68, 0.92, 1.0))

    if pg.frame_end > 0:
        ty -= 32
        _text(font, tx, ty, f"Frame {pg.frame} / {pg.frame_end}", 16, (0.55, 0.58, 0.68, 1.0))

    if pg.detail:
        ty -= 26
        _text(font, tx, ty, pg.detail, 14, (0.45, 0.48, 0.58, 1.0))

    bar_y = cy + 36
    bar_h = 18
    bar_w = card_w - pad * 2
    frac = pg.step / max(1, pg.total)
    _fill(tx, bar_y, bar_w, bar_h, (0.16, 0.16, 0.22, 1.0))
    if frac > 0:
        _fill(tx, bar_y, bar_w * frac, bar_h, (0.52, 0.32, 0.95, 1.0))

    pct = f"{pg.pct}%"
    blf.size(font, 36)
    blf.color(font, 0.92, 0.88, 1.0, 1.0)
    tw = blf.dimensions(font, pct)[0]
    _text(font, cx + card_w - pad - tw, cy + card_h - pad - 6, pct, 36, (0.92, 0.88, 1.0, 1.0))

    _text(font, cx + pad, cy + 14, "Esc to cancel", 13, (0.38, 0.40, 0.50, 0.9))
    gpu.state.blend_set("NONE")


def overlay_begin(context: bpy.types.Context, *, title: str, total_steps: int) -> None:
    pg = progress_props(context)
    pg.active = True
    pg.title = title
    pg.phase = "Starting…"
    pg.detail = ""
    pg.step = 0
    pg.total = max(1, total_steps)
    pg.frame = 0
    pg.frame_end = 0
    pg.pct = 0
    pg.cancel_requested = False

    _HANDLES.clear()
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            space = area.spaces.active
            if space is None:
                continue
            handle = space.draw_handler_add(_draw_overlay, (), "WINDOW", "POST_PIXEL")
            _HANDLES.append((space, handle))
            area.tag_redraw()

    overlay_refresh(context)


def overlay_end(context: bpy.types.Context) -> None:
    pg = progress_props(context)
    pg.active = False
    for space, handle in _HANDLES:
        try:
            space.draw_handler_remove(handle, "WINDOW")
        except Exception:
            pass
    _HANDLES.clear()
    context.workspace.status_text_set(None)
    context.window_manager.progress_end()
    overlay_refresh(context)


def overlay_refresh(context: bpy.types.Context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def overlay_update(
    context: bpy.types.Context,
    *,
    phase: str,
    step: int,
    total: int,
    frame: int = 0,
    frame_end: int = 0,
    detail: str = "",
) -> bool:
    """Update overlay + WM progress. Returns False if user cancelled."""
    wm = context.window_manager
    pg = progress_props(context)
    pg.phase = phase
    pg.step = min(step, total)
    pg.total = max(1, total)
    pg.frame = frame
    pg.frame_end = frame_end
    pg.detail = detail
    pg.pct = int(100 * pg.step / pg.total)

    if pg.cancel_requested or wm.progress_update(pg.step):
        pg.cancel_requested = True
        return False

    context.workspace.status_text_set(
        f"{pg.title} · {pg.pct}% · {phase}"
        + (f" · F{frame}/{frame_end}" if frame_end else "")
    )
    overlay_refresh(context)
    return True

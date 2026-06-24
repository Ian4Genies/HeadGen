"""Pipeline progress — overlay + WM progress bar."""

from __future__ import annotations

import bpy

from .progress_overlay import overlay_begin, overlay_end, overlay_update, progress_props


def export_pipeline_step_count(
    frame_start: int,
    frame_end: int,
    *,
    has_body_join: bool,
    copy_eye_projection: bool,
    bake_hd_eyes: bool,
    save_blend: bool,
) -> int:
    frames = max(0, frame_end - frame_start + 1)
    per_frame = 3
    if copy_eye_projection or bake_hd_eyes:
        per_frame += 1
    steps = frames * per_frame
    if has_body_join:
        steps += 1
    if save_blend:
        steps += 1
    return max(1, steps)


class PipelineProgress:
    """Fullscreen overlay progress; yields to modal between steps."""

    def __init__(self, context: bpy.types.Context, *, title: str, total_steps: int) -> None:
        self._context = context
        self._title = title
        self._total = max(1, total_steps)
        self._step = 0
        self.cancelled = False

    def __enter__(self) -> "PipelineProgress":
        overlay_begin(self._context, title=self._title, total_steps=self._total)
        self._context.window_manager.progress_begin(0, self._total)
        return self

    def __exit__(self, *_args) -> None:
        overlay_end(self._context)

    def advance(
        self,
        phase: str,
        *,
        frame: int | None = None,
        frame_end: int | None = None,
        detail: str = "",
    ) -> bool:
        self._step = min(self._step + 1, self._total)
        ok = overlay_update(
            self._context,
            phase=phase,
            step=self._step,
            total=self._total,
            frame=frame or 0,
            frame_end=frame_end or 0,
            detail=detail,
        )
        if not ok:
            self.cancelled = True
        return ok

    def request_cancel(self) -> None:
        progress_props(self._context).cancel_requested = True
        self.cancelled = True

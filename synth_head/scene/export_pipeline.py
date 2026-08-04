"""Export pipeline — generator yields between steps for modal progress UI."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import bpy

from ..core.config import PipelineConfig
from ..core.export import eye_bake_seq_png_name, frame_dir_name, frame_glb_name, frame_png_name
from .export_bake import bake_head_materials, bake_object_material, scope_bake_environment
from .export_glb import export_glb, rewrite_head_material_slots, staging_scene, stamp_frame_names
from .mesh import cut_and_sew, join_and_merge
from .progress import PipelineProgress, export_pipeline_step_count
from .progress_overlay import progress_props
from .refs import set_ref
from ..core.ref_keys import BODY_GEO


def export_pipeline_generator(
    context: bpy.types.Context,
    cfg: PipelineConfig,
    refs: SimpleNamespace,
    *,
    wedge_projection: bool,
    out_dir: Path,
    start: int,
    end: int,
    write_snapshot: Callable,
) -> Iterator[None]:
    """Run export one phase per ``next()`` — keeps the overlay responsive."""
    total_steps = export_pipeline_step_count(
        start,
        end,
        has_body_join=refs.body_geo is not None,
        copy_eye_projection=bool(wedge_projection and cfg.export.copy_eye_projection),
        bake_hd_eyes=bool(not wedge_projection and cfg.export.bake_hd_eye_texture_direct),
        save_blend=bool(cfg.runner.save_export_blend_path),
    )

    def _abort(prog: PipelineProgress) -> bool:
        if progress_props(context).cancel_requested:
            prog.cancelled = True
        return prog.cancelled

    with PipelineProgress(context, title="Synth Head Export", total_steps=total_steps) as prog:
        if refs.body_geo is not None:
            if not prog.advance("Join head + body"):
                return
            yield
            if _abort(prog):
                return
            join_and_merge(
                [refs.head_geo, refs.body_geo],
                refs.head_geo,
                merge_distance=cfg.cleanup.join_merge_distance,
            )
            set_ref(context, BODY_GEO, None)

        with scope_bake_environment(refs.head_geo, cfg.export) as bake_ctx:
            for frame in range(start, end + 1):
                context.scene.frame_set(frame)
                frame_dir = out_dir / frame_dir_name(frame)
                frame_dir.mkdir(parents=True, exist_ok=True)

                if not prog.advance("Bake head textures", frame=frame, frame_end=end):
                    return
                yield
                if _abort(prog):
                    return
                png_paths = bake_head_materials(
                    refs.head_geo,
                    bake_ctx,
                    frame_dir=frame_dir,
                    samples=cfg.export.bake_samples,
                    margin=cfg.export.bake_margin,
                )

                if wedge_projection and cfg.export.copy_eye_projection:
                    if not prog.advance("Copy eye bakes", frame=frame, frame_end=end):
                        return
                    yield
                    if _abort(prog):
                        return
                    seq_R = Path(cfg.projection.baked_sequence_R_path)
                    seq_L = Path(cfg.projection.baked_sequence_L_path)
                    for side, seq_dir, suffix in (
                        ("R", seq_R, "R_eye_wedge"),
                        ("L", seq_L, "L_eye_wedge"),
                    ):
                        src = seq_dir / eye_bake_seq_png_name(frame, side)
                        dst = frame_dir / frame_png_name(suffix)
                        if src.exists():
                            shutil.copy2(src, dst)
                            png_paths[suffix] = dst
                        else:
                            print(f"[SynthHead][Export] WARNING: eye bake not found: {src}")

                elif not wedge_projection and cfg.export.bake_hd_eye_texture_direct:
                    if not prog.advance("Bake HD eyes", frame=frame, frame_end=end):
                        return
                    yield
                    if _abort(prog):
                        return
                    for obj, suffix in (
                        (refs.hd_eye_R, "R_hd_eye"),
                        (refs.hd_eye_L, "L_hd_eye"),
                    ):
                        if obj is not None:
                            # hd_eye_R/hd_eye_L each carry their own material
                            # (needed so heterochromia can key each eye's
                            # color independently) — bake whichever material
                            # is actually on this object rather than assuming
                            # both share cfg.export.hd_eye_material_name.
                            material_name = (
                                obj.active_material.name
                                if obj.active_material is not None
                                else cfg.export.hd_eye_material_name
                            )
                            p = bake_object_material(
                                obj,
                                material_name,
                                suffix,
                                cfg.export.hd_eye_bake_resolution,
                                frame_dir,
                                cfg.export.bake_samples,
                                cfg.export.bake_margin,
                            )
                            if p is not None:
                                png_paths[suffix] = p

                if not prog.advance("Export GLB", frame=frame, frame_end=end):
                    return
                yield
                if _abort(prog):
                    return
                glb_path = frame_dir / frame_glb_name(frame)
                with staging_scene(refs, cfg.export) as stage:
                    if cfg.export.clean_head_on_export:
                        cut_and_sew(
                            cfg.cleanup.mouth_bag_group,
                            stage.head_geo,
                            cfg.cleanup.mouth_sew_indices,
                            merge_distance=cfg.cleanup.lip_sew_merge_distance,
                            remove_mouth_bag=cfg.cleanup.remove_mouth_bag,
                            snap_lips=cfg.cleanup.snap_lips,
                            sew_lips=cfg.cleanup.sew_lips,
                        )
                    rewrite_head_material_slots(stage.head_geo, png_paths, cfg.export)
                    stamp_frame_names(stage.objects, frame)
                    export_glb(stage.objects, glb_path, format=cfg.export.glb_format)

                if not prog.advance("Write snapshot", frame=frame, frame_end=end, detail=glb_path.name):
                    return
                yield
                if _abort(prog):
                    return
                write_snapshot(context, cfg, frame_dir, frame, label="final")
                print(f"[SynthHead][Export] frame {frame}/{end} done")

        if cfg.runner.save_export_blend_path:
            if not prog.advance("Save export blend"):
                return
            yield
            if _abort(prog):
                return
            Path(cfg.runner.save_export_blend_path).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=cfg.runner.save_export_blend_path)

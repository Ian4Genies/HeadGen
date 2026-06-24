"""Tests for synth_head.scene.progress step counting."""

from synth_head.scene.progress import export_pipeline_step_count


def test_export_steps_minimal():
    assert export_pipeline_step_count(
        1, 10,
        has_body_join=False,
        copy_eye_projection=False,
        bake_hd_eyes=False,
        save_blend=False,
    ) == 30  # 10 frames × 3 phases


def test_export_steps_full():
    assert export_pipeline_step_count(
        1, 5,
        has_body_join=True,
        copy_eye_projection=True,
        bake_hd_eyes=False,
        save_blend=True,
    ) == 1 + 5 * 4 + 1  # join + 5×(bake+copy+export+snapshot) + save

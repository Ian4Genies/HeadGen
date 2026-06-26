"""Value Trace API — delegates to synth_head.core.pipeline_trace."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from synth_head.core.config import PipelineConfig, load_config
from synth_head.core.pipeline_trace import (
    build_trace_catalog,
    collect_param_stages,
    simulate_pipeline,
)

from . import profiles as prof
from .schema import CONFIG_FILE_IDS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


def _profile_config_dir(name: str) -> Path:
    prof.ensure_profiles_layout()
    path = prof.PROFILES_DIR / name
    if not path.is_dir():
        raise prof.ProfileError(f"Profile not found: {name}")
    return path


def load_profile_config(name: str, overrides: dict[str, dict] | None = None) -> PipelineConfig:
    """Load PipelineConfig from profile, optionally merging unsaved UI overrides."""
    if overrides:
        merged_dir = _build_merged_config(name, overrides)
        return load_config(merged_dir, project_root=DATA_ROOT)
    return load_config(_profile_config_dir(name), project_root=DATA_ROOT)


def _deep_overlay(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_overlay(out[key], val)
        else:
            out[key] = deepcopy(val)
    return out


def _build_merged_config(profile: str, overrides: dict[str, dict]) -> Path:
    import json
    import tempfile

    base = _profile_config_dir(profile)
    tmp = Path(tempfile.mkdtemp(prefix="sh_trace_"))
    for file_id in CONFIG_FILE_IDS:
        src = base / f"{file_id}.json"
        data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
        if file_id in overrides:
            data = _deep_overlay(data, overrides[file_id])
        (tmp / f"{file_id}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return tmp


def get_catalog(name: str) -> dict[str, Any]:
    cfg = load_profile_config(name)
    return build_trace_catalog(cfg)


def get_param_stages(name: str, param_key: str) -> dict[str, Any]:
    cfg = load_profile_config(name)
    return collect_param_stages(cfg, param_key)


def run_simulate(
    name: str,
    param_key: str,
    mode: str = "randomize_face",
    seed: int | None = None,
    starting_value: float | None = None,
    input_flat: dict[str, float] | None = None,
    config_overrides: dict[str, dict] | None = None,
) -> dict[str, Any]:
    cfg = load_profile_config(name, config_overrides)
    if mode not in ("randomize_face", "rerandomize"):
        raise ValueError(f"Unknown mode: {mode!r}")
    return simulate_pipeline(
        cfg,
        param_key,
        mode=mode,
        seed=seed,
        starting_value=starting_value,
        input_flat=input_flat,
    )

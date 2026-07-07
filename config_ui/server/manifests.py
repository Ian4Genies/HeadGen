"""Master catalogs for joints, shapes, bone properties, and texture channels."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synth_head.core.blendshapes import EXPRESSION_SHAPES, VARIATION_SHAPES
from synth_head.core.variation import CHAOS_JOINT_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = PROJECT_ROOT / "data" / "manifests"
PROFILES_DIR = PROJECT_ROOT / "data" / "profiles"

MANIFEST_IDS = (
    "joints",
    "variation_shapes",
    "expression_shapes",
    "independent_shapes",
    "bone_properties",
    "texture_channels",
    "hide_collection",
)

# Hard rule: NeckBind must never be re-added to active joint_names.
JOINT_BLOCKED = frozenset({"NeckBind"})

DEFAULT_BONE_PROPERTY_DEFAULTS: dict[str, dict] = {
    "var_iris_shrink": {"min": 0.2, "max": 1.0, "target_bone": "LeftEyeSocketBind"},
    "var_iris_grow": {"min": 0.0, "max": 0.0, "target_bone": "LeftEyeSocketBind"},
    "var_pupil_shrink": {"min": 0.0, "max": 0.5, "target_bone": "LeftEyeSocketBind"},
    "var_pupil_grow": {"min": 0.0, "max": 0.5, "target_bone": "LeftEyeSocketBind"},
}

DEFAULT_INDEPENDENT_DEFAULTS: dict[str, dict] = {
    "nose_male_varGp01G": {"min": 0.0, "max": 0.3, "mirror_sides": False},
}

DEFAULT_TEXTURE_CHANNELS = ("brow", "lash", "lip", "beard", "nose")

DEFAULT_HIDE_COLLECTION_OBJECTS = (
    "_BrowControlShape",
    "_eyeControlShape",
    "_JawControlShape",
    "_LowerCheek",
    "_mouthControlShape",
    "_NoseBSGuideMax",
    "_NoseBSGuideMin",
    "_noseControlShape",
    "_NoseStaticGuideMax",
    "_NoseStaticGuideMin",
    "_UpperCheek",
)

PYTHON_SEEDS: dict[str, list[str]] = {
    "joints": sorted(CHAOS_JOINT_NAMES),
    "variation_shapes": list(VARIATION_SHAPES),
    "expression_shapes": list(EXPRESSION_SHAPES),
    "independent_shapes": list(DEFAULT_INDEPENDENT_DEFAULTS.keys()),
    "bone_properties": list(DEFAULT_BONE_PROPERTY_DEFAULTS.keys()),
    "texture_channels": list(DEFAULT_TEXTURE_CHANNELS),
    "hide_collection": list(DEFAULT_HIDE_COLLECTION_OBJECTS),
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _manifest_path(manifest_id: str) -> Path:
    if manifest_id not in MANIFEST_IDS:
        raise ValueError(f"Unknown manifest: {manifest_id}")
    return MANIFESTS_DIR / f"{manifest_id}.json"


def _empty_manifest(manifest_id: str) -> dict:
    data: dict[str, Any] = {"items": [], "updated_at": _now()}
    if manifest_id == "joints":
        data["blocked"] = sorted(JOINT_BLOCKED)
    if manifest_id == "bone_properties":
        data["defaults"] = dict(DEFAULT_BONE_PROPERTY_DEFAULTS)
    if manifest_id == "independent_shapes":
        data["defaults"] = dict(DEFAULT_INDEPENDENT_DEFAULTS)
    return data


def _load_manifest(manifest_id: str) -> dict:
    path = _manifest_path(manifest_id)
    if not path.exists():
        return _empty_manifest(manifest_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(manifest_id: str, data: dict) -> None:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    path = _manifest_path(manifest_id)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _item_ids(data: dict) -> set[str]:
    return {str(item["id"]) for item in data.get("items", []) if "id" in item}


def register_items(
    manifest_id: str,
    ids: list[str],
    *,
    source: str = "user",
    note: str = "",
) -> dict:
    """Add ids to manifest catalog (no-op for duplicates)."""
    clean = [i.strip() for i in ids if i and i.strip()]
    if not clean:
        return get_manifest(manifest_id)

    data = _load_manifest(manifest_id)
    existing = _item_ids(data)
    blocked = set(data.get("blocked", []))
    for item_id in clean:
        if item_id in blocked or item_id in existing:
            continue
        data.setdefault("items", []).append(
            {"id": item_id, "source": source, "note": note, "added_at": _now()},
        )
    _save_manifest(manifest_id, data)
    return get_manifest(manifest_id)


def get_manifest(manifest_id: str) -> dict:
    data = _load_manifest(manifest_id)
    items = sorted(data.get("items", []), key=lambda x: x.get("id", "").lower())
    return {
        "id": manifest_id,
        "items": items,
        "blocked": sorted(set(data.get("blocked", [])) | (JOINT_BLOCKED if manifest_id == "joints" else set())),
        "defaults": data.get("defaults", {}),
        "updated_at": data.get("updated_at"),
    }


def list_manifests() -> list[dict]:
    return [get_manifest(mid) for mid in MANIFEST_IDS]


def _seed_from_python(manifest_id: str, data: dict) -> None:
    existing = _item_ids(data)
    for item_id in PYTHON_SEEDS.get(manifest_id, []):
        if item_id not in existing:
            data.setdefault("items", []).append(
                {"id": item_id, "source": "python_default", "note": "", "added_at": _now()},
            )


def _scan_profiles(data: dict, manifest_id: str) -> None:
    if not PROFILES_DIR.is_dir():
        return
    existing = _item_ids(data)

    def add_many(ids: list[str], source: str) -> None:
        for item_id in ids:
            if item_id and item_id not in existing:
                data.setdefault("items", []).append(
                    {"id": item_id, "source": source, "note": "", "added_at": _now()},
                )
                existing.add(item_id)

    for profile_dir in PROFILES_DIR.iterdir():
        if not profile_dir.is_dir():
            continue
        cj = profile_dir / "chaos_joints.json"
        if cj.exists() and manifest_id in {"joints", "bone_properties"}:
            raw = json.loads(cj.read_text(encoding="utf-8"))
            if manifest_id == "joints":
                add_many(raw.get("joint_names", []), f"profile:{profile_dir.name}")
            else:
                add_many(list(raw.get("bone_properties", {}).keys()), f"profile:{profile_dir.name}")
        bs = profile_dir / "blendshapes.json"
        if bs.exists() and manifest_id in {"variation_shapes", "expression_shapes", "independent_shapes"}:
            raw = json.loads(bs.read_text(encoding="utf-8"))
            if manifest_id == "variation_shapes":
                add_many(raw.get("variation_shapes", []), f"profile:{profile_dir.name}")
            elif manifest_id == "expression_shapes":
                add_many(raw.get("expression_shapes", []), f"profile:{profile_dir.name}")
            else:
                add_many(list(raw.get("independent_shapes", {}).keys()), f"profile:{profile_dir.name}")
        ts = profile_dir / "texture_swap.json"
        if ts.exists() and manifest_id == "texture_channels":
            raw = json.loads(ts.read_text(encoding="utf-8"))
            add_many(list(raw.get("channels", {}).keys()), f"profile:{profile_dir.name}")
        runner = profile_dir / "runner.json"
        if runner.exists() and manifest_id == "hide_collection":
            raw = json.loads(runner.read_text(encoding="utf-8"))
            add_many(raw.get("hideCollection", []), f"profile:{profile_dir.name}")


def ensure_manifests() -> None:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    for manifest_id in MANIFEST_IDS:
        data = _load_manifest(manifest_id)
        _seed_from_python(manifest_id, data)
        _scan_profiles(data, manifest_id)
        _save_manifest(manifest_id, data)


def ingest_config_file(file_id: str, data: dict) -> None:
    """Register any list/object keys from a saved config into manifests."""
    if file_id == "chaos_joints":
        register_items("joints", data.get("joint_names", []), source="config_save")
        register_items("bone_properties", list(data.get("bone_properties", {}).keys()), source="config_save")
    elif file_id == "blendshapes":
        register_items("variation_shapes", data.get("variation_shapes", []), source="config_save")
        register_items("expression_shapes", data.get("expression_shapes", []), source="config_save")
        register_items("independent_shapes", list(data.get("independent_shapes", {}).keys()), source="config_save")
    elif file_id == "texture_swap":
        register_items("texture_channels", list(data.get("channels", {}).keys()), source="config_save")
    elif file_id == "runner":
        register_items("hide_collection", data.get("hideCollection", []), source="config_save")


def build_registry(profile_name: str) -> dict:
    """Build rerandomize/param picker groups from a profile's config."""
    from . import profiles as prof

    prof.ensure_profiles_layout()
    cj = prof.read_config_file(profile_name, "chaos_joints")
    bs = prof.read_config_file(profile_name, "blendshapes")

    joints = cj.get("joint_names", [])
    joint_set = set(joints)
    channels = ("location", "rotation", "scale")
    axes = ("x", "y", "z")

    def _skip_mirrored_right(joint: str) -> bool:
        if not joint.startswith("Right"):
            return False
        return ("Left" + joint[5:]) in joint_set

    joint_params: list[str] = []
    for joint in joints:
        if _skip_mirrored_right(joint):
            continue
        for ch in channels:
            joint_params.append(f"{joint}.{ch}")
            for ax in axes:
                joint_params.append(f"{joint}.{ch}.{ax}")

    bone_props = list(cj.get("bone_properties", {}).keys())
    var_shapes = bs.get("variation_shapes", [])
    expr_shapes = bs.get("expression_shapes", [])
    indep_shapes = list(bs.get("independent_shapes", {}).keys())

    return {
        "joints": sorted(set(joints)),
        "joint_params": sorted(set(joint_params)),
        "bone_properties": sorted(bone_props),
        "variation_shapes": sorted(var_shapes),
        "expression_shapes": sorted(expr_shapes),
        "independent_shapes": sorted(indep_shapes),
        "rerandomize_suggestions": sorted(
            set(joint_params)
            | {f"property:{p}" for p in bone_props}
            | {f"shape:{s}" for s in var_shapes + expr_shapes + indep_shapes}
            | set(bone_props)
            | set(var_shapes)
            | set(expr_shapes)
        ),
    }

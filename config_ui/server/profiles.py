"""Profile storage, activation, and sync with the live Blender config directory."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from synth_head.core.config import load_config

from .schema import CONFIG_FILE_IDS
from .config_defaults import DEFAULT_CONFIG_FILES, deep_merge_missing

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = PROJECT_ROOT / "data" / "profiles"
ACTIVE_FILE = PROFILES_DIR / "active.json"
LIVE_CONFIG_DIR = PROJECT_ROOT / "data" / "config"
LEGACY_AUTH_HEAD = PROJECT_ROOT / "data" / "config-auth-head"


class ProfileError(Exception):
    pass


def _read_active_name() -> str:
    if not ACTIVE_FILE.exists():
        return "default"
    data = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
    return str(data.get("name", "default"))


def _write_active_name(name: str) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(
        json.dumps({"name": name}, indent=2) + "\n",
        encoding="utf-8",
    )


def _profile_dir(name: str) -> Path:
    safe = name.strip()
    if not safe or safe in {".", ".."} or "/" in safe or "\\" in safe:
        raise ProfileError("Invalid profile name")
    return PROFILES_DIR / safe


def _copy_json_tree(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted(source.glob("*.json")):
        shutil.copy2(src, dest / src.name)


def _ensure_profile_files(profile_path: Path) -> None:
    """Backfill any CONFIG_FILE_IDS JSON missing from *profile_path*."""
    profile_path.mkdir(parents=True, exist_ok=True)
    for file_id in CONFIG_FILE_IDS:
        dest = profile_path / f"{file_id}.json"
        if not dest.exists():
            live = LIVE_CONFIG_DIR / f"{file_id}.json"
            if live.exists():
                shutil.copy2(live, dest)
            elif file_id in DEFAULT_CONFIG_FILES:
                dest.write_text(
                    json.dumps(DEFAULT_CONFIG_FILES[file_id], indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                continue

        defaults = DEFAULT_CONFIG_FILES.get(file_id)
        if defaults is None:
            continue
        data = json.loads(dest.read_text(encoding="utf-8"))
        merged, changed = deep_merge_missing(data, defaults)
        if changed:
            dest.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def _sync_to_live(profile_name: str) -> None:
    src = _profile_dir(profile_name)
    if not src.is_dir():
        raise ProfileError(f"Profile not found: {profile_name}")
    LIVE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for stale in LIVE_CONFIG_DIR.glob("*.json"):
        stale.unlink()
    _copy_json_tree(src, LIVE_CONFIG_DIR)


def ensure_profiles_layout() -> None:
    """Bootstrap profiles/ from legacy layout on first run."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    default_dir = _profile_dir("default")
    if not default_dir.exists() and LIVE_CONFIG_DIR.is_dir():
        _copy_json_tree(LIVE_CONFIG_DIR, default_dir)

    auth_dir = _profile_dir("auth-head")
    if not auth_dir.exists() and LEGACY_AUTH_HEAD.is_dir():
        _copy_json_tree(LEGACY_AUTH_HEAD, auth_dir)

    if not ACTIVE_FILE.exists():
        _write_active_name("default")

    for path in PROFILES_DIR.iterdir():
        if path.is_dir():
            _ensure_profile_files(path)

    active = _read_active_name()
    if not _profile_dir(active).is_dir():
        if default_dir.is_dir():
            _write_active_name("default")
            active = "default"
        else:
            raise ProfileError("No profiles found — add data/config or data/profiles/default")

    _sync_to_live(active)


def list_profiles() -> list[dict]:
    ensure_profiles_layout()
    active = _read_active_name()
    profiles: list[dict] = []
    for path in sorted(PROFILES_DIR.iterdir()):
        if not path.is_dir():
            continue
        json_files = sorted(path.glob("*.json"))
        modified = max(
            (f.stat().st_mtime for f in json_files),
            default=path.stat().st_mtime,
        )
        profiles.append(
            {
                "name": path.name,
                "active": path.name == active,
                "file_count": len(json_files),
                "modified_at": datetime.fromtimestamp(modified, tz=timezone.utc).isoformat(),
            }
        )
    return profiles


def get_active_profile() -> str:
    ensure_profiles_layout()
    return _read_active_name()


def activate_profile(name: str) -> None:
    ensure_profiles_layout()
    if not _profile_dir(name).is_dir():
        raise ProfileError(f"Profile not found: {name}")
    _write_active_name(name)
    _sync_to_live(name)


def create_profile(name: str, source: str | None = None) -> None:
    ensure_profiles_layout()
    dest = _profile_dir(name)
    if dest.exists():
        raise ProfileError(f"Profile already exists: {name}")

    if source:
        src = _profile_dir(source)
        if not src.is_dir():
            raise ProfileError(f"Source profile not found: {source}")
        _copy_json_tree(src, dest)
    elif LIVE_CONFIG_DIR.is_dir():
        _copy_json_tree(LIVE_CONFIG_DIR, dest)
    else:
        dest.mkdir(parents=True)
    activate_profile(name)


def delete_profile(name: str) -> None:
    ensure_profiles_layout()
    target = _profile_dir(name)
    if not target.is_dir():
        raise ProfileError(f"Profile not found: {name}")
    profile_names = [p.name for p in sorted(PROFILES_DIR.iterdir()) if p.is_dir()]
    if len(profile_names) <= 1:
        raise ProfileError("Cannot delete the last profile")
    if name == _read_active_name():
        fallback = next(n for n in profile_names if n != name)
        _write_active_name(fallback)
        _sync_to_live(fallback)
    shutil.rmtree(target)


def rename_profile(old_name: str, new_name: str) -> None:
    ensure_profiles_layout()
    src = _profile_dir(old_name)
    dest = _profile_dir(new_name)
    if not src.is_dir():
        raise ProfileError(f"Profile not found: {old_name}")
    if dest.exists():
        raise ProfileError(f"Profile already exists: {new_name}")
    src.rename(dest)
    if _read_active_name() == old_name:
        _write_active_name(new_name)


def read_config_file(profile: str, file_id: str) -> dict:
    if file_id not in CONFIG_FILE_IDS:
        raise ProfileError(f"Unknown config file: {file_id}")
    path = _profile_dir(profile) / f"{file_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_config_file(profile: str, file_id: str, data: dict) -> None:
    if file_id not in CONFIG_FILE_IDS:
        raise ProfileError(f"Unknown config file: {file_id}")
    if file_id == "chaos_joints" and "joint_names" in data:
        from synth_head.core.variation import sync_mirror_joint_names

        data = {**data, "joint_names": sync_mirror_joint_names(data["joint_names"])}
    profile_path = _profile_dir(profile)
    if not profile_path.is_dir():
        raise ProfileError(f"Profile not found: {profile}")
    path = profile_path / f"{file_id}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if profile == _read_active_name():
        LIVE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, LIVE_CONFIG_DIR / path.name)


def validate_profile(name: str) -> dict:
    ensure_profiles_layout()
    profile_path = _profile_dir(name)
    if not profile_path.is_dir():
        raise ProfileError(f"Profile not found: {name}")
    try:
        cfg = load_config(profile_path, project_root=PROJECT_ROOT / "data")
        return {
            "valid": True,
            "message": "Configuration loaded successfully",
            "frame_count": cfg.runner.frame_count,
            "joint_count": len(cfg.chaos_joint_names),
            "driver_count": len(cfg.drivers.drivers),
        }
    except Exception as exc:
        return {"valid": False, "message": str(exc)}


def validate_constraints(name: str) -> dict:
    from synth_head.core.constraints import ConstraintRules, validate_rule_completeness, validate_rules

    from . import manifests as mf

    ensure_profiles_layout()
    profile_path = _profile_dir(name)
    if not profile_path.is_dir():
        raise ProfileError(f"Profile not found: {name}")
    data = read_config_file(name, "constraints")
    rules = ConstraintRules.from_dict(data)
    known = set(mf.build_registry(name).get("rerandomize_suggestions", []))
    report = validate_rules(rules, known)
    rules_with_issues = []
    for i, rule in enumerate(data.get("relational_rules", [])):
        missing = validate_rule_completeness(rule)
        if missing:
            rules_with_issues.append(
                {
                    "index": i,
                    "title": rule.get("title", ""),
                    "type": rule.get("type", ""),
                    "missing": missing,
                }
            )
    return {
        "stale_keys": report.stale_keys,
        "rules_with_issues": rules_with_issues,
    }

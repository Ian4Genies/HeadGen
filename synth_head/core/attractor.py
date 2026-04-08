"""
Attractor system — pure Python + numpy, no bpy.

Nudges randomly generated head parameters toward a pool of curated
"good head" reference snapshots.  Operates on the same flat
dict[str, float] parameter space used by the constraint engine.
Fully testable with pytest.
"""

from __future__ import annotations

import fnmatch
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .math import quaternion_to_euler_degrees
from .variation import ChaosTransform
from .constraints import flatten_params


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AttractorConfig:
    enabled: bool = True
    debug: bool = False
    attractive_heads_dir: str = "head-attractive"
    min_attractors: int = 2
    max_attractors: int = 5
    max_influence: float = 0.2
    distance_weights: dict[str, float] = field(default_factory=dict)
    exclude_params: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> AttractorConfig:
        return cls(
            enabled=data.get("enabled", True),
            debug=data.get("debug", False),
            attractive_heads_dir=data.get("attractive_heads_dir", "head-attractive"),
            min_attractors=data.get("min_attractors", 2),
            max_attractors=data.get("max_attractors", 5),
            max_influence=data.get("max_influence", 0.2),
            distance_weights=data.get("distance_weights", {}),
            exclude_params=data.get("exclude_params", []),
        )

    def resolve(self, base: Path) -> AttractorConfig:
        """Return a copy with the attractive_heads_dir resolved against *base*."""
        return AttractorConfig(
            enabled=self.enabled,
            debug=self.debug,
            attractive_heads_dir=str((base / self.attractive_heads_dir).resolve()) if self.attractive_heads_dir else "",
            min_attractors=self.min_attractors,
            max_attractors=self.max_attractors,
            max_influence=self.max_influence,
            distance_weights=dict(self.distance_weights),
            exclude_params=list(self.exclude_params),
        )


# ---------------------------------------------------------------------------
# Snapshot → flat-param conversion
# ---------------------------------------------------------------------------

def snapshot_to_flat(
    snapshot: dict,
    joint_names: list[str],
) -> dict[str, float]:
    """Convert an attractive-head snapshot dict into the pipeline's flat param space.

    Handles the quaternion → Euler-degree conversion that differs between
    snapshot format (rotation_quaternion, 4-float wxyz) and the pipeline's
    ChaosTransform (rotation, 3-float xyz degrees).
    """
    chaos_joints = snapshot.get("chaos_joints", {})

    transforms: dict[str, ChaosTransform] = {}
    for name in joint_names:
        if name not in chaos_joints:
            continue
        jdata = chaos_joints[name]

        loc = tuple(jdata.get("location", [0.0, 0.0, 0.0]))
        scale = tuple(jdata.get("scale", [1.0, 1.0, 1.0]))

        quat = jdata.get("rotation_quaternion", [1.0, 0.0, 0.0, 0.0])
        rot = quaternion_to_euler_degrees(tuple(quat))

        transforms[name] = ChaosTransform(
            location=loc,   # type: ignore[arg-type]
            rotation=rot,
            scale=scale,    # type: ignore[arg-type]
        )

    bs_weights: dict[str, float] = {}
    bs_weights.update(snapshot.get("variation_shapes", {}))
    bs_weights.update(snapshot.get("expression_shapes", {}))

    return flatten_params(transforms, bs_weights)


# ---------------------------------------------------------------------------
# Exclude-param matching (supports fnmatch glob patterns)
# ---------------------------------------------------------------------------

def _build_exclude_set(
    exclude_patterns: list[str],
    all_keys: list[str],
) -> frozenset[str]:
    """Expand glob patterns in *exclude_patterns* against *all_keys*."""
    excluded: set[str] = set()
    for pattern in exclude_patterns:
        if "*" in pattern or "?" in pattern or "[" in pattern:
            excluded.update(k for k in all_keys if fnmatch.fnmatch(k, pattern))
        else:
            excluded.add(pattern)
    return frozenset(excluded)


# ---------------------------------------------------------------------------
# Pool cache with incremental manifest
# ---------------------------------------------------------------------------

_DEFAULT_COLOR = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)


class PoolCache:
    """In-memory cache for the attractive-head pool.

    Holds a numpy matrix of flattened head parameters and a parallel color
    matrix (N×4 RGBA) for attractive-color blending.  Both use the same row
    ordering so indices from find_nearest directly index both matrices.
    Module-level singleton persists across operator calls within a session.
    """

    def __init__(self) -> None:
        self.matrix: np.ndarray | None = None
        self.color_matrix: np.ndarray | None = None  # shape (N, 4) RGBA float64
        self.filenames: list[str] = []
        self.param_keys: list[str] = []
        self._dir_path: str = ""

    @property
    def pool_size(self) -> int:
        return len(self.filenames)

    def sync(
        self,
        directory: str | Path,
        joint_names: list[str],
    ) -> dict:
        """Sync cache with the directory.

        Returns a report dict with keys:
          ``changed`` (bool), ``added`` (list[str]), ``removed`` (list[str]),
          ``pool_size`` (int).
        """
        d = Path(directory)
        if not d.is_dir():
            return {"changed": False, "added": [], "removed": [], "pool_size": 0}

        on_disk = {
            p.name for p in d.iterdir()
            if p.suffix == ".json" and not p.name.startswith("_")
        }

        current = set(self.filenames)
        dir_str = str(d.resolve())

        if on_disk == current and dir_str == self._dir_path:
            return {"changed": False, "added": [], "removed": [], "pool_size": self.pool_size}

        added = sorted(on_disk - current)
        removed = sorted(current - on_disk)

        if removed:
            removed_set = set(removed)
            keep_indices = [
                i for i, f in enumerate(self.filenames) if f not in removed_set
            ]
            self.filenames = [self.filenames[i] for i in keep_indices]
            if self.matrix is not None and keep_indices:
                self.matrix = self.matrix[keep_indices]
                self.color_matrix = self.color_matrix[keep_indices] if self.color_matrix is not None else None
            elif not keep_indices:
                self.matrix = None
                self.color_matrix = None

        for fname in added:
            path = d / fname
            with path.open("r", encoding="utf-8") as f:
                snap = json.load(f)
            flat = snapshot_to_flat(snap, joint_names)

            if not self.param_keys:
                self.param_keys = sorted(flat.keys())

            row = np.array(
                [flat.get(k, 0.0) for k in self.param_keys],
                dtype=np.float64,
            )
            if self.matrix is None:
                self.matrix = row.reshape(1, -1)
            else:
                self.matrix = np.vstack([self.matrix, row])

            raw_color = snap.get("skin_color")
            color_row = (
                np.array(raw_color[:4], dtype=np.float64)
                if raw_color and len(raw_color) >= 4
                else _DEFAULT_COLOR.copy()
            )
            if self.color_matrix is None:
                self.color_matrix = color_row.reshape(1, -1)
            else:
                self.color_matrix = np.vstack([self.color_matrix, color_row])

            self.filenames.append(fname)

        self._dir_path = dir_str
        return {
            "changed": True,
            "added": added,
            "removed": removed,
            "pool_size": self.pool_size,
        }


_pool_cache = PoolCache()


def get_pool_cache() -> PoolCache:
    """Return the module-level pool cache singleton."""
    return _pool_cache


# ---------------------------------------------------------------------------
# Manifest file management
# ---------------------------------------------------------------------------

def update_manifest(directory: str | Path) -> None:
    """Write/update _manifest.json listing all snapshot files in *directory*."""
    d = Path(directory)
    if not d.is_dir():
        return
    files = sorted(
        p.name for p in d.iterdir()
        if p.suffix == ".json" and not p.name.startswith("_")
    )
    manifest = {"files": files, "count": len(files)}
    manifest_path = d / "_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def build_range_vectors(
    param_keys: list[str],
    variation_config,
    blendshape_config,
) -> tuple[np.ndarray, np.ndarray]:
    """Build min/max arrays from the generation config for normalization.

    Returns (mins, maxs) each of shape (N_params,).
    For joint params the range comes from the variation overrides.
    For blendshape params, variation shapes use [0, max_variation] and
    expression shapes use [0, expression_max] (with per-shape overrides).
    """
    from .variation import _resolve_range

    ov = variation_config.joint_overrides
    t_max = variation_config.transform_max
    r_max = variation_config.rotate_max
    s_max = variation_config.scale_max

    var_ov = blendshape_config.variation_overrides or {}
    expr_ov = blendshape_config.expression_overrides or {}
    var_set = set(blendshape_config.variation_shapes)
    expr_set = set(blendshape_config.expression_shapes)

    mins = np.zeros(len(param_keys), dtype=np.float64)
    maxs = np.ones(len(param_keys), dtype=np.float64)

    for i, key in enumerate(param_keys):
        parts = key.split(".")
        if len(parts) == 3:
            joint, channel, axis = parts
            channel_globals = {
                "location": t_max,
                "rotation": r_max,
                "scale": s_max,
            }
            g = channel_globals.get(channel, 0.0)
            lo, hi = _resolve_range(joint, channel, g, ov, axis)
            if channel == "scale":
                lo += 1.0
                hi += 1.0
            mins[i] = lo
            maxs[i] = hi
        else:
            if key in var_set:
                cap = var_ov.get(key, blendshape_config.max_variation)
                mins[i] = 0.0
                maxs[i] = float(cap)
            elif key in expr_set:
                cap = expr_ov.get(key, blendshape_config.expression_max)
                mins[i] = 0.0
                maxs[i] = max(float(cap), 0.001)
            else:
                mins[i] = 0.0
                maxs[i] = 1.0

    return mins, maxs


def normalize(
    values: np.ndarray,
    mins: np.ndarray,
    maxs: np.ndarray,
) -> np.ndarray:
    """Normalize values to [0, 1] using provided ranges.

    Handles zero-range columns by leaving them at 0.
    """
    span = maxs - mins
    safe_span = np.where(span == 0.0, 1.0, span)
    return (values - mins) / safe_span


# ---------------------------------------------------------------------------
# Distance & selection
# ---------------------------------------------------------------------------

def find_nearest(
    current_vec: np.ndarray,
    pool_matrix: np.ndarray,
    n: int,
    mins: np.ndarray,
    maxs: np.ndarray,
    distance_weights: np.ndarray | None = None,
) -> np.ndarray:
    """Return indices of the *n* closest pool heads to *current_vec*.

    Both current_vec and pool_matrix are in raw (unnormalized) space.
    Normalization and optional per-param weighting is applied internally.
    """
    norm_current = normalize(current_vec, mins, maxs)
    norm_pool = normalize(pool_matrix, mins, maxs)

    diff = norm_pool - norm_current
    if distance_weights is not None:
        diff = diff * distance_weights
    dists = np.sum(diff ** 2, axis=1)

    n = min(n, len(dists))
    if n >= len(dists):
        return np.arange(len(dists))
    return np.argpartition(dists, n)[:n]


# ---------------------------------------------------------------------------
# Target computation
# ---------------------------------------------------------------------------

def compute_attractor_target(
    pool_matrix: np.ndarray,
    indices: np.ndarray,
    rng: random.Random,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute a weighted-average target vector from selected pool heads.

    Random weights are generated summing to 1.0, so the target is a
    convex combination of the selected attractive heads.

    Returns ``(target_vector, weights)`` so the caller can apply the same
    weights to other per-head data (e.g. color_matrix).
    """
    n = len(indices)
    raw_weights = [rng.random() for _ in range(n)]
    total = sum(raw_weights)
    if total == 0.0:
        weights = np.full(n, 1.0 / n)
    else:
        weights = np.array([w / total for w in raw_weights], dtype=np.float64)

    selected = pool_matrix[indices]
    return weights @ selected, weights


# ---------------------------------------------------------------------------
# Nudge
# ---------------------------------------------------------------------------

def nudge_params(
    current_flat: dict[str, float],
    target_vec: np.ndarray,
    param_keys: list[str],
    max_influence: float,
    excluded: frozenset[str],
) -> dict[str, float]:
    """Move each non-excluded param toward the target by *max_influence* fraction.

    ``new = current + max_influence * (target - current)``
    """
    result = dict(current_flat)
    for i, key in enumerate(param_keys):
        if key in excluded:
            continue
        if key not in result:
            continue
        current_val = result[key]
        target_val = float(target_vec[i])
        result[key] = current_val + max_influence * (target_val - current_val)
    return result


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def attract(
    flat_params: dict[str, float],
    pool: PoolCache,
    config: AttractorConfig,
    variation_config,
    blendshape_config,
    rng: random.Random,
) -> tuple[dict[str, float], list[float] | None, dict | None]:
    """Apply the attractor nudge to *flat_params* and compute an attractive color.

    1. Pick N nearest attractive heads (N randomized per config).
    2. Compute a weighted-average target from those heads (same weights used for both
       shape/joint params and color — color is not included in distance calculations).
    3. Nudge each parameter toward the target by max_influence.
    4. Blend the same pool heads' colors with the same weights → attractive_color.

    Returns ``(nudged_flat, attractive_color, debug_info)``.

    ``attractive_color`` is a plain ``[r, g, b, a]`` list when the attractor is
    active and the pool has color data, otherwise ``None``.

    ``debug_info`` is a dict when ``config.debug`` is True, otherwise ``None``.

    debug_info keys:
      ``n_selected`` (int), ``selected_files`` (list[str]),
      ``mean_abs_delta`` (float) — average absolute change across all params.
    """
    if not config.enabled:
        return flat_params, None, None
    if pool.matrix is None or pool.pool_size == 0:
        return flat_params, None, None

    param_keys = pool.param_keys
    excluded = _build_exclude_set(config.exclude_params, param_keys)

    mins, maxs = build_range_vectors(
        param_keys, variation_config, blendshape_config,
    )

    dw: np.ndarray | None = None
    if config.distance_weights:
        dw = np.array(
            [config.distance_weights.get(k, 1.0) for k in param_keys],
            dtype=np.float64,
        )

    current_vec = np.array(
        [flat_params.get(k, 0.0) for k in param_keys],
        dtype=np.float64,
    )

    n = rng.randint(config.min_attractors, config.max_attractors)
    n = min(n, pool.pool_size)
    if n < 1:
        return flat_params, None, None

    indices = find_nearest(current_vec, pool.matrix, n, mins, maxs, dw)
    target, weights = compute_attractor_target(pool.matrix, indices, rng)
    nudged = nudge_params(flat_params, target, param_keys, config.max_influence, excluded)

    # Blend the same pool heads' colors with the exact same weights.
    attractive_color: list[float] | None = None
    if pool.color_matrix is not None:
        blended = weights @ pool.color_matrix[indices]
        attractive_color = blended.tolist()

    debug_info: dict | None = None
    if config.debug:
        before = np.array([flat_params.get(k, 0.0) for k in param_keys])
        after = np.array([nudged.get(k, 0.0) for k in param_keys])
        mean_abs_delta = float(np.mean(np.abs(after - before)))
        debug_info = {
            "n_selected": n,
            "selected_files": [pool.filenames[i] for i in indices],
            "mean_abs_delta": mean_abs_delta,
        }

    return nudged, attractive_color, debug_info

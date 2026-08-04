"""
Texture overlay swap system — pure Python, no bpy.

Manages pool → sequence directory sync, manifest generation,
selective paging offset calculation, and snapshot round-trip helpers.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Slot / Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TextureSwapSlot:
    """One overlay channel (brow, lash, lip, …).

    ``key`` doubles as the sequence file prefix (e.g. ``"brow"`` →
    ``brow_0001.png``, ``brow_0002.png``, …).
    """

    key: str            # "brow", "lash", "lip"
    node_name: str      # Blender node name, e.g. "brow-sequence"
    material_name: str  # Material that holds the node, e.g. "head_mat"
    pool_path: str      # Absolute path to source pool directory
    sequence_path: str  # Absolute path to output sequence directory
    percentage: float   # Probability of choosing a non-default texture
    enabled: bool = True  # When False, always keys the default (index 1) slot


@dataclass
class TextureSwapConfig:
    """All overlay swap channels, built from ``texture_swap.json``."""

    slots: list[TextureSwapSlot] = field(default_factory=list)
    random_texture_color: bool = True

    @classmethod
    def from_dict(cls, d: dict, default_material: str = "head_mat") -> "TextureSwapConfig":
        """Build from the ``texture_swap.json`` dict.

        Channels are defined as a ``"channels"`` dict, each key being the
        channel name (e.g. ``"brow"``) and the value a struct with::

            {
                "pool_path":     "input-pipeline/texture/brow",
                "sequence_path": "output-pipeline/brow_sequence",
                "node_name":     "brow-sequence",
                "percentage":    1.0,
                "material_name": "head_mat",  // optional, falls back to default_material
                "enabled":       true         // optional, defaults to true
            }

        Adding a new channel requires only a new entry in ``"channels"`` — no
        code changes needed.

        ``random_texture_color`` (top-level, defaults to ``true``) toggles whether
        brow/lash/beard get independently randomized colors per frame, or all
        three share one randomized color per frame (the pre-split behavior).
        """
        slots: list[TextureSwapSlot] = []
        for channel, cfg in sorted(d.get("channels", {}).items()):
            slots.append(TextureSwapSlot(
                key=channel,
                node_name=cfg.get("node_name", ""),
                material_name=cfg.get("material_name", default_material),
                pool_path=cfg.get("pool_path", ""),
                sequence_path=cfg.get("sequence_path", ""),
                percentage=float(cfg.get("percentage", 0.5)),
                enabled=bool(cfg.get("enabled", True)),
            ))

        return cls(
            slots=slots,
            random_texture_color=bool(d.get("random_texture_color", True)),
        )

    def resolve(self, base: Path) -> "TextureSwapConfig":
        """Return a copy with all relative paths resolved against *base*."""
        resolved: list[TextureSwapSlot] = []
        for slot in self.slots:
            resolved.append(TextureSwapSlot(
                key=slot.key,
                node_name=slot.node_name,
                material_name=slot.material_name,
                pool_path=str((base / slot.pool_path).resolve()) if slot.pool_path else "",
                sequence_path=str((base / slot.sequence_path).resolve()) if slot.sequence_path else "",
                percentage=slot.percentage,
                enabled=slot.enabled,
            ))
        return TextureSwapConfig(slots=resolved, random_texture_color=self.random_texture_color)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "_manifest.json"


@dataclass
class SequenceManifest:
    """In-memory view of a sequence directory's ``_manifest.json``.

    ``entries`` maps 1-based frame index to a display name::

        {1: "default", 2: "textureA.png", 3: "textureB.png"}

    Index 1 is always ``"default"`` (the static transparent frame).
    Indices 2..N correspond to sorted pool files.
    Pool file names (not indexes) are what gets saved into snapshots,
    so they remain valid even when the pool changes between sessions.
    """

    pool_files: list[str]    # sorted original pool filenames
    frame_count: int          # total frames including default (index 1)
    entries: dict[int, str]   # {1: "default", 2: "textureA.png", …}

    def name_at_index(self, index: int) -> str | None:
        """Return the name for *index*, or ``None`` if out of range."""
        return self.entries.get(index)

    def index_of_name(self, name: str) -> int | None:
        """Return the index for *name*, or ``None`` if not found."""
        for idx, n in self.entries.items():
            if n == name:
                return idx
        return None


def load_manifest(sequence_path: str | Path) -> SequenceManifest | None:
    """Read ``_manifest.json`` from *sequence_path*.  Returns ``None`` if absent."""
    p = Path(sequence_path) / MANIFEST_FILENAME
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    entries = {int(k): v for k, v in raw.get("entries", {}).items()}
    return SequenceManifest(
        pool_files=raw.get("pool_files", []),
        frame_count=raw.get("frame_count", len(entries)),
        entries=entries,
    )


def _write_manifest(sequence_path: str | Path, manifest: SequenceManifest) -> None:
    p = Path(sequence_path) / MANIFEST_FILENAME
    raw = {
        "pool_files": manifest.pool_files,
        "frame_count": manifest.frame_count,
        "entries": {str(k): v for k, v in manifest.entries.items()},
    }
    with p.open("w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Default PNG  (transparent RGBA, stdlib only — no Pillow, no bpy)
# ---------------------------------------------------------------------------

def _make_transparent_png(width: int = 4, height: int = 4) -> bytes:
    """Return the bytes of a minimal transparent RGBA PNG using only stdlib.

    Used to (re)create ``prefix_0001.png`` when it is missing from the
    sequence directory.  The image is *width* × *height* pixels, all fully
    transparent (alpha = 0).
    """
    def _chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    # IHDR: width, height, bit-depth=8, color-type=6 (RGBA), compress/filter/interlace=0
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    # IDAT: one scanline per row, filter byte 0x00 + RGBA pixels (all zero)
    row = b"\x00" + b"\x00\x00\x00\x00" * width
    idat = zlib.compress(row * height)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# Sequence file naming
# ---------------------------------------------------------------------------

def sequence_prefix(slot: TextureSwapSlot) -> str:
    """The filename prefix for sequence files in this slot (e.g. ``"brow"``)."""
    return slot.key


def sequence_filename(prefix: str, index: int, ext: str = ".png") -> str:
    """Return the canonical filename for one sequence frame.

    Example: ``sequence_filename("brow", 2)`` → ``"brow_0002.png"``.
    """
    return f"{prefix}_{index:04d}{ext}"


# ---------------------------------------------------------------------------
# Pool file discovery
# ---------------------------------------------------------------------------

_IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".tga", ".tiff", ".tif"})

_INDEX_PATTERN = re.compile(r"_(\d{4})\.[^.]+$", re.IGNORECASE)


def _collect_pool_files(pool_path: str | Path) -> list[str]:
    """Return a sorted list of image filenames in *pool_path*.

    Returns an empty list when the directory does not exist.
    """
    p = Path(pool_path)
    if not p.is_dir():
        return []
    return sorted(
        f.name for f in p.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
    )


# ---------------------------------------------------------------------------
# Sequence rebuild
# ---------------------------------------------------------------------------

def rebuild_sequence(slot: TextureSwapSlot) -> SequenceManifest:
    """Rebuild the sequence directory from the current pool contents.

    Behaviour:
      - Creates the sequence directory if it does not exist.
      - Deletes only pool-derived files (index ≥ 2) matching the
        ``{prefix}_####.ext`` naming convention.
      - Writes ``{prefix}_0001.png`` (transparent RGBA) **only** when it
        is missing — this file is static and protected.
      - Copies pool files in sorted order as
        ``{prefix}_0002.png``, ``{prefix}_0003.png``, …
      - Writes ``_manifest.json``.

    Returns the newly constructed :class:`SequenceManifest`.
    """
    seq_dir = Path(slot.sequence_path)
    seq_dir.mkdir(parents=True, exist_ok=True)

    prefix = sequence_prefix(slot)
    prefix_lower = prefix.lower()

    # Remove only pool-derived files (index >= 2)
    for f in list(seq_dir.iterdir()):
        if not f.is_file():
            continue
        stem_lower = f.stem.lower()
        if not stem_lower.startswith(prefix_lower + "_"):
            continue
        m = _INDEX_PATTERN.search(f.name)
        if m and int(m.group(1)) >= 2:
            f.unlink()

    # Ensure the static default frame exists (never overwritten if present)
    default_file = seq_dir / sequence_filename(prefix, 1)
    if not default_file.exists():
        default_file.write_bytes(_make_transparent_png())

    # Copy pool files in sorted order starting at index 2
    pool_files = _collect_pool_files(slot.pool_path)
    entries: dict[int, str] = {1: "default"}
    for i, fname in enumerate(pool_files, start=2):
        dst = seq_dir / sequence_filename(prefix, i)
        shutil.copy2(Path(slot.pool_path) / fname, dst)
        entries[i] = fname

    manifest = SequenceManifest(
        pool_files=pool_files,
        frame_count=len(entries),
        entries=entries,
    )
    _write_manifest(seq_dir, manifest)
    return manifest


def ping_and_sync_sequence(slot: TextureSwapSlot) -> SequenceManifest:
    """Compare the pool directory to the stored manifest; rebuild if different.

    Returns the current (possibly freshly rebuilt) :class:`SequenceManifest`.
    """
    existing = load_manifest(slot.sequence_path)
    pool_files = _collect_pool_files(slot.pool_path)

    if existing is not None and existing.pool_files == pool_files:
        return existing

    return rebuild_sequence(slot)


# ---------------------------------------------------------------------------
# Selective paging helpers
# ---------------------------------------------------------------------------

def pick_texture_index(
    manifest: SequenceManifest,
    percentage: float,
    rng: random.Random,
) -> int:
    """Return a 1-based sequence frame index for one variation frame.

    - Index 1 → default (transparent).
    - Indices 2..N → pool textures chosen uniformly at random.
    - ``percentage`` is the probability of returning a non-default index.
    - Always returns 1 when no pool textures exist (``frame_count == 1``).
    """
    if manifest.frame_count <= 1:
        return 1
    if rng.random() > percentage:
        return 1
    return rng.randint(2, manifest.frame_count)


def calc_offset(
    desired_frame: int,
    current_frame: int,
    start_frame: int = 1,
) -> int:
    """Compute the image sequence node ``frame_offset`` to display *desired_frame*.

    Blender computes the shown file as::

        file_shown = (current_frame - start_frame + 1) + offset   [clamp happens first]

    Rearranged to solve for offset::

        offset = desired_frame - (current_frame - start_frame + 1)

    With ``start_frame`` always fixed at 1 for this system::

        offset = desired_frame - current_frame

    NOTE: ``frame_duration`` on the node must be set larger than the maximum
    timeline frame so Blender's internal clamp never fires before the offset
    is applied.  Use ``runner.frame_count + 100`` when configuring the node.
    """
    return desired_frame - (current_frame - start_frame + 1)


def name_from_current_offset(
    offset: int,
    current_frame: int,
    manifest: SequenceManifest,
    start_frame: int = 1,
) -> str:
    """Infer which pool entry name is showing from the node's current offset.

    Used when saving a snapshot — reads the offset currently on the node
    and converts it back to a stable pool filename (or ``"default"``).

    Returns ``"default"`` when the computed index is absent from the manifest.
    """
    image_index = (current_frame - start_frame + 1) + offset
    name = manifest.name_at_index(image_index)
    return name if name is not None else "default"


def offset_from_name(
    name: str,
    current_frame: int,
    manifest: SequenceManifest,
    start_frame: int = 1,
) -> int | None:
    """Compute the ``frame_offset`` required to display *name* on *current_frame*.

    Used when loading a snapshot — looks up the pool filename in the manifest
    and returns the offset to key onto the node.

    Returns ``None`` if *name* is not present in the manifest (emit a warning
    and skip in the caller).
    """
    index = manifest.index_of_name(name)
    if index is None:
        return None
    return calc_offset(index, current_frame, start_frame)

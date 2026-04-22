"""Move loose .glb and .json files in data/final-output into their frame_NNNN folders.

Usage:
    python scripts/organize_final_output.py              # dry-run (default)
    python scripts/organize_final_output.py --apply      # actually move files
    python scripts/organize_final_output.py --root PATH  # override root dir

File name conventions handled:
    final_frameNNN_YYYYMMDD_HHMMSS.json  ->  frame_{NNNN (zero-padded)}/
    frame_NNNN.glb                       ->  frame_NNNN/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

JSON_RE = re.compile(r"^final_frame(\d{3,4})_\d+_\d+\.json$")
GLB_RE = re.compile(r"^frame_(\d{4})\.glb$")


def target_folder(root: Path, filename: str) -> Path | None:
    m = JSON_RE.match(filename)
    if m:
        return root / f"frame_{int(m.group(1)):04d}"
    m = GLB_RE.match(filename)
    if m:
        return root / f"frame_{m.group(1)}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "final-output",
        help="Directory containing loose files and frame_NNNN subfolders.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this flag, only prints planned moves.",
    )
    args = parser.parse_args()

    root: Path = args.root
    if not root.is_dir():
        print(f"[error] root is not a directory: {root}", file=sys.stderr)
        return 1

    planned: list[tuple[Path, Path]] = []
    unmatched: list[Path] = []
    missing_dirs: set[Path] = set()

    for entry in sorted(root.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in (".glb", ".json"):
            continue

        dest_dir = target_folder(root, entry.name)
        if dest_dir is None:
            unmatched.append(entry)
            continue
        if not dest_dir.is_dir():
            missing_dirs.add(dest_dir)
            continue
        planned.append((entry, dest_dir / entry.name))

    for entry in unmatched:
        print(f"[skip] unrecognised name: {entry.name}")
    for d in sorted(missing_dirs):
        print(f"[skip] target folder missing: {d.name}")

    mode = "MOVE" if args.apply else "PLAN"
    for src, dst in planned:
        if dst.exists():
            print(f"[{mode}] skip (dest exists): {src.name} -> {dst.relative_to(root)}")
            continue
        print(f"[{mode}] {src.name} -> {dst.relative_to(root)}")
        if args.apply:
            shutil.move(str(src), str(dst))

    print()
    print(f"Summary: {len(planned)} files to move, "
          f"{len(unmatched)} unmatched, {len(missing_dirs)} missing target dirs.")
    if not args.apply:
        print("Dry-run only. Re-run with --apply to perform the moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

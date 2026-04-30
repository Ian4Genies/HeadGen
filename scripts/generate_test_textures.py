"""
Generate 500 1x1 pixel PNG textures with random high-saturation / bright colors
into data/input-pipeline/texture/test-sequence-L and test-sequence-R.

Files are named frame_0001.png through frame_0500.png.
Colors are guaranteed to be bright (high value) and saturated (no dark or grey tones).
"""

import random
import colorsys
import struct
import zlib
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

OUTPUT_DIRS = [
    os.path.join(REPO_ROOT, "data", "input-pipeline", "texture", "test-sequence-L"),
    os.path.join(REPO_ROOT, "data", "input-pipeline", "texture", "test-sequence-R"),
]

NUM_FRAMES = 500


def random_bright_color() -> tuple[int, int, int]:
    """Return an (R, G, B) tuple with high saturation and high brightness."""
    hue = random.random()
    saturation = random.uniform(0.7, 1.0)
    value = random.uniform(0.85, 1.0)
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return int(r * 255), int(g * 255), int(b * 255)


def write_1x1_png(path: str, r: int, g: int, b: int) -> None:
    """Write a minimal 1x1 RGB PNG file without external dependencies."""

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB), rest=0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b"IHDR", ihdr_data)

    # IDAT: one scanline with filter byte 0 followed by R G B
    raw_row = bytes([0, r, g, b])
    compressed = zlib.compress(raw_row, 9)
    idat = png_chunk(b"IDAT", compressed)

    iend = png_chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(signature + ihdr + idat + iend)


def main() -> None:
    for out_dir in OUTPUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        label = os.path.basename(out_dir)
        print(f"Writing {NUM_FRAMES} textures to: {out_dir}")
        for i in range(1, NUM_FRAMES + 1):
            r, g, b = random_bright_color()
            filename = f"frame_{i:04d}.png"
            write_1x1_png(os.path.join(out_dir, filename), r, g, b)
        print(f"  Done: {label}")

    print(f"\nFinished. {NUM_FRAMES} frames written to each of {len(OUTPUT_DIRS)} directories.")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Generate a minimal valid .ico file without PIL (for tauri-build).

Produces a 32x32 32bpp icon with a simple green bolt on dark background —
enough for the Windows resource file tauri-build requires in Phase 1.
"""
import struct
import sys
from pathlib import Path


def make_ico(path: Path, size: int = 32) -> None:
    # 1. BGRA pixel data (bottom-up rows), 32bpp.
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            # Dark panel background; green bolt-ish diagonal.
            in_bolt = (x + y) > size * 0.55 and abs(x - y) < size * 0.25
            if in_bolt:
                b, g, r, a = 0x72, 0xA5, 0x2F, 255
            else:
                b, g, r, a = 0x14, 0x18, 0x0B, 255
            row.append(struct.pack("BBBB", b, g, r, a))
        rows.append(b"".join(row))
    pixels = b"".join(reversed(rows))  # bottom-up

    # 2. AND mask (1bpp, all opaque -> zeros), padded to 32-bit rows.
    mask_row_bytes = (size + 7) // 8
    mask_row_padded = ((mask_row_bytes + 3) // 4) * 4
    mask = b"\x00" * (mask_row_padded * size)

    # 3. BITMAPINFOHEADER (40 bytes) + pixel data + mask.
    header = struct.pack(
        "<IiiHHIIiiII",
        40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0,
    )
    image = header + pixels + mask

    # 4. ICO directory: 1 image.
    directory = struct.pack(
        "<HHBBBBHHII",
        0, 1, size, size, 0, 0, 1, 32, len(image), 22,
    )
    path.write_bytes(directory + image)
    print(f"wrote {path} ({len(directory) + len(image)} bytes)")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("icon.ico")
    make_ico(target)

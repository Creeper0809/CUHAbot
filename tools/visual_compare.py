#!/usr/bin/env python3
"""Compare a Discord screenshot to an approved Golden without updating it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def dhash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            value <<= 1
            value |= pixels[row * 9 + column] > pixels[row * 9 + column + 1]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("actual", type=Path)
    parser.add_argument("golden", type=Path)
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--mask", action="append", default=[], help="x,y,width,height")
    parser.add_argument("--max-dhash", type=int, default=8)
    parser.add_argument("--max-changed", type=float, default=0.03)
    args = parser.parse_args()

    actual = Image.open(args.actual).convert("RGB")
    golden = Image.open(args.golden).convert("RGB")
    if actual.size != golden.size:
        print(json.dumps({"passed": False, "reason": "size_mismatch", "actual": actual.size, "golden": golden.size}))
        return 1

    for raw in args.mask:
        x, y, width, height = (int(value) for value in raw.split(","))
        box = (x, y, x + width, y + height)
        ImageDraw.Draw(actual).rectangle(box, fill=(0, 0, 0))
        ImageDraw.Draw(golden).rectangle(box, fill=(0, 0, 0))

    distance = (dhash(actual) ^ dhash(golden)).bit_count()
    diff = ImageChops.difference(actual, golden)
    changed = sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0))
    ratio = changed / (actual.width * actual.height)
    args.diff.parent.mkdir(parents=True, exist_ok=True)
    diff.save(args.diff)
    passed = distance <= args.max_dhash and ratio <= args.max_changed
    print(json.dumps({
        "passed": passed,
        "dhash_distance": distance,
        "changed_pixel_ratio": ratio,
        "diff_path": str(args.diff),
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

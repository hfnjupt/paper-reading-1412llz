#!/usr/bin/env python3
"""Crop an exact rectangular region from a rendered paper page."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("left", type=int)
    parser.add_argument("top", type=int)
    parser.add_argument("right", type=int)
    parser.add_argument("bottom", type=int)
    parser.add_argument("--figure-id")
    parser.add_argument("--page", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.image.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"Image not found: {source}")
    if output.exists():
        raise SystemExit(f"Output already exists; choose a new filename: {output}")
    with Image.open(source) as image:
        width, height = image.size
        box = (args.left, args.top, args.right, args.bottom)
        if not (0 <= args.left < args.right <= width and 0 <= args.top < args.bottom <= height):
            raise SystemExit(f"Crop {box} is outside image bounds {(width, height)}")
        cropped = image.crop(box)
        output.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output, format="PNG", optimize=False)
        result = {
            "source": str(source),
            "output": str(output),
            "source_size": [width, height],
            "crop_box": list(box),
            "output_size": list(cropped.size),
            "figure_id": args.figure_id,
            "pdf_page": args.page,
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

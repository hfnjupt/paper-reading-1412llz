#!/usr/bin/env python3
"""Render selected PDF pages to high-resolution PNG files with Poppler."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--pdftoppm", type=Path, help="Explicit Poppler pdftoppm executable")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf = args.pdf.resolve()
    output_dir = args.output_dir.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")
    if args.first < 1 or (args.last is not None and args.last < args.first):
        raise SystemExit("Invalid page range")
    if not 72 <= args.dpi <= 600:
        raise SystemExit("DPI must be between 72 and 600")
    executable = str(args.pdftoppm.resolve()) if args.pdftoppm else shutil.which("pdftoppm")
    if not executable:
        raise SystemExit("pdftoppm was not found; use the Codex bundled Poppler runtime")
    if args.pdftoppm and not args.pdftoppm.is_file():
        raise SystemExit(f"pdftoppm not found: {args.pdftoppm}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.glob("page-*.png")):
        raise SystemExit("Output directory already contains rendered pages; choose a fresh directory")
    prefix = output_dir / "page"
    command = [executable, "-png", "-r", str(args.dpi), "-f", str(args.first)]
    if args.last is not None:
        command.extend(["-l", str(args.last)])
    command.extend([str(pdf), str(prefix)])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or f"pdftoppm failed with code {completed.returncode}")
    files = sorted(str(path) for path in output_dir.glob("page-*.png"))
    print(json.dumps({"pdf": str(pdf), "dpi": args.dpi, "files": files}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

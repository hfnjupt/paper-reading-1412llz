#!/usr/bin/env python3
"""Build or resume a deterministic manifest for a folder of PDFs."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matches(path: Path, root: Path, patterns: list[str]) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reading-manifest.json"))
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--include", action="append", default=[], help="Glob; may be repeated")
    parser.add_argument("--exclude", action="append", default=[], help="Glob; may be repeated")
    parser.add_argument("--mode", choices=("deep", "coarse"), default="coarse")
    parser.add_argument("--order", choices=("name", "path", "mtime"), default="name")
    parser.add_argument("--force", action="store_true", help="Discard resumable states in an existing manifest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.folder.resolve()
    if not root.is_dir():
        raise SystemExit(f"Folder not found: {root}")

    candidates = list(root.rglob("*") if args.recursive else root.iterdir())
    candidates = [path for path in candidates if path.is_file() and path.suffix.casefold() == ".pdf"]

    if args.order == "mtime":
        candidates.sort(key=lambda path: (path.stat().st_mtime_ns, natural_key(path.name)))
    elif args.order == "path":
        candidates.sort(key=lambda path: natural_key(path.relative_to(root).as_posix()))
    else:
        candidates.sort(key=lambda path: natural_key(path.name))

    previous: dict[tuple[str, str], dict[str, object]] = {}
    output = args.output.resolve()
    if output.exists() and not args.force:
        try:
            old = json.loads(output.read_text(encoding="utf-8"))
            if old.get("source_folder") != str(root):
                raise ValueError("Existing manifest belongs to another folder; choose a new output")
            previous = {(str(item.get("source_path")), str(item.get("sha256"))): item for item in old["items"]}
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"Cannot safely resume manifest: {error}. Inspect it or choose a new output.")

    items: list[dict[str, object]] = []
    first_by_hash: dict[str, str] = {}
    for index, path in enumerate(candidates, start=1):
        relative = path.relative_to(root).as_posix()
        hash_error = None
        try:
            digest = sha256(path)
        except OSError as error:
            digest = None
            hash_error = str(error)
        old = previous.get((str(path), str(digest)), {})
        status = str(old.get("status", "pending"))
        selection = str(old.get("selection", "included"))
        reason = str(old.get("selection_reason", "matched folder filters"))
        # Re-evaluate mechanical exclusions, retaining explicit semantic decisions.
        if reason.startswith(("duplicate of ", "filename filter:")):
            selection, reason, status = "included", "matched folder filters", "pending"
        if args.include and not matches(path, root, args.include):
            selection, reason = "excluded", "filename filter: did not match include patterns"
        if args.exclude and matches(path, root, args.exclude):
            selection, reason = "excluded", "filename filter: matched exclude patterns"
        duplicate_of = first_by_hash.get(digest) if digest and selection == "included" else None
        if digest and selection == "included":
            first_by_hash.setdefault(digest, relative)
        if duplicate_of:
            selection, reason = "excluded", f"duplicate of {duplicate_of}"
        if selection == "excluded":
            status = "skipped"
        elif hash_error:
            status = "read_failed"
        elif status == "in_progress":
            status = "pending"
        output_path = old.get("output_path")
        if status == "completed":
            artifact = Path(str(output_path)) if output_path else None
            if artifact and not artifact.is_absolute():
                artifact = output.parent / artifact
            if not artifact or not artifact.exists():
                status = "pending"
        items.append(
            {
                "order": index,
                "source_path": str(path),
                "relative_path": relative,
                "sha256": digest,
                "title_guess": path.stem,
                "selection": selection,
                "selection_reason": reason,
                "mode": old.get("mode", args.mode),
                "status": status,
                "read_scope": old.get("read_scope"),
                "output_path": output_path,
                "error": hash_error or old.get("error"),
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_folder": str(root),
        "recursive": args.recursive,
        "order": args.order,
        "mode": args.mode,
        "include": args.include,
        "exclude": args.exclude,
        "items": items,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2))
    try:
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"output": str(output), "items": len(items), "included": sum(i["selection"] == "included" for i in items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

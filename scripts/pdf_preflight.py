#!/usr/bin/env python3
"""Inspect a PDF before claiming any full-text reading scope."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")

    result: dict[str, object] = {
        "path": str(pdf),
        "sha256": file_hash(pdf),
        "size_bytes": pdf.stat().st_size,
        "valid": False,
    }
    try:
        reader = PdfReader(str(pdf), strict=False)
        result["encrypted"] = bool(reader.is_encrypted)
        if reader.is_encrypted and reader.decrypt("") == 0:
            result.update({"status": "PDF_INVALID", "error": "encrypted PDF requires a password"})
        else:
            char_counts: list[int] = []
            extraction_errors: list[dict[str, object]] = []
            for number, page in enumerate(reader.pages, start=1):
                try:
                    char_counts.append(len((page.extract_text() or "").strip()))
                except Exception as exc:  # pypdf exposes varied parser exceptions
                    char_counts.append(0)
                    extraction_errors.append({"page": number, "error": str(exc)})
            page_count = len(reader.pages)
            text_pages = sum(count >= 40 for count in char_counts)
            coverage = text_pages / page_count if page_count else 0.0
            if page_count == 0:
                status = "PDF_INVALID"
                quality = "none"
            elif coverage == 0:
                status = "OCR_REQUIRED"
                quality = "none"
            elif coverage < 0.7:
                status = "OCR_REQUIRED"
                quality = "partial"
            else:
                status = "LOCAL_READY"
                quality = "usable"
            metadata = reader.metadata or {}
            result.update(
                {
                    "valid": page_count > 0,
                    "status": status,
                    "page_count": page_count,
                    "pages_with_text": text_pages,
                    "text_coverage_ratio": round(coverage, 4),
                    "text_layer_quality": quality,
                    "char_counts_by_page": char_counts,
                    "extraction_errors": extraction_errors,
                    "metadata": {
                        "title": metadata.get("/Title"),
                        "author": metadata.get("/Author"),
                        "subject": metadata.get("/Subject"),
                    },
                }
            )
    except Exception as exc:
        result.update({"status": "PDF_INVALID", "error": str(exc)})

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "LOCAL_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())

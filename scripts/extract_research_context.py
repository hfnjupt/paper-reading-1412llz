#!/usr/bin/env python3
"""Extract user-provided research context as untrusted text data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def extract_docx(path: Path) -> tuple[list[dict[str, str]], list[list[list[str]]], list[dict]]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    paragraphs, tables, blocks = [], [], []
    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            paragraph = Paragraph(element, document)
            if paragraph.text.strip():
                item = {"style": paragraph.style.name if paragraph.style else "", "text": paragraph.text}
                paragraphs.append(item)
                blocks.append({"kind": "paragraph", **item})
        elif element.tag.endswith("}tbl"):
            table = Table(element, document)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            tables.append(rows)
            blocks.append({"kind": "table", "rows": rows})
    return paragraphs, tables, blocks


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"Context file not found: {source}")
    suffix = source.suffix.casefold()
    if suffix == ".docx":
        paragraphs, tables, blocks = extract_docx(source)
        kind = "docx"
    elif suffix in {".md", ".txt"}:
        try:
            text = source.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            raise SystemExit("Context text must be UTF-8; convert its encoding explicitly before retrying")
        paragraphs = [{"style": "", "text": block.strip()} for block in text.splitlines() if block.strip()]
        tables = []
        blocks = [{"kind": "paragraph", **item} for item in paragraphs]
        kind = suffix.lstrip(".")
    else:
        raise SystemExit("Supported context types: .docx, .md, .txt")

    combined_parts = []
    for block in blocks:
        if block["kind"] == "paragraph":
            combined_parts.append(block["text"])
        else:
            combined_parts.extend(" | ".join(row) for row in block["rows"])
    result = {
        "source": str(source),
        "kind": kind,
        "untrusted_data": True,
        "paragraphs": paragraphs,
        "tables": tables,
        "blocks": blocks,
        "combined_text": "\n".join(combined_parts),
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

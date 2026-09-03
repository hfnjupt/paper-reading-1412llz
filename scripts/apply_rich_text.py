#!/usr/bin/env python3
"""Add verified partial-bold runs to the builder's new XLSX via standard OOXML.

The workbook's values and layout are authored by artifact-tool. This helper
only changes text styling in B/F, and refuses any change to the cell text.
"""

import argparse
import io
import json
import os
from pathlib import Path
import posixpath
import re
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML = "http://www.w3.org/XML/1998/namespace"


def tag(name):
    return f"{{{NS}}}{name}"


def text_value(cell, shared):
    if cell.find(tag("f")) is not None:
        raise ValueError(f"Cannot modify formula cell {cell.get('r')}")
    if cell.get("t") == "s":
        return shared[int(cell.findtext(tag("v")))]
    if cell.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f"{tag('is')}//{tag('t')}"))
    return cell.findtext(tag("v")) or ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    args = parser.parse_args()
    workbook_path = args.workbook.resolve(strict=True)
    if workbook_path.suffix.lower() != ".xlsx":
        raise ValueError("Expected a newly generated .xlsx workbook")
    plan = json.loads(args.runs.read_text(encoding="utf-8"))
    if not isinstance(plan, list) or not plan:
        raise ValueError("Expected a nonempty list of rich-text cell plans")
    seen = set()
    for item in plan:
        address = item.get("cell", "")
        if not re.fullmatch(r"[BF][1-9][0-9]*", address) or int(address[1:]) < 2 or address in seen:
            raise ValueError(f"Invalid or repeated B/F body cell: {address}")
        seen.add(address)
        runs = item.get("runs")
        if not isinstance(runs, list) or not runs:
            raise ValueError(f"Empty runs in {address}")
        for run in runs:
            if not isinstance(run.get("text"), str) or not isinstance(run.get("bold", False), bool):
                raise ValueError(f"Invalid run in {address}")

    with ZipFile(workbook_path) as archive:
        entries = archive.infolist()
        data = {entry.filename: archive.read(entry) for entry in entries}
        archive_comment = archive.comment
    book = ET.fromstring(data["xl/workbook.xml"])
    sheets = book.findall(f"{tag('sheets')}/{tag('sheet')}")
    if len(sheets) != 1 or sheets[0].get("name") != "论文粗读":
        raise ValueError("Helper only supports the builder's single-sheet 论文粗读 workbook")
    relation_id = sheets[0].get(f"{{{REL}}}id")
    relationships = ET.fromstring(data["xl/_rels/workbook.xml.rels"])
    relation = next(node for node in relationships if node.get("Id") == relation_id)
    if relation.get("TargetMode") == "External":
        raise ValueError("External worksheet target is not supported")
    target = relation.get("Target")
    sheet_path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
    raw_sheet = data[sheet_path]
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(raw_sheet), events=["start-ns"]):
        if not re.fullmatch(r"ns[0-9]+", prefix):
            ET.register_namespace(prefix, uri)
    ET.register_namespace("", NS)
    sheet = ET.fromstring(raw_sheet)
    shared_root = ET.fromstring(data["xl/sharedStrings.xml"]) if "xl/sharedStrings.xml" in data else None
    shared = [] if shared_root is None else ["".join(node.text or "" for node in item.iter(tag("t"))) for item in shared_root.findall(tag("si"))]
    cell_path = f"{tag('sheetData')}/{tag('row')}/{tag('c')}"
    cells = {node.get("r"): node for node in sheet.findall(cell_path)}
    for item in plan:
        cell = cells[item["cell"]]
        expected_text = "".join(run["text"] for run in item["runs"])
        if text_value(cell, shared) != expected_text:
            raise ValueError(f"Plain text mismatch in {item['cell']}; refusing replacement")
        for child in list(cell):
            if child.tag in (tag("v"), tag("is")):
                cell.remove(child)
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, tag("is"))
        for run in item["runs"]:
            element = ET.SubElement(inline, tag("r"))
            properties = ET.SubElement(element, tag("rPr"))
            ET.SubElement(properties, tag("rFont"), {"val": "等线"})
            ET.SubElement(properties, tag("b"), {"val": "1" if run.get("bold", False) else "0"})
            ET.SubElement(properties, tag("sz"), {"val": "14"})
            ET.SubElement(properties, tag("color"), {"rgb": "FF222222"})
            ET.SubElement(element, tag("t"), {f"{{{XML}}}space": "preserve"}).text = run["text"]
    data[sheet_path] = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
    with tempfile.NamedTemporaryFile(dir=workbook_path.parent, suffix=".xlsx", prefix="richtext-", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with ZipFile(temporary_path, "w") as archive:
            for entry in entries:
                archive.writestr(entry, data[entry.filename])
            archive.comment = archive_comment
        with ZipFile(temporary_path) as archive:
            if archive.testzip() is not None:
                raise ValueError("XLSX archive verification failed")
            verified = ET.fromstring(archive.read(sheet_path))
            verified_cells = {node.get("r"): node for node in verified.findall(cell_path)}
            for item in plan:
                runs = verified_cells[item["cell"]].findall(f"{tag('is')}/{tag('r')}")
                actual = [{"text": run.findtext(tag("t")) or "", "bold": run.find(f"{tag('rPr')}/{tag('b')}").get("val") == "1"} for run in runs]
                expected = [{"text": run["text"], "bold": run.get("bold", False)} for run in item["runs"]]
                if actual != expected:
                    raise ValueError(f"Rich-text verification failed for {item['cell']}")
        os.replace(temporary_path, workbook_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(json.dumps({"verified": True, "cells": len(plan), "bold_runs": sum(run.get("bold", False) for item in plan for run in item["runs"]), "plain_text_preserved": True}))


if __name__ == "__main__":
    main()

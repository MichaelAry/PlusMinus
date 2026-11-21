#!/usr/bin/env python3
"""Export portable Studio 4 QSettings without modifying the old preferences.
Usage: python scripts/export-studio4-settings.py --output studio4-settings.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QSettings
except ImportError as exc:
    raise SystemExit("Use the existing Studio 4 PySide6 environment: " + str(exc))

def portable(settings: QSettings) -> dict:
    def value(key, default=None):
        item = settings.value(key, default)
        if isinstance(item, (list, tuple)):
            return [str(part) for part in item]
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        return str(item)
    files = value("open_files", [])
    if not isinstance(files, list):
        files = [files] if files else []
    pages = value("workspace_pages", [])
    if not isinstance(pages, list):
        pages = [pages] if pages is not None else []
    return {
        "schemaVersion": 1,
        "origin": "PlusMinus/Studio4",
        "openFiles": [x for x in files if x],
        "lastFile": value("last_file", ""),
        "lastNotebook": value("last_notebook_v4", ""),
        "activeResearchMode": value("research_mode_v4", ""),
        "workspacePages": pages,
        "splitEditor": str(value("split_editor", False)).lower() in ("true", "1"),
        "notExported": ["geometry", "research_docks_v4"]
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a new JSON file (never overwrite)")
    args = parser.parse_args()
    doc = json.dumps(portable(QSettings("PlusMinus", "Studio4")), ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(doc)
    else:
        if args.output.exists():
            parser.error("Output exists; refusing to overwrite")
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(doc)
        print("Exported: " + str(args.output))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

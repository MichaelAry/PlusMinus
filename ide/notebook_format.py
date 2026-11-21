"""Portable Jupyter v4 notebook I/O without requiring nbformat at runtime.

The first PlusMinus backend executes code cells in isolated interpreter processes.
There is no cross-cell state until a persistent native kernel is implemented.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


def new_notebook():
    return {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "PlusMinus (isolated)",
                "language": "plusminus",
                "name": "plusminus-isolated",
            },
            "language_info": {"name": "plusminus", "file_extension": ".pm"},
            "plusminus": {"execution_mode": "isolated"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def make_cell(kind="code", source=""):
    if kind not in ("code", "markdown"):
        raise ValueError("Only code and markdown notebook cells are supported")
    cell = {"cell_type": kind, "id": uuid.uuid4().hex[:8],
            "metadata": {}, "source": str(source)}
    if kind == "code":
        cell.update(execution_count=None, outputs=[])
    return cell


def source_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(line, str) for line in value):
        return "".join(value)
    raise ValueError("Invalid notebook cell source")


def validate(notebook):
    if not isinstance(notebook, dict) or notebook.get("nbformat") != 4:
        raise ValueError("Expected a Jupyter notebook (nbformat v4)")
    raw_cells = notebook.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("Notebook has no valid cells array")
    for cell in raw_cells:
        if not isinstance(cell, dict) or cell.get("cell_type") not in ("code", "markdown"):
            raise ValueError("Only code and markdown cells can be edited in Studio")
        cell["source"] = source_text(cell.get("source", ""))
        cell.setdefault("id", uuid.uuid4().hex[:8])
        cell.setdefault("metadata", {})
        if cell["cell_type"] == "code":
            cell.setdefault("execution_count", None)
            cell.setdefault("outputs", [])
    notebook.setdefault("metadata", {})
    notebook.setdefault("nbformat_minor", 5)
    return notebook


def load_notebook(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def serialize(notebook):
    return json.dumps(validate(notebook), ensure_ascii=False, indent=2) + "\n"


def stream_output(content):
    return {"output_type": "stream", "name": "stdout", "text": str(content)}


def error_output(message):
    return {"output_type": "error", "ename": "PlusMinusError",
            "evalue": str(message), "traceback": [str(message)]}

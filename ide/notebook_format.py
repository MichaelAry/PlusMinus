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
    metadata = notebook.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Notebook metadata must be an object")
    language_info = metadata.get("language_info", {})
    kernelspec = metadata.get("kernelspec", {})
    if not isinstance(language_info, dict) or not isinstance(kernelspec, dict):
        raise ValueError("Notebook language metadata must be objects")
    language = language_info.get("name")
    kernel_name = kernelspec.get("name")
    if ((language and language != "plusminus") or
            (kernel_name and not str(kernel_name).startswith("plusminus"))):
        raise ValueError("This notebook uses another kernel; Studio can execute only PlusMinus.")
    raw_cells = notebook.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("Notebook has no valid cells array")
    if len(raw_cells) > 2000:
        raise ValueError("Notebook exceeds the 2,000-cell editor limit")
    for cell in raw_cells:
        if not isinstance(cell, dict) or cell.get("cell_type") not in ("code", "markdown"):
            raise ValueError("Only code and markdown cells can be edited in Studio")
        cell["source"] = source_text(cell.get("source", ""))
        cell.setdefault("id", uuid.uuid4().hex[:8])
        if not isinstance(cell["id"], str) or not cell["id"]:
            raise ValueError("Notebook cell id must be a nonempty string")
        cell.setdefault("metadata", {})
        if not isinstance(cell["metadata"], dict):
            raise ValueError("Notebook cell metadata must be an object")
        if cell["cell_type"] == "code":
            cell.setdefault("execution_count", None)
            counter = cell["execution_count"]
            if (counter is not None and
                    (not isinstance(counter, int) or isinstance(counter, bool) or counter < 0)):
                raise ValueError("Notebook execution_count must be a nonnegative integer or null")
            cell.setdefault("outputs", [])
            if not isinstance(cell["outputs"], list) or not all(
                    isinstance(value, dict) for value in cell["outputs"]):
                raise ValueError("Notebook cell outputs must be an array of objects")
    notebook.setdefault("nbformat_minor", 5)
    return notebook


def load_notebook(path):
    path = Path(path)
    # Avoid locking the GUI while loading notebooks with enormous embedded assets.
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Notebook exceeds the 32 MiB interactive editor limit")
    return validate(json.loads(path.read_text(encoding="utf-8-sig")))


def serialize(notebook):
    return json.dumps(validate(notebook), ensure_ascii=False, indent=2) + "\n"


def stream_output(content):
    return {"output_type": "stream", "name": "stdout", "text": str(content)}


def error_output(message):
    return {"output_type": "error", "ename": "PlusMinusError",
            "evalue": str(message), "traceback": [str(message)]}

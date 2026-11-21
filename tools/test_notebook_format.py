"""Pure notebook model tests (Qt and native runner not required)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ide"))
from notebook_format import (
    error_output, load_notebook, make_cell, new_notebook, serialize,
    source_text, stream_output, validate,
)


class NotebookDocumentTests(unittest.TestCase):
    def test_jupyter_v4_roundtrip(self):
        notebook = new_notebook()
        notebook["cells"].append(make_cell("markdown", "# Experiment"))
        cell = make_cell("code", "print(2 + 2);")
        cell["execution_count"] = 1
        cell["outputs"] = [stream_output("4\n")]
        notebook["cells"].append(cell)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.ipynb"
            path.write_text(serialize(notebook), encoding="utf-8")
            data = load_notebook(path)
            self.assertEqual(data["nbformat"], 4)
            self.assertEqual(data["cells"][0]["cell_type"], "markdown")
            self.assertEqual(data["cells"][1]["source"], "print(2 + 2);")
            self.assertEqual(data["cells"][1]["outputs"][0]["text"], "4\n")
            self.assertEqual(data["metadata"]["plusminus"]["execution_mode"], "isolated")
            self.assertIsNotNone(data["cells"][1]["id"])

    def test_legacy_line_arrays(self):
        data = new_notebook()
        data["cells"] = [
            {"cell_type": "code", "source": ["x=1;\n", "print(x);"],
             "metadata": {}, "outputs": [], "execution_count": None}
        ]
        restored = validate(data)
        self.assertEqual(restored["cells"][0]["source"], "x=1;\nprint(x);")
        self.assertTrue(restored["cells"][0]["id"])

    def test_reject_invalid_notebooks_without_eval(self):
        with self.assertRaises(ValueError):
            validate({"nbformat": 3, "cells": []})
        with self.assertRaises(ValueError):
            validate({"nbformat": 4, "cells": [{"cell_type": "raw"}]})
        with self.assertRaises(ValueError):
            source_text([123, "wrong"])

    def test_error_output_is_jupyter_compatible(self):
        output = error_output("compile: unexpected ')'")
        self.assertEqual(output["output_type"], "error")
        self.assertEqual(output["ename"], "PlusMinusError")
        self.assertEqual(output["traceback"], ["compile: unexpected ')'"])
        self.assertTrue(json.loads(serialize(new_notebook())))


if __name__ == "__main__":
    unittest.main()

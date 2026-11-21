"""Output and metric reporting should never hide real execution results."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ide"))
from execution_report import render_output, render_details


class ExecutionReportTests(unittest.TestCase):
    def test_stdout_return_and_zero(self):
        self.assertIn("Hello", render_output({"ok": True, "output": "Hello\n", "result": 0}))
        self.assertIn("Return value: 0", render_output({"ok": True, "output": "", "result": 0}))
        self.assertIn("(No stdout produced)", render_output({"ok": True, "result": ""}))

    def test_errors_visible_even_without_stdout(self):
        report = {"ok": False, "output": "", "result": "", "error": "compile failed",
                  "ms": 9.5, "metrics": {}}
        self.assertIn("Execution failed", render_output(report))
        self.assertIn("compile failed", render_details(report))
        self.assertIn("not measured", render_details(report))

    def test_instrumented_runtime_metrics(self):
        report = {
            "ok": True, "ms": 34.2, "output": "42\n",
            "metrics": {"compile_ms": 1.2, "execute_ms": 3.4,
                        "peak_rss_mb": 12.0, "peak_threads": 2,
                        "program_instructions": 50,
                        "executed_instructions": 500,
                        "opcode_hits": {"Jmp": 10},
                        "samples": [[40, 12.0, 2, 1.0]]},
            "trace": [{"ip": 0}],
            "trace_truncated": False,
        }
        text = render_details(report, "Profile")
        self.assertIn("Profile", text)
        self.assertIn("1.20 ms", text)
        self.assertIn("12.00 MB", text)
        self.assertIn("500", text)
        self.assertIn("Resource samples          1", text)

    def test_missing_data_never_claimed_zero(self):
        summary = render_details({"ok": True, "ms": 0, "metrics": {}})
        self.assertIn("CPU time          not measured", summary)
        self.assertIn("RSS  not measured", summary)
        self.assertIn("sampling can miss", summary)


if __name__ == "__main__":
    unittest.main()

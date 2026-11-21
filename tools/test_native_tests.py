"""Portable native suite metadata and regression history tests."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"ide"))
from native_tests import NativeHistory, source_fingerprint


class NativeTestHistoryTests(unittest.TestCase):
    def test_regressions_and_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = NativeHistory(root/"history.db")
            a = {"id":"X.a","group":"arithmetic","source":"x.cpp",
                 "status":"PASS","elapsed_ms":1.0,"error":""}
            b = {"id":"X.b","group":"arithmetic","source":"x.cpp",
                 "status":"FAIL","elapsed_ms":2.0,"error":"bad"}
            initial = store.save("before", [a,b], root)
            store.set_baseline(initial)
            self.assertEqual(store.baseline(), initial)
            later = store.save("after", [{**a,"status":"FAIL"}, {**b,"status":"PASS"}], root)
            diff = store.compare(initial, later)
            self.assertEqual(diff["introduced"], ["X.a"])
            self.assertEqual(diff["fixed"], ["X.b"])
            self.assertEqual(len(store.recent()), 2)

    def test_source_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"src"/"api.cpp"
            path.parent.mkdir()
            path.write_text("int a;")
            before=source_fingerprint(root)
            path.write_text("int b;")
            self.assertNotEqual(before,source_fingerprint(root))


if __name__ == "__main__":
    unittest.main()

"""Portable native suite metadata and regression history tests."""
import tempfile
import unittest
import sqlite3
from contextlib import closing
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

    def test_body_timings_and_comparison_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = NativeHistory(root / "history.db")
            case = {"id":"Math.add","group":"arithmetic","source":"math.cpp",
                    "status":"PASS","error":"", "elapsed_ms":15.0, "test_ms":2.0}
            before = store.save("before", [case], root)
            after = store.save("after", [{**case, "elapsed_ms":20.0, "test_ms":4.0}], root)
            delta = store.compare(before, after)
            self.assertTrue(delta["comparable_platform"])
            self.assertTrue(delta["same_source"])
            self.assertEqual(delta["performance"]["Math.add"]["metric"], "body")
            self.assertEqual(delta["performance"]["Math.add"]["delta_ms"], 2.0)
            self.assertEqual(delta["performance"]["Math.add"]["delta_pct"], 100.0)
            self.assertEqual(store.results(after)["Math.add"]["test_ms"], 4.0)
            self.assertEqual(store.session(before)["label"], "before")

    def test_existing_database_migrates_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "legacy.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("""CREATE TABLE native_results (
                    session_id INTEGER NOT NULL, test_id TEXT NOT NULL,
                    category TEXT NOT NULL, status TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL, error TEXT NOT NULL, source TEXT NOT NULL,
                    peak_rss_mb REAL, cpu_ms REAL,
                    PRIMARY KEY(session_id, test_id))""")
                connection.execute("""INSERT INTO native_results
                    VALUES (1, 'Old.test', 'legacy', 'PASS', 2.0, '', 'legacy.cpp', NULL, NULL)""")
            store = NativeHistory(database)
            with closing(sqlite3.connect(database)) as connection:
                columns = {r[1] for r in connection.execute("PRAGMA table_info(native_results)")}
                self.assertIn("test_ms", columns)
            self.assertIsNone(store.results(1)["Old.test"]["test_ms"])
            NativeHistory(database)  # Second initialization must be idempotent.

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

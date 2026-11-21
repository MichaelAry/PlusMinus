"""Source coordinate and lexical warning tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ide"))
from source_diagnostics import analyze_diagnostics, position

class SourceDiagnosticTests(unittest.TestCase):
    def test_coordinates(self):
        self.assertEqual(position("one\n abc",5),(2,2))

    def test_ignores_comments_and_strings(self):
        self.assertEqual(analyze_diagnostics('print("{"); /* ( */ // }\n'),[])

    def test_missing_brace(self):
        issues=analyze_diagnostics("while (1) {\n print(2);\n")
        self.assertTrue(any(i['code']=='PM1001' and i['line']==1 for i in issues))

    def test_unmatched_close(self):
        issues=analyze_diagnostics("x = 2; }")
        self.assertTrue(any(i['code']=='PM1002' for i in issues))

    def test_concurrency_is_a_warning(self):
        issues=analyze_diagnostics("go work();")
        self.assertTrue(any(i['code']=='PM3001' and i['severity']=='warning' for i in issues))

if __name__ == "__main__":
    unittest.main()

"""Git detection should work for non-repository folders."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ide'))
from git_service import repository_summary

class GitSummaryTests(unittest.TestCase):
    def test_directory_without_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(repository_summary(Path(temp))['available'])

if __name__=="__main__":
    unittest.main()

"""Windows startup recovery and safe-mode CLI regression tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ide"))
import launch
from startup_diagnostics import safe_mode_requested


class DiagnosticModeTests(unittest.TestCase):
    def test_safe_mode_parser(self):
        self.assertTrue(safe_mode_requested(["studio_qt.py", "--safe-mode"], {}))
        self.assertTrue(safe_mode_requested(["studio_qt.py"], {"PLUSMINUS_SAFE_MODE": "1"}))
        self.assertFalse(safe_mode_requested(["studio_qt.py"], {}))

    def test_successful_gui_launch_does_not_retry(self):
        with patch.object(launch.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as task:
            launch.run_studio("python.exe")
        self.assertEqual(task.call_count, 1)
        self.assertIn("-X", task.call_args.args[0])

    def test_access_violation_retries_once_in_safe_mode(self):
        with patch.object(launch.sys, "platform", "win32"), patch.object(
                launch.subprocess, "run", side_effect=[
                    SimpleNamespace(returncode=3221225477),
                    SimpleNamespace(returncode=0),
                ]) as task:
            launch.run_studio("python.exe")
        self.assertEqual(task.call_count, 2)
        self.assertNotIn("--safe-mode", task.call_args_list[0].args[0])
        self.assertIn("--safe-mode", task.call_args_list[1].args[0])

    def test_signed_access_violation_is_also_detected(self):
        with patch.object(launch.sys, "platform", "win32"), patch.object(
                launch.subprocess, "run", side_effect=[
                    SimpleNamespace(returncode=-1073741819),
                    SimpleNamespace(returncode=0),
                ]) as task:
            launch.run_studio("python.exe")
        self.assertEqual(task.call_count, 2)

    def test_safe_mode_crash_does_not_loop(self):
        with patch.object(launch.sys, "platform", "win32"), patch.object(
                launch.subprocess, "run", return_value=SimpleNamespace(returncode=3221225477)
        ) as task:
            with self.assertRaises(launch.LaunchError):
                launch.run_studio("python.exe", safe_mode=True)
        self.assertEqual(task.call_count, 1)

    def test_other_errors_are_not_misclassified_as_access_violations(self):
        with patch.object(launch.sys, "platform", "win32"), patch.object(
                launch.subprocess, "run", return_value=SimpleNamespace(returncode=2)
        ) as task:
            with self.assertRaises(launch.LaunchError):
                launch.run_studio("python.exe")
        self.assertEqual(task.call_count, 1)


if __name__ == "__main__":
    unittest.main()

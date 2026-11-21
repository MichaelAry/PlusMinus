"""Dependency-free smoke tests for the portable source launcher."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch


class LauncherTests(unittest.TestCase):
    def test_missing_dependencies(self):
        with patch.object(launch, 'has_tk', return_value=False), \
             patch.object(launch, 'find_cmake', return_value=None), \
             patch.object(launch, 'has_compiler', return_value=False):
            self.assertEqual(launch.missing_dependencies(), ['cmake', 'cxx'])

    def test_launcher_tracks_modular_sources(self):
        all_cpp = tuple((launch.ROOT / 'src').rglob('*.cpp'))
        all_headers = tuple((launch.ROOT / 'include').rglob('*.hpp'))
        self.assertGreater(len(all_cpp), 5)
        self.assertTrue(all(path in launch.SOURCES for path in all_cpp + all_headers))
        self.assertIn(launch.ROOT / 'CMakeLists.txt', launch.SOURCES)

    def test_existing_runner_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'Parser.cpp'
            source.write_text('int x;')
            runner = folder / 'plusminus_runner'
            runner.write_text('bin')
            with patch.object(launch, 'SOURCES', (source,)):
                self.assertFalse(launch.needs_build(runner))
                source.write_text('int y;')
                os.utime(source, (runner.stat().st_mtime + 10, runner.stat().st_mtime + 10))
                self.assertTrue(launch.needs_build(runner))

    def test_check_does_not_require_installation(self):
        # Check mode is diagnostic: no package-management subprocesses.
        with patch.object(sys, 'argv', ['launch.py', '--check']), \
             patch.object(launch, 'missing_dependencies', return_value=['tk']), \
             patch.object(launch, 'source_runner', return_value=None), \
             patch.object(launch, 'find_cmake', return_value=None), \
             patch.object(launch, 'has_compiler', return_value=True), \
             patch.object(launch, 'has_tk', return_value=False), \
             patch.object(launch, 'run') as run:
            self.assertEqual(launch.main(), 1)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

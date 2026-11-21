#!/usr/bin/env python3
"""Build a self-contained PlusMinus Studio desktop release on the host OS.

Requires a compiled runner in ide/build and PyInstaller in the active Python.
Run separately on each target OS/CPU architecture; cross-compilation is not used.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDE = ROOT / "ide"
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
APP = "PlusMinusStudio"


def runner_path() -> Path:
    sys.path.insert(0, str(IDE))
    from engine import find_runner
    runner = find_runner()
    if runner is None:
        raise RuntimeError("C++ runner missing. Run: python launch.py --build-only")
    return runner.resolve()


def main() -> int:
    runner = runner_path()
    if shutil.which("cmake") is None:
        print("Note: CMake is not needed by PyInstaller if the runner is already compiled.")
    RELEASE.mkdir(exist_ok=True)
    (ROOT / "build" / "pyinstaller").mkdir(parents=True, exist_ok=True)
    platform_name = {"win32": "windows", "linux": "linux", "darwin": "macos"}.get(sys.platform)
    if platform_name is None:
        raise RuntimeError(f"Unsupported release platform: {sys.platform}")
    machine = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    # macOS .app must be onedir; Windows/Linux use onefile (no installed Python).
    from native_tests import find_native_runner
    native = find_native_runner()
    if native is None:
        raise RuntimeError("Native test executable missing; rebuild all CMake targets.")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--distpath", str(DIST), "--workpath", str(ROOT / "build" / "pyinstaller"),
               "--specpath", str(ROOT / "build" / "pyinstaller"),
               "--name", APP, "--windowed", "--onedir" if sys.platform == "darwin" else "--onefile",
               "--add-binary", f"{runner}{os.pathsep}.",
               "--add-binary", f"{native}{os.pathsep}.", str(IDE / "studio_qt.py")]
    subprocess.run(command, cwd=str(ROOT), check=True)
    base_name = f"{APP}-{platform_name}-{machine}"
    if sys.platform == "win32":
        app = DIST / f"{APP}.exe"
        if not app.is_file():
            raise RuntimeError("Windows executable missing after PyInstaller build")
        artifact = RELEASE / f"{base_name}.zip"
        with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(app, f"{APP}.exe")
    elif sys.platform == "darwin":
        app = DIST / f"{APP}.app"
        if not app.is_dir():
            raise RuntimeError("macOS .app bundle missing after PyInstaller build")
        artifact = RELEASE / f"{base_name}.zip"
        # ditto preserves app symlinks, permissions and bundle structure.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(app), str(artifact)], check=True)
    else:
        app = DIST / APP
        if not app.is_file():
            raise RuntimeError("Linux executable missing after PyInstaller build")
        app.chmod(app.stat().st_mode | 0o111)
        artifact = RELEASE / f"{base_name}.tar.gz"
        with tarfile.open(artifact, "w:gz") as tar:
            tar.add(app, arcname=f"{APP}/{APP}")
            tar.add(ROOT / "tools" / "PlusMinusStudio.desktop", arcname=f"{APP}/{APP}.desktop")
    print(f"Built release artifact: {artifact}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Packaging failed: {exc}", file=sys.stderr)
        sys.exit(1)

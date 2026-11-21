#!/usr/bin/env python3
"""Build and launch PlusMinus Studio from a source checkout.

Requires Python >= 3.9. Release binaries do not require this launcher or a
locally installed Python, CMake, compiler, or Qt.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDE = ROOT / "ide"
BUILD = IDE / "build"
# Track every core translation unit/header, including files created by Language Internals.
SOURCES = tuple(sorted([
    ROOT / "CMakeLists.txt", ROOT / "Parser.h", IDE / "runner.cpp", IDE / "CMakeLists.txt",
    *(ROOT / "src").rglob("*.cpp"), *(ROOT / "src").rglob("*.hpp"),
    *(ROOT / "include").rglob("*.hpp"),
]))


class LaunchError(RuntimeError):
    """An actionable installation, build, or launch failure."""


def log(message: str) -> None:
    print(f"[PlusMinus] {message}", flush=True)


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    log("Running: " + " ".join(str(item) for item in command))
    try:
        result = subprocess.run(command, cwd=str(cwd), check=False)
    except OSError as exc:
        raise LaunchError(f"Could not execute {command[0]}: {exc}") from exc
    if result.returncode:
        raise LaunchError(f"Command failed with exit code {result.returncode}: {command[0]}")


def find_cmake() -> str | None:
    found = shutil.which("cmake")
    if found:
        return found
    if sys.platform == "win32":
        for environment in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(environment)
            if base:
                candidate = Path(base) / "CMake" / "bin" / "cmake.exe"
                if candidate.is_file():
                    return str(candidate)
        for edition in ("BuildTools", "Community", "Professional", "Enterprise"):
            for version in ("2022", "2026", "2019"):
                for environment in ("ProgramFiles", "ProgramFiles(x86)"):
                    base = os.environ.get(environment)
                    if base:
                        candidate = (Path(base) / "Microsoft Visual Studio" / version / edition /
                                     "Common7" / "IDE" / "CommonExtensions" / "Microsoft" /
                                     "CMake" / "CMake" / "bin" / "cmake.exe")
                        if candidate.is_file():
                            return str(candidate)
    return None


def windows_visual_studio() -> bool:
    for environment in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(environment)
        if not base:
            continue
        vswhere = Path(base) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if vswhere.is_file():
            result = subprocess.run(
                [str(vswhere), "-latest", "-products", "*", "-requires",
                 "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
    return bool(shutil.which("cl"))


def has_compiler() -> bool:
    if os.environ.get("CXX"):
        return True  # CMake will validate the explicit toolchain.
    if any(shutil.which(item) for item in ("g++", "clang++")):
        return True
    return sys.platform == "win32" and windows_visual_studio()


def has_tk() -> bool:
    try:
        import tkinter  # noqa: F401 - tkinter is a required stdlib module.
        return True
    except (ImportError, OSError):
        return False


def missing_dependencies() -> list[str]:
    missing = []
    if not find_cmake():
        missing.append("cmake")
    if not has_compiler():
        missing.append("cxx")
    return missing


def package_manager() -> str | None:
    for manager in ("apt-get", "dnf", "pacman", "zypper"):
        if shutil.which(manager):
            return manager
    return None


def linux_install_command(missing: list[str]) -> list[str]:
    manager = package_manager()
    packages = {
        "apt-get": {"tk": ["python3-tk"], "cmake": ["cmake"], "cxx": ["build-essential"]},
        "dnf": {"tk": ["python3-tkinter"], "cmake": ["cmake"], "cxx": ["gcc-c++", "make"]},
        "pacman": {"tk": ["tk"], "cmake": ["cmake"], "cxx": ["base-devel"]},
        "zypper": {"tk": ["python3-tk"], "cmake": ["cmake"], "cxx": ["gcc-c++", "make"]},
    }
    if manager not in packages:
        raise LaunchError("Unsupported Linux package manager. Install Python Tk, CMake and a C++20 compiler manually.")
    selected = sorted({package for need in missing for package in packages[manager][need]})
    prefix = [] if (getattr(os, "geteuid", lambda: 1)() == 0) else ["sudo"]
    if prefix and not shutil.which("sudo"):
        raise LaunchError("Administrator rights required; sudo was not found.")
    flags = {"apt-get": ["install", "-y"], "dnf": ["install", "-y"],
             "pacman": ["-S", "--needed", "--noconfirm"], "zypper": ["--non-interactive", "install"]}
    return prefix + [manager] + flags[manager] + selected


def install_dependencies(missing: list[str], *, agree: bool) -> None:
    if not missing:
        return
    log("Missing dependencies: " + ", ".join(missing))
    if not agree:
        if not sys.stdin.isatty():
            raise LaunchError("Cannot request installation consent in a noninteractive terminal. Use --yes or install dependencies manually.")
        answer = input("Allow system package installation? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            raise LaunchError("Installation declined. Run with --no-install after installing the dependencies.")
    if sys.platform.startswith("linux"):
        run(linux_install_command(missing))
    elif sys.platform == "win32":
        if not shutil.which("winget"):
            raise LaunchError("winget was not found. Install CMake and Visual Studio Build Tools (Desktop development with C++) manually.")
        if "tk" in missing:
            raise LaunchError("This Python installation lacks Tcl/Tk. Reinstall Python with the 'tcl/tk and IDLE' feature enabled.")
        if "cmake" in missing:
            run(["winget", "install", "--id", "Kitware.CMake", "--exact", "--silent",
                 "--accept-source-agreements", "--accept-package-agreements"])
        if "cxx" in missing:
            run(["winget", "install", "--id", "Microsoft.VisualStudio.2022.BuildTools", "--exact",
                 "--accept-source-agreements", "--accept-package-agreements", "--override",
                 "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"])
    elif sys.platform == "darwin":
        if "tk" in missing:
            raise LaunchError("Current Python lacks tkinter. Install a Python distribution with Tcl/Tk support.")
        if "cxx" in missing:
            raise LaunchError("Install Apple Command Line Tools with 'xcode-select --install', then rerun the launcher.")
        if "cmake" in missing and shutil.which("brew"):
            run(["brew", "install", "cmake"])
        elif "cmake" in missing:
            raise LaunchError("Install CMake (for example via Homebrew), then rerun the launcher.")
    else:
        raise LaunchError(f"Unsupported OS: {sys.platform}")
    remaining = missing_dependencies()
    if remaining:
        raise LaunchError("Dependencies are still unavailable: " + ", ".join(remaining) + ". Reopen the terminal if PATH changed and rerun.")


def source_runner() -> Path | None:
    # The IDE already supports this layout; do not accidentally select a debug
    # executable before its corresponding release build.
    name = "plusminus_runner.exe" if sys.platform == "win32" else "plusminus_runner"
    for directory in (BUILD / "Release", BUILD, BUILD / "Debug"):
        path = directory / name
        if path.is_file():
            return path
    return None


def needs_build(runner: Path | None) -> bool:
    if runner is None:
        return True
    return any(path.stat().st_mtime > runner.stat().st_mtime for path in SOURCES)


def build_runner(*, install: bool, agree: bool, rebuild: bool) -> Path:
    for source in SOURCES:
        if not source.is_file():
            raise LaunchError(f"Missing project source file: {source}")
    existing = source_runner()
    if existing is not None and not rebuild and not needs_build(existing):
        log("Using existing C++ runner (no rebuild needed).")
        return existing
    missing = missing_dependencies()
    if missing:
        if not install:
            raise LaunchError("Missing " + ", ".join(missing) + ". Install manually or rerun without --no-install.")
        install_dependencies(missing, agree=agree)
    cmake = find_cmake()
    if cmake is None:
        raise LaunchError("CMake cannot be found after installation.")
    configure = [cmake, "-S", str(ROOT), "-B", str(BUILD), "-DCMAKE_BUILD_TYPE=Release"]
    # CMake's default generator chooses Visual Studio when available on Windows,
    # and a platform-native Make/Ninja generator on Linux/macOS.
    run(configure)
    cmd = [cmake, "--build", str(BUILD), "--config", "Release", "--parallel", "2"]
    if rebuild:
        cmd.append("--clean-first")
    run(cmd)
    result = source_runner()
    if result is None or not result.is_file():
        raise LaunchError("CMake completed without producing plusminus_runner.")
    return result


def local_gui_python() -> Path:
    venv = ROOT / '.venv'
    return venv / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def gui_python_ready() -> bool:
    candidate = local_gui_python()
    if not candidate.exists():
        candidate = Path(sys.executable)
    try:
        result = subprocess.run([str(candidate), '-c', 'import PySide6, psutil'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=8, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_gui_python(*, install: bool) -> str:
    candidate = local_gui_python()
    if gui_python_ready():
        return str(candidate if candidate.exists() else Path(sys.executable))
    if not install:
        raise LaunchError('PySide6/psutil missing. Install ide/requirements.txt, or omit --no-install.')
    if not candidate.is_file():
        log('Creating isolated Python environment for PlusMinus Studio...')
        run([sys.executable, '-m', 'venv', str(ROOT / '.venv')])
    log('Installing Qt interface and telemetry dependencies (first launch only)...')
    run([str(candidate), '-m', 'pip', 'install', '-r', str(IDE / 'requirements.txt')])
    if not gui_python_ready():
        raise LaunchError('Qt dependencies are unavailable after installation.')
    return str(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and run PlusMinus Studio on Windows, Linux, or macOS.")
    parser.add_argument("--yes", action="store_true", help="Approve system package installation without prompting")
    parser.add_argument("--no-install", action="store_true", help="Never install system packages")
    parser.add_argument("--check", action="store_true", help="Print prerequisites and exit without changing the system")
    parser.add_argument("--build-only", action="store_true", help="Prepare the C++ runner without opening the GUI")
    parser.add_argument("--test", action="store_true", help="Run existing IDE smoke tests after preparing the runner")
    parser.add_argument("--rebuild", action="store_true", help="Force a fresh C++ build")
    args = parser.parse_args()
    if sys.version_info < (3, 9):
        raise LaunchError("Python 3.9 or newer is required for source launch.")
    if args.check:
        log(f"Operating system: {platform.platform()} ({platform.machine()})")
        log(f"Python: {sys.version.split()[0]} / Qt: {'OK' if gui_python_ready() else 'missing'}")
        log(f"CMake: {find_cmake() or 'missing'} / C++ compiler: {'OK' if has_compiler() else 'missing'}")
        runner = source_runner()
        log(f"C++ runner: {str(runner) if runner else 'missing'}")
        return 0 if not missing_dependencies() and gui_python_ready() else 1
    runner = build_runner(install=not args.no_install, agree=args.yes, rebuild=args.rebuild)
    log(f"Runner ready: {runner}")
    if args.test:
        run([sys.executable, str(IDE / "smoke_test.py")])
    if args.build_only or args.test:
        return 0
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise LaunchError("No graphical session detected (DISPLAY/WAYLAND_DISPLAY is unset).")
    run([ensure_gui_python(install=not args.no_install), str(IDE / "studio_qt.py")])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LaunchError, KeyboardInterrupt) as error:
        print(f"[PlusMinus] ERROR: {error}", file=sys.stderr)
        sys.exit(1)

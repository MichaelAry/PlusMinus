#!/usr/bin/env python3
"""Differential smoke: Studio 4 Python execution adapter vs unchanged C++ runner.

This checks *runner/report* semantics, not graphical Qt-vs-Tauri UI parity.
No PySide6, project files, C++ source modifications or user DB access needed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ide"))
from engine import execute  # noqa: E402 -- original Studio 4 adapter


def resolve_binary(build: Path) -> Path:
    ext = ".exe" if sys.platform == "win32" else ""
    for folder in (build, build / "Release", build / "Debug"):
        target = folder / ("plusminus_runner" + ext)
        if target.is_file():
            return target.resolve()
    raise FileNotFoundError("No C++ runner in " + str(build))


def check_case(binary: Path, mode: str, source: str, expected_ok: bool) -> None:
    direct = subprocess.run(
        [str(binary), mode], input=source.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=12, check=False,
    )
    raw = json.loads(direct.stdout.decode("utf-8"))
    qt = execute(binary, source, mode=mode, timeout=12.0)
    if direct.returncode != (0 if expected_ok else 1):
        raise AssertionError(f"{mode}: unexpected C++ exit code {direct.returncode}")
    if raw.get("ok") is not expected_ok or qt.get("ok") is not expected_ok:
        raise AssertionError(f"{mode}: status disagreement (Qt={qt.get('ok')}, native={raw.get('ok')})")

    for field in ("output", "result", "variables", "bytecode", "error", "diagnostics", "trace_truncated"):
        if qt.get(field) != raw.get(field):
            raise AssertionError(f"{mode}: Studio 4 and original C++ disagree on {field!r}")

    for field in ("compile_ms", "execute_ms", "program_instructions", "executed_instructions", "opcode_hits"):
        if field not in raw.get("metrics", {}) or field not in qt.get("metrics", {}):
            raise AssertionError(f"{mode}: missing a native metric key: {field}")

    # Trace entries may carry runtime-dependent timing; compare count and cap.
    native_trace = raw.get("trace", [])
    if len(qt.get("trace", [])) != len(native_trace) or len(native_trace) > 5000:
        raise AssertionError(f"{mode}: invalid/corrupted post-execution trace count")
    print(f"{mode:<7}  {'ok' if expected_ok else 'compiler error':<16} "
          f"output={len(raw.get('output', ''))} bytes  trace={len(native_trace)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/studio5")
    args = parser.parse_args()
    binary = resolve_binary(args.build_dir)
    samples = [
        ("run", "print(0);\n", True),
        ("run", "x = 2;\n", True),
        ("compile", "print(1);\n", True),
        ("profile", "print(1);\n", True),
        ("trace", "print(1);\n", True),
        ("run", "print(;\n", False),
    ]
    for mode, source, ok in samples:
        check_case(binary, mode, source, ok)
    print("PASS: original Studio 4 execution adapter matches native C++ one-shot responses.")


if __name__ == "__main__":
    main()

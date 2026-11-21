# PlusMinus Studio 2.0

**A native desktop analytics IDE for the PlusMinus C++20 interpreter.**

PlusMinus Studio has a Qt/PySide6 dark GUI, a code editor, live resource monitoring,
startup regression tests, benchmark lab, bytecode analysis, a persistent run history,
and portable binary packaging for Windows, Linux and macOS.

## Start with a double-click

Download the repository or clone it, then launch from its top-level folder:

| Operating system | Double-click | Source prerequisites |
|---|---|---|
| Windows | `Start-PlusMinus.cmd` | Python 3.9+ (with venv/pip), CMake, Visual Studio C++ tools |
| Linux | `Start-PlusMinus.desktop` | Python 3.9+, CMake, C++20 compiler |
| macOS | `Start-PlusMinus.command` | Python 3.9+, CMake, Apple Command Line Tools |

The source launcher **automatically builds the C++ VM and creates a local `.venv`**,
then installs the free Python GUI dependencies from `ide/requirements.txt`.
For native build prerequisites, it asks before installing system packages where supported.
Linux file managers may require **Allow Launching / Mark as Trusted** once. On macOS,
unsigned command files may need a permission adjustment.

For **installation-free startup**, download a platform-native binary from the
[GitHub Releases](https://github.com/Maksim23060/PlusMinus/releases) page *once a
successful tagged build has been published*:

- Windows: extract and double-click `PlusMinusStudio.exe`.
- Linux: extract and run `PlusMinusStudio/PlusMinusStudio` or the accompanying `.desktop` shortcut.
- macOS Intel: extract and open `PlusMinusStudio.app`.

The executable bundles Python, Qt, psutil and the C++ runner. macOS unsigned binaries
may require approval in Privacy & Security. Linux bundles depend on a compatible glibc.

## Features

| Area | Features |
|---|---|
| Overview | Test health, execution and memory cards, performance history |
| Code Editor | Syntax highlighting, line numbers, open/save, code insights, compiler output, bytecode, variables |
| Test Center | Automatic startup suite, separate process per test, expected vs actual, import/export user tests |
| Profiler | Real wall/CPU time, sampled RSS and thread counts, C++ VM phase timing, compiled opcode frequencies |
| Resources | Live GUI CPU/RSS graph and per-program memory trend |
| Benchmarks | Repeated runs, warmup, mean, median, P95, standard deviation, graphical comparisons |
| History | SQLite records (in `~/.plusminus/studio.db`), CSV and JSON export |

**Measurement honesty:** Source complexity is a lexical *estimate*, not a full AST or
control-flow proof. Compiled opcode counts are *static* counts, not execution frequency.
CPU and memory are sampled; very short processes may escape reliable sampling, and
sampled peak RSS is not an absolute guaranteed maximum. VM internal timings are only
present after rebuilding the C++ runner with the metric protocol.

## Command-line operations

```bash
python launch.py                  # compile VM if needed, install GUI deps locally, start GUI
python launch.py --check          # inspect environment; never install
python launch.py --no-install     # fail without adding missing dependencies
python launch.py --build-only     # compile the C++ runner
python launch.py --test           # legacy C++ smoke tests
python launch.py --rebuild        # force native rebuild
```

## Development and release packaging

```bash
python launch.py --build-only
python -m venv .venv
# Activate .venv or call .venv/Scripts/python.exe on Windows:
.venv/bin/python -m pip install -r ide/requirements.txt pyinstaller==6.16.0
.venv/bin/python -m unittest discover -s tools -p 'test_*.py'
.venv/bin/python tools/package.py
```

GitHub Actions builds portable bundles per operating system, verifies the runner and
runs headless smoke tests. These are separate native artifacts, not a single binary
usable across operating systems.

## Security and scope

Programs run in a separate process with a configurable timeout, **not** in an OS
security sandbox. Do not execute untrusted PlusMinus source without additional OS
isolation. Startup tests run only a small, trusted built-in suite; arbitrary imported
user programs are not executed automatically. The GUI uses no cloud service.


## Language Internals — edit the C++ language inside Studio

Hold **Ctrl** and click a PlusMinus keyword or built-in function in the code
editor (for example `if`, `while`, `go`, `print`, `pow`, or `len`).
The separate **Language Internals** window opens the real implementation in
`Parser.cpp` and lets you switch between compiler and runtime
sections. It also provides the core types/opcodes from `Parser.h`
and the JSON runner adapter in `ide/runner.cpp`.

You can edit the actual C++ implementation and press **Ctrl+S**. Studio saves
a backup under `.plusminus-backups/`, writes the C++ source
atomically, and by default rebuilds the runner in the background. If compilation
succeeds, the built-in tests run again automatically. If compilation fails,
Studio blocks using the obsolete VM until a successful rebuild. Turn off
automatic rebuilding in Language Internals to build manually.

Open the symbol browser with **Ctrl+Shift+I** or the **Language C++**
toolbar button. Native source editing needs the checked-out project sources,
CMake, and a C++20 compiler; standalone prebuilt binaries cannot edit the
embedded interpreter. The editor does not hot-patch a running VM: changes
take effect after saving and successfully rebuilding.


## Modular C++ core

The C++20 interpreter now lives in `include/plusminus/` and `src/` and is built as a single static `plusminus_core` library. `Parser.h` remains as a compatibility header; `Parser.cpp` is removed. The runner is a separate executable linking the same library.

```sh
cmake -S . -B ide/build -DCMAKE_BUILD_TYPE=Release
cmake --build ide/build --config Release
ctest --test-dir ide/build -C Release --output-on-failure
```

The source launcher keeps the original double-click workflow. `Ctrl+click` in Studio 2.0 navigates to the compiler, VM and bytecode source files at their new locations. The Visual Studio native unit tests are grouped under `tests/cpp/` while retaining their original `TEST_CLASS` and `TEST_METHOD` definitions.

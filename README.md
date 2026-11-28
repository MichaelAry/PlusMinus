# PlusMinus and PlusMinus Studio

PlusMinus is a C++20 interpreter with a bytecode VM, concurrent execution,
a math library and thread-tagged drawing. PlusMinus Studio provides a desktop
editor, native C++ test lab, notebooks and execution analysis.

## Choose a desktop launcher

| Edition | Windows | Linux | macOS |
|---|---|---|---|
| **Studio 4** (default, Qt/PySide6) | [Start-PlusMinus.cmd](Start-PlusMinus.cmd) | [Start-PlusMinus.desktop](Start-PlusMinus.desktop) or `bash ./Start-PlusMinus.sh` | [Start-PlusMinus.command](Start-PlusMinus.command) |
| **Studio 5** (Tauri, parallel x64 candidate) | [Start-PlusMinus-Studio5.cmd](Start-PlusMinus-Studio5.cmd) | [Start-PlusMinus-Studio5.desktop](Start-PlusMinus-Studio5.desktop) or `bash ./Start-PlusMinus-Studio5.sh` | Intel build in CI |

Run the source launchers from a complete checkout. Linux file managers may
require marking the desktop shortcut as trusted. See platform prerequisites,
preflight and packaging in the [Studio 4 guide](ide/README.md) and
[Studio 5 guide](apps/studio/README.md).

Studio 4 launchers build the C++ executables and prepare a local Python
environment. Studio 5 launchers prepare native and frontend build dependencies,
build both C++ sidecars and start the Tauri development app. To check system
prerequisites without installing or building, use `python launch.py --check`,
`.\Start-PlusMinus-Studio5.cmd -Check` in PowerShell, or
`bash ./Start-PlusMinus-Studio5.sh --check` on Linux.

Portable Studio 4 bundles are built by the [desktop workflow](.github/workflows/desktop.yml).
Published tagged builds, when available, are listed on [GitHub Releases](https://github.com/MichaelAry/PlusMinus/releases).
Studio 5 package smoke checks and desktop acceptance criteria are in the
[Windows/Linux migration status](docs/migration/STAGE3_WINDOWS_LINUX.md).

## Workbench

| Area | Workflows |
|---|---|
| Editor | Edit multiple `.pm` files in tabs, split the editor, navigate source, and inspect compiler and lexical diagnostics. |
| Run and analysis | Compile or run source, inspect bytecode, profile executed opcode counts, and replay up to 5,000 VM trace events after execution. The control-flow graph comes from bytecode, and the call graph uses source heuristics. |
| Test Lab | Run built-in and custom PlusMinus cases or discover 225 original native C++ tests. Run individual tests or suites and compare SQLite baselines with commit and source metadata. |
| History and Git | Browse execution and native test history, export execution reports, and inspect local Git status and recent commits. |
| Notebooks | Open or save nbformat-v4 `.ipynb` files, edit Markdown and code cells, and run or interrupt code. Every cell starts a fresh PlusMinus process. |
| Language Internals | Navigate implementation files in a source checkout, edit C++ and rebuild native executables. Native inputs changed since the last successful build can invalidate execution or test discovery. |
| Plot Editor | Graph formulas and point tables, adjust parameters, zoom and pan, fit visible data, and save `.pmplot` documents. |

Studio 4 samples its C++ child processes for resource measurements. Studio 5's
Resources panel samples the Rust backend process. Both receive VM metrics from
the native runner. Child processes have timeouts and share the user's OS
privileges. Use a separate OS sandbox for untrusted source.

## Formulas and program drawing

- **Plot Editor.** Open **View → Plot Editor** in Studio 4. In Studio 5,
  choose **Plot Editor** in the activity rail or command palette, or use
  **Open Plot** to pick a document. Both use the same UTF-8 `.pmplot` v1
  format. [Try the examples](docs/plot-examples/README.md) or see the
  [format and editor guide](docs/PLOT_EDITOR_PLAN.md).
- **Drawing from PlusMinus code.** In a `.pm` program, `plot(x, y)` adds
  a point to the calling VM thread's curve, `point(x, y)` adds a dot,
  `line(x1, y1, x2, y2)` adds a segment, and `clear()` resets the buffer.
  The runner returns the captured events in a top-level JSON `plot` field.
  [Drawing protocol and math reference](docs/PLOT_PROTOCOL.md).

[examples/mandelbrot.pm](examples/mandelbrot.pm) uses complex arithmetic
and 32 `go` workers to emit 5,120 drawing events. With the build below, try
`./build/native/plusminus_runner run < examples/mandelbrot.pm` in a Unix shell.

## Build and test the interpreter

Install CMake 3.16+, a C++20 compiler and Python 3 for native test registration.
Run from the repository root.

```sh
cmake -S . -B build/native -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
```

CTest runs `core_smoke`, `drawer_smoke` (math and drawing), and
`native_quick` when Python 3 is available. Use the native test executable
to list all 225 original test methods, run a specific ID, or opt into the
full suite, including stress and benchmark cases.

```sh
./build/native/plusminus_native_tests --list
./build/native/plusminus_native_tests --run Class.Method
./build/native/plusminus_native_tests --suite full
```

Replace `Class.Method` with an ID from `--list`. For Windows Visual
Studio builds, executables are under `build/native/Release/` and end in
`.exe`. Use CMake on Windows too. The legacy
[Visual Studio project](UnitTest1.vcxproj) omits `src/vm/mathlib.cpp`,
which the current core requires.

The compiler lives in [src/compiler](src/compiler), the VM and Math
library in [src/vm](src/vm), and the C++ API in
[include/plusminus](include/plusminus). The root build produces the
`plusminus_core` static library and links it into `plusminus_runner`.
[Parser.h](Parser.h) forwards the legacy includes. The Qt launcher uses
[ide/CMakeLists.txt](ide/CMakeLists.txt) to keep the `ide/build` layout.

## Studio 5 migration reference

- [Feature parity and evidence](docs/migration/FEATURE_PARITY.md)
- [Runner and Tauri IPC contract](docs/migration/IPC_CONTRACT.md)
- [Acceptance checklist](docs/migration/PRE_CUTOVER_VERIFICATION.md)
- [Performance comparison protocol](docs/migration/PERFORMANCE_BASELINE.md)
- [Stage 2 audit](docs/migration/STAGE2_STATUS.md) and [original migration plan](docs/migration/STUDIO5_PLAN.md)

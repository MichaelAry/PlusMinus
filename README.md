# PlusMinus Studio 4.0 — Research Workbench

**A cross-platform desktop IDE and C++ interpreter test laboratory for PlusMinus (C++20).**

PlusMinus Studio 3.0 uses Qt/PySide6 with a tabbed, multi-document workspace,
a split editor, PlusMinus/C++ highlighting, source-positioned diagnostics,
automatic startup checks, portable native C++ test discovery and execution,
SQLite regression baselines, VM profiling and bounded trace replay.
Windows, Linux and macOS packages are built in GitHub Actions.

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
[GitHub Releases](https://github.com/MichaelAry/PlusMinus/releases) page *once a
successful tagged build has been published*:

- Windows: extract and double-click `PlusMinusStudio.exe`.
- Linux: extract and run `PlusMinusStudio/PlusMinusStudio` or the accompanying `.desktop` shortcut.
- macOS Intel: extract and open `PlusMinusStudio.app`.

The executable bundles Python, Qt, psutil and the C++ runner. macOS unsigned binaries
may require approval in Privacy & Security. Linux bundles depend on a compatible glibc.

## Plot Editor

Open **View → Plot Editor** to graph formulas and point tables together. Formula
parameters have live sliders and numeric fields. Use the mouse wheel to zoom
around the cursor, drag to pan, or choose **Fit** to frame visible data. Save your
series, parameters, colors, and viewport in a `.pmplot` file.

The [ready-to-open plot examples](docs/plot-examples/README.md) cover adjustable
waves, measurements with repeated X values, discontinuities, formula diagnostics,
and fitting hidden and visible series.

## Studio 3.0 features

| Area | Implemented |
|---|---|
| Workspace | Closable/reorderable section tabs, multiple open files, two-pane split editor, session restoration |
| Editor | PlusMinus and C++ highlighting, completion, comment toggle, symbol outline, Ctrl+click to editable language internals |
| Problems | Bracket and concurrency heuristics, compiler errors with source coordinates, inline highlights and Problems pane |
| Test Center | Fast startup suite, custom JSON suites, and **225 discoverable native C++ test methods** |
| Native C++ Lab | Quick/full/selected/filtered/failure-only runs, separate process for each case, cancellation and live status |
| Regression History | SQLite result sessions with Git commit, dirty state, source hash, per-test timing, saved baseline and diff |
| Profiler / Trace | Runtime opcode hit counts and capped trace replay (5,000 events), separate from compiled opcode counts |
| Analysis | Bytecode control flow graph, heuristic source call graph, resource measurements, Git status |
| Benchmarks | Warmup, repeated execution, median, mean, P95, standard deviation |
| Reports | Execution and test history; JSON/CSV export of general run history |

### Running the native C++ tests

The source launcher builds `plusminus_native_tests` alongside `plusminus_runner`.
Open **Test Center → Native C++ test suite**. **Run quick** excludes the slow
stress/benchmark cases; **Run all 225** runs every discovered method and may take
significantly longer. Use **Run filtered**, **Run failed**, or select an individual
method. Test results are stored in `~/.plusminus/studio.db`; select **Set baseline**
and **Compare baseline** after making C++ changes.

You can also use:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
./build/plusminus_native_tests --list
./build/plusminus_native_tests --suite full
```

On Windows, use `build/Release/plusminus_native_tests.exe` with multi-config generators.
The full suite includes stress tests and is not automatically executed at startup.
The portable `tests/portable/CppUnitTest.h` adapter preserves the existing 225 test
methods; it is **not** a general replacement for Microsoft's test framework.

**Measurement limits:** Static source diagnostics and call graphs are heuristic,
not comprehensive AST/type proofs. CPU/RSS are sampled; short-lived spikes can be
missed. A single test timing is not a statistically reliable performance benchmark.
Trace replay records up to 5,000 executed instructions; it is **not** a live,
pausable breakpoint debugger. Programs run in isolated child processes with
timeouts, not in a complete OS security sandbox.

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
the files under `src/compiler/` and `src/vm/`, allowing compiler/runtime selection
sections. It also provides core types/opcodes from `include/plusminus/bytecode.hpp`
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
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The source launcher keeps the original double-click workflow. `Ctrl+click` in Studio 2.0 navigates to the compiler, VM and bytecode source files at their new locations. The Visual Studio native unit tests are grouped under `tests/cpp/` while retaining their original `TEST_CLASS` and `TEST_METHOD` definitions.

The built-in function implementations (`print`, `len`, `resize`, `sin`, `cos`, `pow`, `fact`, `multifact`) reside in `src/vm/builtins.cpp` and can be opened directly from Language Internals. User-defined function dispatch remains in `src/vm/executor.cpp`.

For source-IDE launches, `launch.py` continues to configure `ide/build` with `cmake -S ide` to preserve existing CMake caches from previous versions. `ide/CMakeLists.txt` is now a compatibility wrapper around the root build; you can also configure the root CMake project separately in `build/` as shown above.


## Multi-tab workspace

Every left navigation item opens a separate workspace tab without replacing previous pages. Tabs are movable and individually closable; the open workspace pages are restored on the next launch.

The Code Editor also supports independent document tabs for multiple `.pm` files, with their own undo history, modification indicators, save prompts, de-duplicated opening and restored open paths. Loading test source opens a new tab rather than overwriting active source.

## Native C++ test laboratory

CMake now builds `plusminus_native_tests` using adapters generated from all **225** original Microsoft `TEST_METHOD` tests without rewriting their bodies. `--list` emits JSON Lines of test IDs and categories, `--run Class.Method` runs one original method with JSON timing and failures, `--suite quick` runs all except heavyweight scaling/benchmark classes, and `--suite full` includes them. CTest registers `native_quick` alongside `core_smoke`. Full suites remain opt-in because some concurrency benchmarks are expensive. The Visual Studio native unit-test project continues to exist and now links `src/vm/builtins.cpp`.

## Studio Native C++ Test Laboratory

Test Center now has two modes: fast built-in PlusMinus checks and the full original C++ suite. The Native tab discovers all methods and offers Run selected, Run quick (skips slow scaling classes), and Run all 225 (explicit opt-in); every method runs as a separate time-limited OS process so test crashes cannot crash Studio. Live results and sampled resource statistics are shown in the table. Each batch persists in SQLite with Git SHA, modified-tree flag, source fingerprint and platform. Set a baseline from the latest run and compare new failures, fixes, missing/new tests and per-method timing changes. Double-click a native test to open its C++ source in the multi-document editor.

## Code analysis graphs

The additional Code Analysis workspace displays a zoomable control-flow graph from compiled bytecode (branch targets and fall-through edges) and a heuristic call graph derived from PlusMinus function declarations/calls. Double-click a graph node to navigate to the compiled instruction or function source. Graph rendering caps very large bytecode programs to keep the UI responsive; the source call graph is marked heuristic rather than a full semantic proof. Profile mode (F6) now counts executed opcodes with atomic counters across VM threads, separate from static bytecode counts, and visualizes the dynamic distribution.

## Multithreaded drawing and Math library

The interpreter now exposes thread-tagged drawing primitives: `plot(x, y)`
adds a point to the calling thread's connected curve, `point(x, y)` adds an
unconnected dot, `line(x1, y1, x2, y2)` adds a segment, and `clear()` resets
the buffer. Every event records the VM thread ordinal (main thread `0`,
workers `1..N`), so a renderer can colour one curve per thread and show the
actual concurrency of the program.

The one-shot runner returns this data in the new `plot` field of its JSON
report (`events`, `truncated`, `threads`), alongside the existing `bytecode`
listing and the thread-aware `trace` events. `report.bytecode` is available
in every mode; `report.trace` (bounded to 5,000 events) is collected in
`trace` mode and lets a bytecode view highlight executed instructions per
thread. The capture is bounded to 50,000 drawing primitives. See
`docs/PLOT_PROTOCOL.md` for the exact protocol.

`examples/mandelbrot.pm` is the default demonstration: 32 `go row(...)`
workers draw 160 points each (5,120 events), using complex numbers through
the new Math library. All non-trivial arithmetic now lives in
`include/plusminus/math.hpp` / `src/vm/mathlib.cpp`: complex values
(`complex(re, im)`, `re`, `im`, `conj`, `arg`, `abs`) participate in the
ordinary `+ - * / ^` operators, and the scalar functions (`sin`, `cos`,
`sqrt`, `log`, `pow`, `min`, `max`, ...) are provided there instead of being
scattered through the VM.

## Git-aware history and regression trends

History & Reports contains separate panes for program runs, C++ testing sessions, and a read-only Git summary. Native session graphs visualize pass percentages and elapsed suite time across runs, while each stored session retains commit SHA, source fingerprint, platform, and per-test verdicts. The Git pane shows branch, dirty working tree, diff summary and recent commits without making changes to the repository. All Git operations are local-only and optional.

## Bounded VM trace replay

F7 runs the C++ VM with a thread-safe, bounded instruction trace (maximum 5,000 opcode events). Runtime Profiler has a recorded-step slider and Previous/Next controls; each event displays instruction pointer, opcode, VM thread ordinal and stack depth. Recorded events can be inspected alongside the compiled bytecode. This is *post-execution replay*, not a live source-level debugger: interactive breakpoints, variable snapshots and Step Into/Over/Out are not implemented. Trace capture may affect performance, so normal Run and Profile do not collect step traces. Output includes `trace_truncated` when the bound is reached.

## Split source workspace

Click **Split Editor** in Code Editor to open a second live, editable pane beside the source tabs. Use the right-hand file selector to show any currently open source file. Both panes can edit the same underlying Qt document with separate cursors; edits are shared immediately rather than copied. Split mode is saved with the session and can be closed independently. Closing a source document updates the secondary selector to avoid a stale document reference.


## Research Workbench 4.0 UI

The Graphite Research shell retains all existing C++ VM and Studio 3 services
while adding an Activity Bar, movable/dockable **Explorer**, **Inspector**, and
**Output and Diagnostics** panels, and an accessible command palette
(`Ctrl+Shift+P`). The Explorer supports opening `.pm`, C++ sources and
`.ipynb` files from the checkout. The six activity modes (Develop, Test Lab,
Notebooks, Language Lab, Performance, Source Control) are workspace presets;
they keep existing document tabs intact. Dock layouts are stored under
`QSettings('PlusMinus', 'Studio4')`, with migration of Studio2 settings.

### Native C++ Test Analysis

In **Test Lab → C++ Test Analysis**, select a registered method to inspect
the corresponding C++ source (when available), a clearly labelled lexical
summary of assertions and interpreter API calls, its last recorded outcome,
and its SQLite history. **Run method** executes the selected real native test;
**Compare baseline** uses the existing persisted test sessions. Source coverage
is displayed as unavailable until instrumentation produces measured data.

### Notebook documents

Open **Notebooks** from the Activity Bar and create/open `.ipynb` files.
The implementation uses standard nbformat-v4 JSON, code and Markdown cells,
reordering/removing cells, read-only results, Run Cell, Run All and Interrupt.
Code cells run **out-of-process in isolated PlusMinus VM processes**. This is
real execution, but NOT a persistent Jupyter kernel; variables/functions do
not carry over from one code cell to another. The UI explicitly communicates
this. No network dependencies or embedded browser are required.

The ordinary source launcher, CMake build, local unit-test history, Windows
and Unix launch scripts and standalone packaging remain supported.

## Studio 4.0 GUI reliability fixes

The **Explorer and Activity Bar are permanent** (not closable or floatable),
including after restoring older layouts. Workspace switches no longer
automatically hide the bottom output dock. Every program run — successful,
failed, empty stdout or compilation failure — opens **Run / Metrics** with
actual output and execution measurements side by side. Missing process samples
are shown as *not measured*, not as zero. The output panel reopens automatically
when a new run begins. Runtime errors remain visible alongside diagnostics.

Notebook **Shift+Enter / Ctrl+Enter** executes the current cell. After executing
the last code cell, the editor appends one focused empty code cell; reruns do not
create duplicates. The global **Run (F5)** and **Save (Ctrl+S)** commands work on
the active notebook rather than a hidden source editor. Cells store execution
timings and output using the Jupyter v4 schema; edits warn about stale outputs.
The global Stop action interrupts notebook executions too. Notebook cells are
still isolated and do not share persistent VM state.

The Test Laboratory now updates incoming native C++ test results incrementally,
retains selection, and keeps the source inspector open when running its selected
method. Headless Qt smoke checks cover these behaviors on Linux, macOS and Windows.

Source edits in `src/`, `include/`, `ide/runner.cpp` and C++ tests
invalidate the affected native binaries until a successful rebuild. Pressing
Save on an unchanged C++ file no longer needlessly invalidates the VM. Native
Test Lab Refresh will not silently rediscover an obsolete test executable
while source changes await rebuilding.


## Windows GUI startup crash (0xC0000005)

If the launcher reports exit code **3221225477** (Windows access violation),
the C++ interpreter executable may be fine: the crash can occur when Qt shows
its main window. Standard CI's offscreen GUI tests do **not** reproduce every
graphics driver / shell extension / DPI / stale layout problem.

* The launcher now records faulthandler stacks and startup phases to
  `%USERPROFILE%\\.plusminus\\studio-startup.log` on Windows.
* After exactly one Windows access violation, it **automatically retries once
  in safe mode**. Safe mode disables saved geometry/dock restoration,
  native filesystem watchers and custom directory icons, automatic startup
  tests and telemetry polling, and requests software rendering. It does
  not delete or overwrite existing settings, notebooks, or SQLite history.
* To launch safe mode directly from PowerShell:
  `./Start-PlusMinus.cmd --safe-mode`.
* To distinguish Qt platform problems from Studio widgets:
  `.\\.venv\\Scripts\\python.exe -X faulthandler .\\ide\\studio_qt.py --qt-probe`.
  The probe opens a minimal widget briefly and exits.
* To test the Studio widgets without startup workers:
  `.\\.venv\\Scripts\\python.exe -X faulthandler .\\ide\\studio_qt.py --safe-mode --gui-smoke`.
* The final line in the startup log identifies the last completed phase.
  If `main: calling window.show()` is present but
  `main: window.show() returned` is absent, the failure is in native
  window display/polishing. This alone does **not** identify its root cause.

If the minimal Qt probe also crashes, capture the Windows Event Viewer
Application Error entry (faulting module and exception code), and record
Python / PySide6 / Qt versions before changing dependencies. Never delete
`%USERPROFILE%\\.plusminus` merely to troubleshoot a startup failure.

## Studio 5 Windows/Linux x64 candidate

The Tauri/Rust/React desktop workbench in `apps/studio/` is in Stage 3
pre-cutover review, **NOT READY** to replace Qt. The original source
launch scripts and Qt data remain intact.

See [Stage 3 acceptance, packaging and rollback](docs/migration/STAGE3_WINDOWS_LINUX.md)
and [performance comparison matrix](docs/migration/PERFORMANCE_BASELINE.md).

## Studio 5: one-click launch on Windows x64 / Linux x64

Use the new **separate** Studio 5 launchers from a complete source checkout:
- Windows: double-click [Start-PlusMinus-Studio5.cmd](Start-PlusMinus-Studio5.cmd).
  It uses winget to install missing Node.js LTS/npm, Rust/Cargo (MSVC target),
  CMake, Python3, Visual Studio C++ Build Tools and WebView2. UAC and a reboot
  may be required for machine-wide packages.
- Linux: run [Start-PlusMinus-Studio5.sh](Start-PlusMinus-Studio5.sh), or launch
  the [desktop shortcut](Start-PlusMinus-Studio5.desktop) from the repository
  (mark as trusted if requested). The supported package managers are apt
  (Debian/Ubuntu), dnf (Fedora) and pacman (Arch). sudo prompts for a password.
  Node.js 24 LTS is installed under the user home when needed after checking
  the official SHA256 manifest; Rust is installed through official rustup.

The launchers verify installed tools, build unchanged C++20 sidecars into a
dedicated incremental CMake directory, stage the native binaries, install npm
modules as needed, and run `npm run tauri dev`. This is the full application in
**development mode**, NOT a signed production installer. A first-time setup
needs Internet access, free disk space and permission to install system packages.

To inspect requirements without installing or building, run:
- Windows: `.\Start-PlusMinus-Studio5.cmd -Check`
- Linux: `bash ./Start-PlusMinus-Studio5.sh --check`

To prohibit installing packages, use `-NoInstall` (Windows) or
`--no-install` (Linux). On errors the launcher stops and reports the cause.
The original `Start-PlusMinus.cmd` and `Start-PlusMinus.sh` still launch Qt
Studio 4, and original .pm/.ipynb files and studio.db are not modified
by bootstrap. Windows/Linux x64 only.

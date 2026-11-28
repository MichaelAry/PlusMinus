# PlusMinus Studio 4

Studio 4 is the default Qt/PySide6 research workbench. The Graphite shell
has an activity bar, movable Explorer, Inspector and Output and Diagnostics
docks, plus a command palette (**Ctrl+Shift+P**). Develop, Test Lab,
Notebooks, Language Lab, Performance and Source Control are workspace
presets that keep open documents. The Explorer and activity bar stay
available across presets.

## Launch and package

From the repository root, use the platform's [Studio 4 launcher](../README.md#choose-a-desktop-launcher)
or run `python launch.py`. The launcher needs Python 3.9+ with venv/pip,
CMake and a C++20 toolchain. Use Visual Studio C++ tools on Windows and
Apple Command Line Tools on macOS. The launcher builds the C++ runner,
creates `.venv` and installs the dependencies from [requirements.txt](requirements.txt).
The GUI uses PySide6-Essentials and psutil.

| Command | Operation |
|---|---|
| `python launch.py --check` | Inspect Python, Qt, CMake, compiler and runner. |
| `python launch.py --no-install` | Start using installed prerequisites. |
| `python launch.py --build-only` | Build native targets without starting Qt. |
| `python launch.py --test` | Build and run the five CLI regression checks in `ide/smoke_test.py`. |
| `python launch.py --rebuild` | Force a fresh native build. |
| `python launch.py --safe-mode` | Start with a clean in-memory window layout, software rendering and startup workers disabled. |

Build and check a portable bundle on Linux/macOS from the repository root.
On Windows, use `.venv/Scripts/python.exe` and omit `QT_QPA_PLATFORM=offscreen`
to check native window startup.

```sh
python3 launch.py --build-only
python3 -m venv .venv
.venv/bin/python -m pip install -r ide/requirements.txt pyinstaller==6.16.0
.venv/bin/python -m unittest discover -s tools -p 'test_*.py'
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/smoke_qt.py
.venv/bin/python tools/package.py
```

The workflow bundles both C++ executables, Qt, Python and psutil for each OS.
Extract and start `PlusMinusStudio.exe` on Windows,
`PlusMinusStudio/PlusMinusStudio` on Linux, or `PlusMinusStudio.app` on
Intel macOS. Linux requires a compatible glibc. Unsigned macOS bundles may
require approval in Privacy & Security. [Desktop build workflow](../.github/workflows/desktop.yml).

## Use the workbench

- **Editor.** Open multiple `.pm` files or split the editor. Two views of
  the same source share edits and have independent cursors. Diagnostics
  include source-positioned compiler errors and lexical checks.
- **Execution.** F5 runs, F6 profiles executed opcodes and F7 records up
  to 5,000 instructions for replay. Run / Metrics opens on completion
  even for empty stdout or a language error. CPU/RSS are sampled and
  unavailable measurements are marked accordingly.
- **Native C++ tests.** Open **Test Center → Native C++ test suite** to run
  quick, full, filtered, failed or selected methods. The full suite includes
  all 225 original cases and runs on request. Results stream into the table.
  Source and assertion summaries are available in **Test Lab → C++ Test Analysis**.
  Studio records outcomes, timings, Git SHA, dirty state and source hashes in
  `~/.plusminus/studio.db` for history and baseline comparisons.
- **Notebooks.** Open or create `.ipynb` files in Notebooks. Use
  **Shift+Enter** or **Ctrl+Enter** to run a cell. **F5** in the notebook
  workspace targets the focused code cell or the last nonempty code cell.
  **Run all** queues code cells, and Stop interrupts execution. Completing
  the last code cell appends one focused blank cell. Outputs use nbformat v4
  and edits can mark them stale. Each code cell gets its own VM.
- **Plots.** Use **View → Plot Editor** or the global **Open** dialog to
  open a `.pmplot` document. When the plot is active, **Ctrl+S** saves it.
  [Examples and controls](../docs/plot-examples/README.md).

Dock layouts and last-plot selection use `QSettings('PlusMinus', 'Studio4')`.
The Qt shell can migrate earlier Studio2 settings. The earlier Tkinter GUI
is retained in [app.py](app.py).

## Edit the language

**Ctrl+click** a keyword or builtin in PlusMinus source to navigate to its
C++ implementation. **Ctrl+Shift+I** opens the Language Internals browser
for compiler, VM, math, bytecode and runner code. Save with **Ctrl+S** to
write the source atomically and create a backup in `.plusminus-backups/`.
With automatic rebuilding enabled, a successful VM build reruns the built-in
checks. Changes to native inputs invalidate the affected executables until
a successful build. Saving an unchanged C++ file keeps the existing build
valid. Language editing requires a source checkout and native toolchain.

Main modules are [studio_qt.py](studio_qt.py) and [research_shell.py](research_shell.py)
for the UI, [engine.py](engine.py) for C++ execution and process samples,
[analytics.py](analytics.py) and [native_tests.py](native_tests.py) for
history and testing, and [runner.cpp](runner.cpp) for the native JSON adapter.

## Windows startup recovery

For exit code **3221225477** (`0xC0000005`), the launcher retries once in
safe mode. Safe mode skips saved geometry, dock restoration, native filesystem
watchers and custom directory icons, startup tests and telemetry polling.
Existing Qt settings, notebooks and history are preserved.

From PowerShell, use the safe-mode launcher or run the Qt-only and Studio
window probes after preparing the local environment:

```powershell
.\Start-PlusMinus.cmd --safe-mode
.\.venv\Scripts\python.exe -X faulthandler .\ide\studio_qt.py --qt-probe
.\.venv\Scripts\python.exe -X faulthandler .\ide\studio_qt.py --safe-mode --gui-smoke
```

Check `%USERPROFILE%\.plusminus\studio-startup.log` for the last completed
startup phase. If the log reaches `main: calling window.show()` without
returning from `window.show()`, inspect the Windows Event Viewer Application
Error entry for the faulting module and exception code. Record Python,
PySide6 and Qt versions when reporting the failure.

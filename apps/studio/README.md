# PlusMinus Studio 5 — Windows/Linux x64 Stage 3 candidate (not cut over)

Experimental Tauri 2 / Rust / React / TypeScript / Vite / Monaco / Dockview GUI.
This is a **parallel replacement**, not a removal of the working Qt Studio 4.

## Prerequisites
- Node.js 22+, Rust stable, CMake and a C++20 toolchain.
- Tauri v2 native OS prerequisites: WebView2 on Windows, WebKitGTK 4.1 on Linux, Xcode Command Line Tools on macOS.
- A checked-out PlusMinus source tree. The C++20 core is not modified.

## Run in development
From repository root:

~~~sh
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --config Release
ctest --test-dir build/studio5 -C Release --output-on-failure
node scripts/stage-native.mjs --build-dir build/studio5
cd apps/studio
npm install
npm run tauri dev
~~~

Stage sidecars again after rebuilding C++. For checks:

~~~sh
cd apps/studio
npm run typecheck
npm run test
cargo test --manifest-path src-tauri/Cargo.toml
npm run tauri build
~~~

## Stage 1 scope
Choose a workspace folder with the native system dialog. The explorer lists
.pm documents up to depth four; symlinks are skipped. Open .pm files, use
Monaco editing, create/save with on-disk conflict detection, and run
Run / Compile / Profile / Trace on exactly the editor source.

The C++ runner is one-shot. stdin requires UTF-8 and EOF; stdout contains
one JSON result, compilation errors return a nonzero exit with ok=false.
No JSON-RPC, permanent kernel, AST service or live debugger is claimed.
The trace is an existing bounded post-execution replay.

Frontend has no generic shell/filesystem plugin permissions. Rust enforces
workspace path validation and restricted executable selection.

## Known limitations
- 225-test UI, SQLite history, notebooks and Language Lab are Stage 2.
- No live CPU/RSS sampling yet. Missing metrics read "not measured".
- Cancellation is a best-effort process kill, not a complete sandbox or
  process-tree/job-object manager (Stage 3 hardening).
- .pm files max 2 MiB; C++ runner source max 1 MiB; stdout max 8 MiB.
- Workspace/session restoration and deeper file browsing are Stage 2.
- The original Qt launcher/CI remain supported.
- Installed package smoke testing on actual OS desktops remains a gate.

See docs/migration/ for the audited baseline, IPC rules and remaining stages.

## Stage 2 research panels (work in progress)

The activity rail and Ctrl+Shift+P command palette open Test Lab (native C++ tests and regression history), Source Tests (Studio 4 built-ins and copied user cases), Notebook, Profiler/Resource graphs, Compiler Explorer (bytecode CFG and heuristic call graph), Git Inspector and Language Internals. Dockview layouts are saved locally; Monaco can be split into two panels with shared document models.

The first Stage 2 launch copies the legacy SQLite database into ~/.plusminus/studio-v5.db through SQLite Backup API; it never migrates by overwriting the original. User test JSON definitions are likewise copied to ~/.plusminus/user_tests-v5.json, leaving the original untouched. Read-only Qt portable preferences can be exported with Python and PySide6 using scripts/export-studio4-settings.py; window geometry bytes cannot migrate to Dockview.

Notebooks are nbformat v4 and isolated per cell, without shared VM state. Source changes are tracked for C++ rebuilds; any failed rebuild leaves native execution stale. Use a source checkout for Language Internals; packaged binaries need not include C++ sources.

**Stage 2 is not approved for final cutover yet.** Follow docs/migration/STAGE2_STATUS.md for exact pending feature-parity and desktop smoke criteria. The original Qt application remains usable.

## Windows/Linux x64 Stage 3 acceptance and fallback

Source/release builds use Tauri 2, Rust, React, Monaco, Dockview and the
original unmodified native C++ sidecars; no Python or PySide6 is needed to
run an installed Studio 5 itself. The normal `Start-PlusMinus.cmd` and
`Start-PlusMinus.sh` continue to launch the original Qt Studio 4.

Clean file tabs can reopen after explicitly choosing the same workspace;
unsaved source bytes are not persisted. Process-tree termination is
best-effort (Linux groups, Windows taskkill) and has not been independently
verified under adversarial descendants. See `docs/migration/STAGE3_WINDOWS_LINUX.md`.

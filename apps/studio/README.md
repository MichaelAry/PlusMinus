# PlusMinus Studio 5 — Stage 1 foundation

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

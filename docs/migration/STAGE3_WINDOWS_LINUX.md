# Studio 5 Stage 3 — Windows x64 and Linux x64

**Base master SHA:** `a33ad24582f11594ada2118e0a5764d33d53f44d`.
**Branch:** `feature/studio5-cutover`; **PR:** #23 (DRAFT, no auto-merge).
macOS/ARM64 are not in the user-requested Stage 3 scope.

## Code and acceptance findings

The runner accepts `run|compile|profile|trace` as its only native execution
verbs; source is UTF-8 stdin with mandatory EOF; a single original C++ JSON
response is decoded by Rust. Native tests use `--list` and `--run ID`. Trace
events are available only AFTER execution, limited to 5000; no live breakpoints,
persistent shared-state notebook kernel, AST API or JSON-RPC is claimed.

| Check | Evidence | Current acceptance |
|---|---|---|
| Preserve C++20/Qt files and launch scripts | Immutable baseline and branch diff | PASS after final diff |
| Source execution/IPC | Existing tests and strict report validator | PARTIAL — installed GUI not verified |
| Multi-document/split view | Monaco/Dockview, new concurrent open fix | PARTIAL — 20-tab E2E not verified |
| Clean session tab restore | New `model/session.ts` and Vitest | PARTIAL — user must reselect workspace; unsaved edits not persisted |
| File saves | Same-process optimistic digest lock across file types | PARTIAL — external editor races remain |
| Test Lab / native cases | CI 225-case isolation and new MSI/deb sidecar smoke | NOT VERIFIED on latest commit |
| Cancel/timeout and descendants | Unix process groups; Windows taskkill /T /F | PARTIAL — no Job Object or adversarial orphan proof |
| SQLite migration | Separate `studio-v5.db` from read-only old DB | PARTIAL — representative nonempty Qt migration not verified |
| Large graphs, ECharts, notebooks | Lazy-loaded panels; virtualized test/trace lists | PARTIAL — real GUI profiling absent |
| Windows x64 packaged sidecars | MSI extraction/PE architecture/runner+one test script | NOT VERIFIED until CI green |
| Linux x64 packaged sidecars | deb extraction/runner/one test/Xvfb startup script | NOT VERIFIED until CI green |
| GUI parity, large sessions and perf | 12-case comparison method in PERFORMANCE_BASELINE | NOT MEASURED |
| Qt rollback and original data | Qt scripts and `~/.plusminus/studio.db` unchanged | AVAILABLE, acceptance drill NOT VERIFIED |

**Decision: NOT READY**. The default launcher must NOT be switched at this
stage. Do not merge until blockers are resolved and checks actually pass.

## Build, check and package commands

From the repository root (Windows PowerShell or Linux shell; adapt syntax):

~~~text
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --config Release --parallel 2
ctest --test-dir build/studio5 -C Release --output-on-failure
node scripts/verify-native-isolation.mjs --build-dir build/studio5
node scripts/smoke-native.mjs --build-dir build/studio5
python scripts/check-qt-native-parity.py --build-dir build/studio5
node scripts/stage-native.mjs --build-dir build/studio5
cd apps/studio
npm install --no-audit --no-fund
npm run test
npm run typecheck
npm run lint:types
npm run build:ui
cargo check --all-targets --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --all-targets --manifest-path src-tauri/Cargo.toml
npm run tauri build
~~~

CI smoke: `bash scripts/smoke-packaged-linux.sh` against a Linux deb;
`powershell -File scripts/smoke-packaged-windows.ps1` against a Windows MSI.
A successful package build is **not** a successful installed GUI interaction.

## Install and rollback

**Windows x64 test candidate:** use the Windows x64 MSI artifact from the
successful PR CI run on a machine with WebView2. **Linux x64 test candidate:**
use the deb artifact on a Linux WebKitGTK 4.1 installation. They are
pre-production candidates and use the unmodified C++ sidecar executables;
Studio 5 runtime does not require PySide6 or Python.

To resume Studio 4, close Studio 5 and run
`Start-PlusMinus.cmd` on Windows, `sh ./Start-PlusMinus.sh` on Linux or
`python launch.py --no-install` with Qt prerequisites. Do not remove old
`~/.plusminus/studio.db`, Qt settings, `.pm`, `.ipynb`, C++ sources, or
`studio-v5.db`. Save or discard unsaved edits before switching. Keep
a backup of notebooks modified between the two versions. For rollback of
the checkout itself, use the preserved Stage 2 merge commit `a33ad245`.

## Outstanding proof before a real cutover

- Windows/Linux packaged GUI Run/Compile/Profile/Trace, notebooks, split
  editor, 20 tabs, persisted history, Test Lab, diagrams, keyboard and DPI.
- End-to-end process cancellation, timeout and child descendants, including
  Windows Job Object cleanup for strong guarantees.
- Nonempty original SQLite migration including runs, native sessions/results,
  baselines, original source DB checksum and power-loss/recovery failures.
- Qt-vs-Tauri GUI measurement on the SAME hardware for all 12 workloads;
  raw data and memory-leak monitoring, including Linux X11 and Wayland.

See `PERFORMANCE_BASELINE.md` for all 12 workloads marked NOT MEASURED.

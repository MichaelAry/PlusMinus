# Studio 5 Stage 3 — Windows x64 and Linux x64

PR #23 merged at `97b5d2c`. PRs #24–25 and commits `8036ce1` and
`a27a9a6` added and hardened the separate source launchers.
Stage 3 desktop acceptance covers Windows and Linux x64. Intel macOS
builds run in CI.

## Code and acceptance findings

The runner accepts `run|compile|profile|trace` as its only native execution
verbs. Rust passes UTF-8 source over stdin, closes it to signal EOF and reads
one C++ JSON response. Native tests use `--list` and `--run ID`. Trace
provides up to 5,000 recorded events after execution.

| Check | Evidence | Current acceptance |
|---|---|---|
| Default Qt launch | Original `Start-PlusMinus` entry points | Available. Both editions build the shared engine, which gained Math and native drawing in PR #26. |
| Source execution/IPC | Existing tests and strict report validator | PARTIAL — installed GUI not verified |
| Multi-document/split view | Monaco/Dockview, new concurrent open fix | PARTIAL — 20-tab E2E not verified |
| Clean session tab restore | New `model/session.ts` and Vitest | PARTIAL — user must reselect workspace; unsaved edits not persisted |
| File saves | Same-process optimistic digest lock across file types | PARTIAL — external editor races remain |
| Test Lab / native cases | CI 225-case isolation and new MSI/deb sidecar smoke | NOT VERIFIED on latest commit |
| Cancel/timeout and descendants | Unix process groups with a Linux grandchild regression, Windows best-effort `taskkill /T /F` | PARTIAL — Windows descendant behavior needs desktop verification |
| SQLite migration | Separate `studio-v5.db` from read-only old DB | PARTIAL — representative nonempty Qt migration not verified |
| Large graphs, ECharts, notebooks | Lazy-loaded panels; virtualized test/trace lists | PARTIAL — real GUI profiling absent |
| Windows x64 packaged sidecars | MSI extraction/PE architecture/runner+one test script | NOT VERIFIED until CI green |
| Linux x64 packaged sidecars | deb extraction/runner/one test/Xvfb startup script | NOT VERIFIED until CI green |
| GUI parity, large sessions and perf | 12-case comparison method in PERFORMANCE_BASELINE | NOT MEASURED |
| Qt rollback and original data | Qt scripts and `~/.plusminus/studio.db` unchanged | AVAILABLE, acceptance drill NOT VERIFIED |
| Source launchers | Windows PowerShell 5.1 bootstrap checks and Linux preflight workflow | PARTIAL — complete first-run install and desktop launch remain acceptance checks |
| Plot Editor | Shared .pmplot fixtures, Qt smoke, Studio 5 Vitest and Rust round-trip | PARTIAL — installed WebView detach/dock and cross-version file workflows need testing |

Studio 5 remains a parallel candidate. The default launcher continues to
open Studio 4.

## Build, check and package commands

See the [launcher and manual build guide](../../apps/studio/README.md)
for prerequisites and the Linux development port fallback. Run these
verification commands from the repository root:

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

After packaging, `bash scripts/smoke-packaged-linux.sh` extracts the deb,
executes both sidecars and checks startup under Xvfb.
`powershell -File scripts/smoke-packaged-windows.ps1` uses the CI
`RUNNER_TEMP` directory to extract the MSI and verify x64 sidecars.
Interactive workflows are listed in the [acceptance checklist](PRE_CUTOVER_VERIFICATION.md).

## Install and rollback

**Windows x64 test candidate:** use the Windows x64 MSI artifact from the
successful Studio 5 workflow run on a machine with WebView2. **Linux x64 test candidate:**
use the deb artifact on a Linux WebKitGTK 4.1 installation. They are
pre-production candidates and bundle the C++ sidecars built from their
checkout. The installed runtime consists of the native app, the OS
webview and the sidecars.

To resume Studio 4, close Studio 5 and run
`Start-PlusMinus.cmd` on Windows, `sh ./Start-PlusMinus.sh` on Linux or
`python launch.py --no-install` with Qt prerequisites. Do not remove old
`~/.plusminus/studio.db`, Qt settings, `.pm`, `.ipynb`, C++ sources, or
`studio-v5.db`. Save or discard unsaved edits before switching. Keep
a backup of shared documents when comparing builds. The Stage 2
baseline used for migration comparisons is `a33ad245`.

## Outstanding proof before a real cutover

- Windows/Linux packaged GUI Run/Compile/Profile/Trace, notebooks, split
  editor, 20 tabs, persisted history, Test Lab, diagrams, keyboard and DPI.
- Plot open/save/conflict recovery, close prompts and detach/re-dock in
  WebView2 and WebKitGTK. Round-trip sample documents through both apps.
- End-to-end process cancellation, timeout and child descendants, including
  Windows Job Object cleanup for strong guarantees.
- Nonempty original SQLite migration including runs, native sessions/results,
  baselines, original source DB checksum and power-loss/recovery failures.
- Qt-vs-Tauri GUI measurement on the SAME hardware for all 12 workloads;
  raw data and memory-leak monitoring, including Linux X11 and Wayland.

See the [performance baseline](PERFORMANCE_BASELINE.md) for the 12 workloads.

# PlusMinus Studio 5 — pre-Stage-3 acceptance checklist

Target: merged foundation and parity plus PR #21 hardening. The C++20 engine, Qt Studio 4, original CMake, launch.py, and studio.db must be preserved.

## Automated checks on the current head

- [ ] Original Qt CI green on Windows, Linux and macOS.
- [ ] Original CTest quick suite and native runner smoke green.
- [ ] All 225 native tests executed as individual independent C++ processes using scripts/verify-native-isolation.mjs; exact JSONL ID, PASS and exit 0 checked on three OS.
- [ ] TypeScript, Vitest, Rust tests and Tauri package pass all three OS.
- [ ] Linux packaged .deb includes working C++ sidecars and launches GUI under Xvfb.
- [ ] Verify immutable C++ and Qt paths against original commit 41360ed7; no modifications to src/, include/, tests/cpp/, tests/portable/, ide/runner.cpp, CMakeLists.txt, launch.py or ide/studio_qt.py.

## Installed GUI checks on each OS (not covered by CI unit tests)

- [ ] Open an actual packaged Tauri GUI and check Graphite Research, Monaco, Dockview split editor and 20 document tabs.
- [ ] Run, Compile, Profile and Trace via GUI; compare with Qt using the identical unchanged C++ binaries. Test empty stdout, numeric return 0, compile error diagnostics and unavailable metrics.
- [ ] Verify cancel/timeout, quick/full/filtered/failed/selected native Test Lab, results, source inspector, baseline comparisons, closure/reopening of Dockview panels.
- [ ] Open a legacy Jupyter v4 notebook missing cell IDs; verify normalization, per-cell isolation, retained custom metadata, Run All and correct cell result target.
- [ ] Verify Markdown, Shift+Enter, Ctrl+Enter, Ctrl+S and toolbar Save, notebook closure and restoration of unsaved edits, workspace switching and file-conflict handling.
- [ ] Test history CSV/JSON export, source diagnostics, CFG/call graph, Git read-only inspector, profiler and trace navigation up to 5000 events.
- [ ] Modify a protected C++ source with an external editor; confirm old native binary is refused until successful CMake rebuild; verify changed sources during rebuild are rejected.
- [ ] Verify Windows read-only and failed-replace file recovery, and check no original user files were overwritten.

## Real nonempty SQLite migration safety

1. Create a disposable SQLite backup from a genuine nonempty Studio 4 database, including any WAL changes. Do not operate on the live source.
2. Record SHA256 of the original snapshot, four source table row counts, baseline entries and session metadata.
3. Start Studio 5 against the disposable HOME and trigger history initialization, producing studio-v5.db.
4. Check PRAGMA integrity_check, row count, legacy IDs, values, baseline, Git SHA and source fingerprint. Confirm original backup unchanged.
5. Create new Studio 5 sessions and compare old Qt win32/darwin platform labels with equivalent Rust windows/macos labels.
6. Inject interrupted backup/read-only and conflict failures, verify no data loss and no original database alteration.

## Stage 3 performance and release readiness

- [ ] Cold/warm startup, combined WebView + Rust + native child memory, 225 tests, 5000 trace events, 20 tabs, large notebooks and cursor-to-paint latency measured on the same hardware as Studio 4.
- [ ] Installed Windows, Linux X11/Wayland, macOS Intel and optionally ARM64 tested; preserve raw data, screenshots, environment and logs.
- [ ] Original Qt launch workflow, user studio.db and rollback remain operational.

Decision rule: code merged or CI green alone is not proof of installed GUI parity. Do not switch the default launcher or remove Qt until all applicable acceptance gates pass.

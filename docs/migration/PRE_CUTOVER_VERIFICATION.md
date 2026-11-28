# PlusMinus Studio 5 — cutover acceptance checklist

Use this checklist for a candidate checkout and its installed packages.
Desktop acceptance covers Windows and Linux x64. The Qt and Studio 5
workflows also build on Intel macOS.

## Automated checks on the current head

- [ ] Original Qt CI green on Windows, Linux and macOS.
- [ ] CTest `core_smoke`, `drawer_smoke`, `native_quick` and native runner smoke green.
- [ ] All 225 native tests executed as individual independent C++ processes using scripts/verify-native-isolation.mjs; exact JSONL ID, PASS and exit 0 checked on three OS.
- [ ] TypeScript, Vitest, Rust tests and Tauri package pass all three OS.
- [ ] Linux packaged .deb includes working C++ sidecars and launches GUI under Xvfb.
- [ ] Verify both desktop apps use native binaries built from the same current sources. Compare sidecar fingerprints, including the Math and drawing changes in PR #26.
- [ ] Windows and Linux bootstrap preflight runs without changing the checkout. Exercise Windows PowerShell 5.1 rustup handling and Linux's fallback when port 1420 is occupied.

## Installed GUI checks on Windows and Linux x64

- [ ] Open an actual packaged Tauri GUI and check Graphite Research, Monaco, Dockview split editor and 20 document tabs.
- [ ] Run, Compile, Profile and Trace via GUI and compare with Qt using identical C++ builds. Test empty stdout, numeric return 0, compile error diagnostics and unavailable metrics.
- [ ] Verify cancel/timeout, quick/full/filtered/failed/selected native Test Lab, results, source inspector, baseline comparisons, closure/reopening of Dockview panels.
- [ ] Open a legacy Jupyter v4 notebook missing cell IDs; verify normalization, per-cell isolation, retained custom metadata, Run All and correct cell result target.
- [ ] Verify Markdown, Shift+Enter, Ctrl+Enter, Ctrl+S and toolbar Save, notebook closure and restoration of unsaved edits, workspace switching and file-conflict handling.
- [ ] Test history CSV/JSON export, source diagnostics, CFG/call graph, Git read-only inspector, profiler and trace navigation up to 5000 events.
- [ ] Edit a C++ build input in a test checkout. Confirm the old native binary is refused until CMake rebuilds successfully. Repeat with an edit during rebuild to check stale-build detection.
- [ ] Verify Windows read-only and failed-replace file recovery, and check that original user files are preserved.
- [ ] Open the [same plot examples](../plot-examples/README.md) in each edition. Verify Save As and reopen, formula diagnostics, zoom/Fit, pan, detach/dock, Ctrl+S, file conflict detection in Studio 5 and last-file restoration.
- [ ] Verify Save, Discard and Cancel when replacing a dirty plot or closing the app. Test Studio 5's separate plot window and floating fallback where applicable.

## Real nonempty SQLite migration safety

1. Create a disposable SQLite backup from a genuine nonempty Studio 4 database, including any WAL changes. Do not operate on the live source.
2. Record SHA256 of the original snapshot, four source table row counts, baseline entries and session metadata.
3. Start Studio 5 against the disposable HOME and trigger history initialization, producing studio-v5.db.
4. Check PRAGMA integrity_check, row count, legacy IDs, values, baseline, Git SHA and source fingerprint. Confirm original backup unchanged.
5. Create new Studio 5 sessions and compare old Qt win32/darwin platform labels with equivalent Rust windows/macos labels.
6. Inject interrupted backup/read-only and conflict failures, verify no data loss and no original database alteration.

## Stage 3 performance and release readiness

- [ ] Cold/warm startup, combined WebView + Rust + native child memory, 225 tests, 5000 trace events, 20 tabs, large notebooks and cursor-to-paint latency measured on the same hardware as Studio 4.
- [ ] Installed Windows and Linux X11/Wayland tested. Preserve raw data, screenshots, environment and logs.
- [ ] Original Qt launch workflow, user studio.db and rollback remain operational.

Decision rule: code merged or CI green alone is not proof of installed GUI parity. Do not switch the default launcher or remove Qt until all applicable acceptance gates pass.

## Stage 3 restricted to Windows/Linux x64

- [ ] Both Windows/Linux original C++ CTest + 225 individual tests + native smoke green on latest commit.
- [ ] Frontend Vitest/typecheck/lint and Rust check/test/Clippy green on latest commit.
- [ ] Windows x64 extracted MSI runs bundled runner, lists 225 tests and executes one native case.
- [ ] Linux x64 extracted deb runs bundled runner/test and starts under X11/Xvfb.
- [ ] Installed GUI parity and notebook/history/source edits verified on both OS.
- [ ] Cancellation/timeout and descendant cleanup verified on both OS.
- [ ] Real nonempty Qt SQLite database migration verified with complete row and baseline comparison.
- [ ] Same-hardware Qt-vs-Tauri profiling and memory checks completed.
- [x] Default Qt launcher and separate Studio 5 history database are present.

Studio 4 remains the default while these checks are pending.
[Windows/Linux Stage 3 status](STAGE3_WINDOWS_LINUX.md).

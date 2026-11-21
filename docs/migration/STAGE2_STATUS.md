# PlusMinus Studio 5 — Stage 2 evidence ledger

**Branch:** `feature/studio5-parity` (Draft [PR #20](https://github.com/MichaelAry/PlusMinus/pull/20)).
**Source baseline:** stage-1 merged commit `c395dfe8` on `master`.
**Acceptance policy:** DONE requires verified functionality, not merely a class, button or PR description.
PARTIAL means implemented in part or missing comparable runtime evidence. BLOCKED
means impossible with the unchanged native protocol or presently not implemented.

## Architecture actually present

```text
Monaco / Dockview / React + Zustand / Virtual / ECharts / Cytoscape
                    | typed Tauri commands + Channel
             Rust / Tokio process services
                    | (TaskRegistry: progress, cancel, task snapshots)
       +------------+-----------------+-------------------+
       |                              |                   |
 plusminus_runner              plusminus_native_tests   SQLite Backup API
 run|compile|profile|trace     --list / --run ID         ~/.plusminus/studio.db (READ-ONLY)
 UTF-8 stdin then EOF          one process per test     -> ~/.plusminus/studio-v5.db
 one JSON report               JSONL results            independent DB
       |
 original, unchanged C++20 language engine / VM
```

The interface uses recorded, **post-execution** trace only (max 5000 native
events). No JSON-RPC server, pause/step/breakpoints, or persistent notebook VM.
User tests are copied from `user_tests.json` to `user_tests-v5.json`; Qt
QSettings exporter only reads original preferences.

## Detailed functional-parity audit

| Capability | Status | Source and repeatable check | Outstanding acceptance work |
|---|---|---|---|
| C++20 files, original CMake and Qt GUI preserved | DONE | Compare `master...feature/studio5-parity` with GitHub commit diff; protected paths unchanged | Keep checking on every later commit |
| Runner run/compile/profile/trace, EOF and JSON semantics | PARTIAL | `process.rs`, `scripts/smoke-native.mjs`; stage-1 CI exercised one-shot C++ runner | Installed Tauri invocation vs Qt fixtures must be demonstrated |
| Empty stdout, numeric 0, native compilation diagnostics | PARTIAL | `scripts/smoke-native.mjs`, `OutputPane.tsx` | UI end-to-end run and actual error rendering |
| Multi-file Monaco, tabs, split Dockview | PARTIAL | `EditorPane.tsx`, `App.tsx`, per-workspace models | Split focus independence, close/reopen and real UI smoke |
| .pm open/create/save and optimistic conflict | PARTIAL | `workspace.rs` test `pm_write_round_trip_preserves_content_and_detects_conflicts`; Windows replace backup | Cross-OS Rust tests and installed file-dialog smoke |
| 225 native C++ test discovery | PARTIAL | `native_tests.rs::discover`, `scripts/smoke-native.mjs` | Confirm on latest CI and packaged app |
| Per-test independent OS process, quick/full/filtered/failed | PARTIAL | `native_tests.rs`, `TestLab.tsx`; smoke runs 3 separate tests | Actual suite status/exit parity, resource exhaustion and all 225 |
| Two-worker concurrency, timeout and cancellation | PARTIAL | Tokio `JoinSet`, `kill_on_drop`, `CancellationToken` | Targeted cancellation, timeout, crash and orphan-process tests |
| TaskRegistry, progress and panel reattachment | PARTIAL | `tasks.rs`, `TaskSnapshot`, `list_tasks`, `TestLab.tsx` polling | Task state is process-local, not recovered across application restarts |
| Test inspector, navigation to C++ sources | PARTIAL | `TestLab.tsx`, `extra_files.rs`, `EditorPane.tsx` anchors | End-to-end anchor navigation in installed GUI |
| SQLite copy without modifying Studio 4 DB | PARTIAL | `history.rs::initialize_at`, SQLite Backup API, read-only source; disk fixture `real_disk_studio4_migration_is_lossless_and_read_only` | Test on real existing nonempty Studio 4 database; backup failure cases |
| Runs / native sessions / original baselines / diff | PARTIAL | `history.rs`, `HistoryPanel.tsx`; source fingerprint ordering matched to Qt | Verify cross-version baseline and historical retention in real data |
| Complete CSV/JSON export of program history | PARTIAL | `history.rs::export_runs_to`, `HistoryPanel.tsx` and Rust serialization test | UI save-dialog smoke and large dataset checks remain |
| User-defined test JSON import/export | PARTIAL | `user_tests.rs`, `SourceTestsPanel.tsx` | Actual Qt user_tests.json fixture and UI smoke |
| Portable Qt QSettings export | PARTIAL | `scripts/export-studio4-settings.py` (read only) | Execute with PySide6; Dockview layout not translatable byte-for-byte |
| Notebook v4 editable code/Markdown, per-cell execution | PARTIAL | `extra_files.rs`, `NotebookPanel.tsx`, `model/notebook.ts` | Tests of full UI round-trip and keyboard shortcuts |
| Notebook metadata retention and conflict detection | PARTIAL | `extra_files.rs` fixture `notebook_round_trip_conflict_and_metadata_preservation` | Real .ipynb fixtures across OS; foreign cells unsupported like Qt |
| Notebook Run all, stale outputs, append blank cell | PARTIAL | `NotebookPanel.tsx`; verified by code review | UI test for ordering, error termination and concurrent cell edit |
| Source lexical analysis, diagnostics markers | PARTIAL | `sourceMetrics.ts`, `sourceDiagnostics.ts` + Vitest | Compare markers and exact metrics with Qt reference corpus |
| Bytecode CFG and heuristic call graph | PARTIAL | `graphs.ts` + Vitest, `GraphPanel.tsx` / Cytoscape | No native AST; verify visual cases and branch semantics |
| Post-execution trace replay <=5000 | PARTIAL | Native cap, `TraceReplay.tsx` / `TraceReplay.test.ts` | Interactive Prev/Next, slider and virtualized events added; installed GUI smoke pending |
| Profiler and repeated benchmark chart | PARTIAL | `ProfilerPanel.tsx`, `benchmarkStats` Vitest, ECharts | Same-source/same-binary Qt comparisons, full OS process metrics |
| Rust process CPU/RSS graph | PARTIAL | `resources.rs`, `ResourcePanel.tsx`, sysinfo | Does not include WebView or native test/VM child processes |
| Git read-only status/commits/diff | PARTIAL | `git_view.rs`, `GitPanel.tsx` | Git navigation and detailed file diffs not at full Qt parity |
| Language source navigation and CMake rebuild | PARTIAL | `language.rs`, `LanguagePanel.tsx`; stale binary guard | Verify C++ edits / failed rebuild on actual checkout across OS |
| Command palette, persisted Dockview panels | PARTIAL | `App.tsx` | Keyboard, session, schema restoration and DPI smoke |
| Genuine VM breakpoints, pause, stepping | BLOCKED | One-shot original runner exposes no live VM control | Requires separate future C++ debugger interface |
| Shared-state persistent notebook kernel | BLOCKED | Original runner starts new VM per call | Requires separate future C++ kernel |
| Structured native AST | BLOCKED | Runner only returns bytecode/report | Requires separate future C++ API |

## Verification matrix

- [ ] Latest HEAD: Studio 5 Rust tests, Vitest, TypeScript, Tauri package green on **Windows/Linux/macOS**
- [ ] Latest HEAD: existing Qt CI green on **Windows/Linux/macOS**
- [x] Protected C++ and original Qt/CMake files unchanged in branch comparison (recheck after every commit)
- [ ] Actual installed GUI exercises run/compile/profile/trace with original native sidecar
- [ ] Native test suite all 225: quick/full, cancellation, timeout, kill, per-test errors
- [ ] Nonempty real Qt database: source checksum, original counts and baseline equal after migration
- [ ] .pm/.ipynb round-trip and conflict handling on all supported OS
- [ ] Differential check `scripts/check-qt-native-parity.py` passes on 3 OS; real UI-vs-Qt comparison still required
- [ ] GUI performance evidence on real hardware

**Stage 2 is not complete while these acceptance gates are unmet.**
Do not switch the default launcher, remove Qt, or merge this Draft PR until
functional parity and cross-platform results are independently established.

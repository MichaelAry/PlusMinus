# Studio 5 — independent Stage 1/2 feature parity ledger

**Baseline:** original Qt/C++ revision `41360ed7f470dd76da264b24ff74171ef55da5c2`.
**Migration base:** `master` at `5ebab2836f6ba914373abfa23c8d17c007d14af8`.
**Merged fixes:** PR #22 into `master` at `a33ad24582f11594ada2118e0a5764d33d53f44d`. Stage 3 PR #23 targets Windows x64 and Linux x64 only; evidence below remains conservative.
**Status definitions:** DONE = independently confirmed by meaningful tests or immutable Git comparison; PARTIAL = implemented but incomplete or GUI confirmation unavailable; MISSING = not implemented; BLOCKED = impossible under the unchanged runner contract. A successful compile alone never proves desktop feature parity.

## Stage 1 — Foundation

| Function | Status | Code/evidence | Missing proof or correction |
|---|---|---|---|
| Unchanged C++20 interpreter, portable tests and CMake | DONE | Git compare against master; protected paths untouched | Keep immutable until cutover |
| Qt Studio 4 and launch.py available | DONE | Original files and existing Desktop Qt workflow unchanged | Never default to Tauri in Stage 2 |
| Tauri 2 / Rust Tokio / React / TypeScript / Vite | PARTIAL | `apps/studio/package.json`, `src-tauri/Cargo.toml`; PR #21 passed 3-OS build | PR #22 check and real desktop interactions |
| Monaco editor and Dockview panels | PARTIAL | `src/App.tsx`, `src/features/editor/EditorPane.tsx` | Split-view, layout/focus E2E smoke |
| Workspace tree and .pm read/create/save | PARTIAL | `src-tauri/src/workspace.rs` round-trip tests | Installed GUI interaction and symlink-race tests |
| Run/Compile/Profile/Trace via unchanged runner | PARTIAL | `src-tauri/src/process.rs`; staged C++ tests and `smoke-native.mjs` | Execute from installed GUI on each OS |
| UTF-8 stdin / mandatory EOF | PARTIAL | `process.rs`: async write_all and drop(stdin), actual C++ smoke | Installed sidecar invocation |
| Single JSON object, exact exit codes, nested protocol validation | PARTIAL | `process.rs` decode_report tests incl. invalid diagnostics/trace/metrics | PR #22 CI on actual binaries |
| Empty stdout, result \"0\", compile/runtime errors | PARTIAL | `present.ts`, `process.rs` tests, original native smoke | GUI display of all cases |
| stderr, output bounds and history errors | PARTIAL | `process.rs`, `lib.rs`, `OutputPane.tsx` | IPC + UI negative-path testing |
| Timeouts/cancellation and descendants | PARTIAL | Stage 3 `process_tree.rs`: Unix process group kill, Windows best-effort taskkill /T /F | Windows Job Object/orphan regression NOT VERIFIED |
| Secure workspace-relative paths and optimistic saves | PARTIAL | `workspace.rs` and `extra_files.rs` tests | TOCTOU/symlink attacks and concurrent writers |
| Windows/Linux/macOS x64 packaging of both sidecars | PARTIAL | `studio5.yml`, `stage-native.mjs`; inherited CI passed | PR #22 CI, installed launch and IPC, ARM64 |
| Typed TS/Rust invoke declarations | PARTIAL | `src/api/contracts.ts`, `src-tauri/src/{lib,process}.rs` | Generated contract parity/round-trip E2E |
| Separate CI and regression suite | PARTIAL | `.github/workflows/studio5.yml` includes C++/TS/Rust/Clippy | Latest required checks and GUI E2E |

## Stage 2 — Qt functional parity

| Qt feature or capability | Status | Code/evidence | Missing proof or correction |
|---|---|---|---|
| Multi-document tabs, dirty/conflict handling | PARTIAL | `model/studio.ts`, `EditorPane.tsx`, Zustand tests | 20 documents, close/reopen, save-as |
| Independent split editor | PARTIAL | Dockview split and local pane selection in `App.tsx`, `EditorPane.tsx` | Independent focus/save/restore UI acceptance |
| Monaco model lifetime and 2 MiB documents | PARTIAL | `EditorPane.tsx` model Map/dispose | Long-session memory/leak tests |
| Find, comment toggling, lexical completion | PARTIAL | `features/editor/monaco.ts`, `model/completion.ts` + Vitest | Actual Monaco keyboard and accessibility |
| Native compiler diagnostics markers | PARTIAL | `EditorPane.tsx`, `model/studio.ts` source-snapshot tracking | GUI test and position accuracy under split views |
| 225 native test discovery | DONE | `scripts/smoke-native.mjs`, `verify-native-isolation.mjs` and inherited all-OS PR #21 CI | Reconfirm latest CI |
| Individual test process per C++ test | PARTIAL | `native_tests.rs`, `verify-native-isolation.mjs` all 225 | GUI-driven Test Lab and failure injection |
| Test Lab quick/full/selected/filters/inspector | PARTIAL | `features/parity/TestLab.tsx`, TanStack Virtual | GUI end-to-end including source navigation |
| Global bounded concurrency and TaskRegistry | PARTIAL | `native_tests.rs` shared semaphore, `tasks.rs` tests | Stress/race tests and process-tree cleanup |
| Cancellation/timeout/progress Channels | PARTIAL | `native_tests.rs`, `api/parity.ts` | Complete/stop under crash, stale streams and remount |
| User source tests and import/export | PARTIAL | `SourceTestsPanel.tsx`, `user_tests.rs`; duplicate-name fix | GUI import/suite/stop, legacy fixtures |
| Benchmark and native opcode profile | PARTIAL | `ProfilerPanel.tsx`, ECharts, native report | Repeatable Qt comparison on same hardware |
| OS CPU/RSS for native VM child | MISSING | Rust `resources.rs` intentionally samples only backend PID | Add verified cross-OS child telemetry or explicitly defer |
| Rust resource graphs | PARTIAL | `ResourcePanel.tsx`, `resources.rs` | Total memory and long-running UI tests |
| Post-execution trace replay capped at 5000 | PARTIAL | `TraceReplay.tsx` + unit tests, TanStack Virtual | UI performance at 5000 events |
| SQLite Studio 4 -> studio-v5.db | PARTIAL | `history.rs`: read-only backup, versioning, atomic no-clobber staging, integrity tests | Full real-like migrations/rollback/security fixtures |
| History, export, baseline comparisons | PARTIAL | `history.rs`, `HistoryPanel.tsx` | Large history, reports, cross-OS metadata, GUI |
| Portable QSettings export | PARTIAL | `scripts/export-studio4-settings.py` | Complete import/session restoration in new GUI |
| Complete Qt workspace session restoration | PARTIAL | `model/session.ts` reopens bounded clean tab paths and active document when user reselects workspace | No automatic last-workspace selection or unsaved source recovery on app restart |
| Notebook v4 open/create/edit/save/Run all | PARTIAL | `extra_files.rs`, `NotebookPanel.tsx`, `notebook.test.ts` | Qt fixture and installed GUI output/save/reopen |
| Legacy `execute_result` and numeric-zero notebook return | PARTIAL | `model/notebook.ts`, `NotebookPanel.tsx` + Vitest | Real file-backed UI acceptance |
| CFG and heuristic call graph | PARTIAL | `model/graphs.ts`, `GraphPanel.tsx`, Cytoscape | Large/complex programs; native AST unavailable |
| Git status/diff/history view | PARTIAL | `git_view.rs`, `GitPanel.tsx` | Rich file navigation and GUI tests |
| Command palette | PARTIAL | `App.tsx` | Qt command coverage and keyboard interaction |
| Language Internals / rebuild C++ | PARTIAL | `language.rs`, `LanguagePanel.tsx`; build fingerprint manifests | External edits, rebuild errors, installed sidecar switching |
| Stale-response prevention and safe workspace switching | PARTIAL | `App.tsx`, `NotebookPanel.tsx`, source-snapshot identity | Race-focused GUI stress |
| Cross-platform installed GUI interactions | MISSING | Only Linux installed-layout startup smoke without interactions | Windows/macOS/Linux GUI workflow test suite |
| Live debugger / breakpoints / VM stepping | BLOCKED | Unmodified C++ runner is one-shot JSON, no DAP/debug control API | Requires separately authorized native engine changes |
| Shared persistent Jupyter kernel state | BLOCKED | Each notebook cell spawns a fresh C++ VM | Requires a new runner session API |
| Structured native compiler AST | BLOCKED | Only bytecode listing and source heuristics exposed | Requires additional C++ compiler API |

## Validation and merge gate

**Prior validated ancestry:** PR #21 `cc2e084` CI passed C++ checks, 225 separately launched test cases, frontend/Rust tests and x64 packages. New code in PR #22 must be validated again; canceled and pending jobs count as NOT RUN, not PASS. See the current `studio5.yml` workflow results on PR #22.

Commands in repository root and app directories:

```sh
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --config Release --parallel 2
ctest --test-dir build/studio5 -C Release --output-on-failure
node scripts/verify-native-isolation.mjs --build-dir build/studio5
node scripts/smoke-native.mjs --build-dir build/studio5
python scripts/check-qt-native-parity.py --build-dir build/studio5
(cd apps/studio && npm install && npm run test && npm run typecheck && npm run lint:types && npm run build:ui)
(cd apps/studio/src-tauri && cargo check --all-targets && cargo test && cargo clippy --all-targets)
```

Stage 3 remains **NOT READY** until critical functional gaps and actual installed-GUI checks pass. Never infer RUNNER/VM feature availability from a button, a description, or a successful package build.

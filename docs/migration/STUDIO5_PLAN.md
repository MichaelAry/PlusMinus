# PlusMinus Studio 5 — three-stage migration plan

**Audited baseline:** master 41360ed7f470dd76da264b24ff74171ef55da5c2,
21 November 2026. Stage 1 branch: feature/studio5-foundation.

## Immutable boundaries
Do not alter src/, include/, ide/runner.cpp, tests/cpp/, tests/portable/,
root CMakeLists.txt or the behavior of the PlusMinus language. Qt Studio 4,
launch.py, the original release workflow and user files remain intact
through Stages 1 and 2. Every stage is an independently reviewed PR.

## Baseline audit
- Qt GUI: ide/studio_qt.py (~2020 lines), ide/research_shell.py,
  ide/workspace.py and ide/documents.py.
- C++: plusminus_core (C++20), one-shot ide/runner.cpp binary
  plusminus_runner; argv run|compile|profile|trace, UTF-8 stdin until EOF,
  one JSON response, exit 0 for success and 1 for PlusMinus errors.
- Native tests: 225 discoverable portable tests from original CMake;
  plusminus_native_tests --list (JSONL), --run <ID> (JSONL), --suite quick/full.
- Python helpers: ide/engine.py samples elapsed/CPU/RSS;
  ide/native_tests.py manages isolated tests and SQLite baselines;
  ide/analytics.py manages runs and source analysis.
- Data: ~/.plusminus/studio.db includes runs, native_sessions,
  native_results and native_baseline. Never overwrite this file.
- Notebooks: nbformat v4 code/Markdown cells with isolated execution,
  NOT persistent kernel. Qt stage 4 improvements include notebook shortcuts,
  honest metrics, final empty cell and stale-output warning.
- Language Lab: ide/internals.py and language_window.py navigate source,
  edit C++ and rebuild invalidated binaries.
- Windows Qt GUI startup issues are now documented, diagnosed and mitigated
  by safe-mode fallback. No claim that switching WebView cures all OS issues.

## Target separation
WebView (React, Monaco, Dockview) -> Tauri typed invoke
-> Rust Tokio process / project services
-> *unchanged* C++ child processes (runner and native tests).

Frontend never controls generic shell commands or arbitrary executable paths.
Source results, errors and metrics remain native data. For Stage 1 execution,
the C++ protocol is one-shot JSON, **not JSON-RPC** or streamed debugging.

## Stage 1 — Foundation (this PR)
Deliver a parallel Tauri 2 app, Vite/React/TypeScript frontend, Monaco
editor with basic PlusMinus tokens, Dockview panels, a project tree,
.pm open/create/save, Run/Compile/Profile/Trace, stdout/diagnostics/bytecode,
native metrics and post-execution trace. Rust validates workspace paths,
protects against symlink traversal, handles UTF-8/EOF, max buffers,
timeouts/cancel and exit status. Stage both C++ executables into Tauri
externalBin with target triple. Add an independent multi-OS workflow,
adapter/format tests and baseline docs. Keep Qt untouched.

**Stage 1 exit gate:** real runner launches from installed Tauri package,
Run/Compile/Profile/Trace semantics match Qt, stdout empty and numeric-zero
results are visible, a compilation failure is a result rather than transport
failure, no fake CPU/RSS numbers, C++ sources unchanged, Qt CI remains green.
Do not call this gate passed until observed platform builds are green.

## Stage 2 — Functional parity (next PR)
1. Replace remaining Qt panels: Test Lab, Native C++ Test Analysis,
   code inspector, benchmark/resource/profile charts, source control,
   navigation, history, notebook and Language Lab.
2. Discover 225 native tests. Rust Test Orchestrator with isolated test
   child processes, bounded concurrency (start with two), cancellation,
   timeout, progress through Tauri Channel, error/crash differentiation.
3. Copy user's ~/.plusminus/studio.db with SQLite Backup API, migrate into
   studio-v5.db with integrity checks, preserve original test IDs, session
   times, Git SHA, dirty status, baselines and user run history. Keep
   original read-only for Studio 5, and plan later reconciliation.
4. Notebook v4 round-trip (Markdown/code/output), isolated cells only,
   Shift+Enter/Ctrl+Enter, stop, final blank cell and stale output warnings.
5. Language C++ navigation and reliable CMake rebuild; mark native binaries
   invalid after source edits and do not run obsolete executables.
6. Full Monaco split views sharing models, diagnostics, command palette,
   workspace layout/session persistence, Git read-only source view.
7. Bytecode CFG and heuristic call graph, opcode hit profiles, measured
   benchmarks, replay max 5000 events; validate existing semantics.
8. Update parity matrix with file/commit/tests evidence. Qt remains available.

**Stage 2 exit gate:** every existing Qt workflow usable without Python
GUI; data restored, comprehensive tests and identical native behavior.

## Stage 3 — Production cutover (third PR)
- Independent code-level verification of Stage 2; no unsupported promises.
- Profile cold/warm startup, total idle RAM, input latency, 20 open files,
  225 native tests, 5000 trace events, large histories and reflow.
- Optimize Monaco model lifetimes, React renders, Dockview resize, tables
  virtualization, chart lazy loading, SQLite indexing and async task queues.
- Harden process groups/job objects, timeout/cancel cleanup, crashes,
  bounded native output, stale results, observability and CSP.
- Validate Windows WebView2, Linux WebKitGTK on Wayland/X11, macOS WKWebView
  on Intel/ARM64, DPI, fonts and installed sidecars. Cache Rust/CMake/npm.
- Only when verified, switch Start-PlusMinus scripts and packaging to Tauri,
  remove mandatory Qt/Python GUI runtime and update docs; keep rollback via
  tag/release and old SQLite original.

**Stage 3 exit gate:** real cross-OS installed builds, proven feature parity,
no critical performance regressions, data safety and rollback documented.

## Deliberate non-goals (require future C++ enhancement)
Live VM pause/breakpoints/step, real-time trace stream, structured compiler
AST and a persistent shared-state notebook VM kernel. Rust cannot implement
these reliably by changing only the desktop interface.

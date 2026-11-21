# Studio 5 IPC contract v1 — 2026-11-21

## Exact C++ one-shot protocol (unchanged)
Spawn executable: plusminus_runner run|compile|profile|trace
Write UTF-8 source to stdin, then CLOSE stdin to produce EOF.
Read one complete JSON object from stdout (not JSON Lines and not JSON-RPC).
C++ exits 0 and ok=true on success, exits 1 and ok=false on semantic
compile/runtime errors. A normal PlusMinus compile error must not be
converted into an IPC exception. A crash, invalid JSON, exit/ok mismatch,
output above limit, spawn error, timeout or cancellation is a transport error.

C++ JSON fields: ok:boolean, output:string, result:string,
variables:string, bytecode:string, error:string,
diagnostics:array, trace:array, trace_truncated:boolean, metrics:object.
Native metrics include compile_ms, execute_ms, program_instructions,
executed_instructions and opcode_hits. Ordinary run may report zero profiled
instructions; do not misrepresent it as measured execution count.
CPU/RSS and thread counts are currently NOT measured by the new backend.
A numeric zero result is the string "0" and must be shown.
Empty stdout must be explicitly displayed as empty, not mistaken for zero.

## Frontend -> Rust commands
engine_status() -> string | error
native_test_status() -> string | error
run_source({ request:{job_id,source,mode,timeout_ms} })
  -> {job_id,report,exit_code,wall_ms} | transport error
cancel_run({jobId}) -> boolean
choose_workspace() -> absolute user-selected folder display name
list_workspace() -> [{path,name,directory,depth}]
open_source({path}) -> {path,source,digest}
create_source({path}) -> {path,source,digest}
save_source({path,source,expected}) -> {path,source,digest}

Top-level invoke args use camelCase. The nested request JSON uses
snake_case. TS definitions are in src/api/contracts.ts and Rust definitions
are in src-tauri/src/{process,workspace}.rs.

## Trust boundaries
- JS has NO shell plugin/fs plugin capability. Rust owns native execution.
- Executable selection is a fixed allowlist, resolved from trusted
  installed sidecar or development CMake paths; no user-supplied binary.
- Workspace root is selected through native Rust dialog and canonicalized.
- File paths are relative to workspace and limited to .pm in Stage 1.
- Parent and actual paths are canonicalized to reject symlink escapes.
- Files <= 2 MiB, runner source <= 1 MiB, stdout <= 8 MiB,
  stderr <= 256 KiB; timeout 100..300000 ms.
- Jobs are keyed by random job_id; no duplicate running job IDs.
  UI ignores older completed results that do not match the active job.
- Cancellation kills spawned child best-effort; not a complete process
  tree sandbox. Native process is untrusted relative to user code.

## Stage 2 protocol
Test Orchestrator will add typed channels for test progress and bounded
concurrency; SQLite/read-only history; source rebuild operations; notebook
file round-trip. This is a Rust/application-level extension, not a claim
that the current C++ binary can accept JSON-RPC or live debug commands.

## Stage 2 additions (Rust/Tauri, not new C++ commands)

- list_native_tests / start_native_suite (jobId, testIds, label, onEvent Channel): independent native C++ test worker processes, bounded concurrency two, progress and cancel_run using the common active-jobs registry.
- history_overview / recent_runs / native_sessions / session_results / set_native_baseline / compare_native_sessions: read/write studio-v5.db. Original studio.db is opened read-only solely for SQLite Backup API migration.
- open_workspace_document / save_workspace_document / create_notebook: validated UTF-8 notebook v4 or limited checked-out C++ source. Outside user-selected workspace and symlink traversal rejected.
- git_summary: read-only fixed Git commands; language_targets / rebuild_native / native_source_stale: fixed source anchors and explicit CMake rebuilding.
- list_user_tests / save_user_tests / import_user_tests / export_user_tests: validated user test cases, optimistic digest, original user_tests.json left unchanged; copied into user_tests-v5.json.
- resource_snapshot: observed host Rust process RSS/CPU only. The WebView and C++ child-process metrics are not included in this sample.

No public shell command is granted to JavaScript, no native VM live stepping, no persistent cross-cell kernel and no genuine structured AST output.

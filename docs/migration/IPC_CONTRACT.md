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

## Stage 2 TaskRegistry contract

- \`task_snapshot({jobId})\` -> nullable
  \`{job_id,kind,status,done,total,passed,failed,session_id,error,created_at_ms}\`.
- \`list_tasks()\` -> snapshots sorted newest first. Task statuses:
  \`running\`, \`cancel_requested\`, \`completed\`, \`canceled\`, \`error\`.
- \`cancel_run({jobId})\` requests cancellation for source executions and
  independent native test suites. Cancellation is best-effort process kill;
  structured "canceled" status is not a native C++ response.
- Registry snapshots survive a Dockview panel unmount and can be reloaded by
  another pane in the same process. Completed test results are persisted in
  \`studio-v5.db\`; the active TaskRegistry itself does NOT survive app restart.
- Native test progress is delivered through a Tauri Channel per completed
  test, never per C++ VM instruction. A detached UI can poll snapshots.
- Source fingerprint of new native sessions reproduces Studio 4's per-parent
  ordered path+byte SHA256 on the host OS; legacy metadata is copied unchanged.

Source/runner protocols remain distinct: \`plusminus_runner\` consumes raw
UTF-8 stdin until EOF, no JSON-RPC; \`plusminus_native_tests\` consumes argv
\`--list\` or \`--run ID\` and writes JSON Lines.

## Complete history export

`export_history({format: "csv" | "json"})` presents a native save dialog. The destination must not already exist. The streaming exporter reads only `studio-v5.db` and leaves `studio.db` untouched; CSV output escapes quotes and guards spreadsheet formula interpretation. There is no 1000-record UI limit on exported data.

## Pre-cutover C++ build and worker contract

Native sidecars are staged with a source-fingerprint.json manifest (SHA256 of source/header/test/compiler build inputs). If a selected PlusMinus checkout differs from the embedded fingerprint, native execution and test discovery are blocked until the checkout is rebuilt. Sources are fingerprinted before and after CMake rebuild; a concurrent edit invalidates the result. The historical Qt session source_hash remains separate. All concurrently started native suites share a global two-permit Tokio semaphore. Each process streams bounded stdout/stderr before exit; cancellation is best-effort child termination, not a full process-tree sandbox. The C++ one-shot runner accepts exit 0/ok=true or exit 1/ok=false only, never exit 2 as a valid language diagnostic.


## PR #22 response extension and strict validation

`run_source` returns `{job_id,report,exit_code,wall_ms,stderr,history_error}`.
`report` is the original unmodified C++ JSON object; `stderr` is a bounded
UTF-8-lossy decoded string from the child stderr pipe, not part of that JSON.
`history_error` is a nullable string: `null` means history was persisted;
a string means execution finished but saving into `studio-v5.db` failed.
The frontend must show this warning without turning a successful VM execution
into a native compile/runtime error. Malformed diagnostic fields, trace entries,
trace_truncated, missing/null-incompatible nested metrics, excess trace length,
and contradictory exit codes are rejected as protocol errors. Valid metric `0`
and explicitly missing `null` values are preserved.

The C++ runner still takes one argv mode and UTF-8 stdin ending with EOF;
no JSON-RPC, debugger or persistent notebook kernel is introduced.

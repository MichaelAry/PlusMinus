# Performance baseline — NOT MEASURED

Source baseline: master 41360ed7f470dd76da264b24ff74171ef55da5c2.
The authoring environment had no Rust toolchain and could not resolve npm
dependencies, so no desktop benchmark numbers can be claimed from it.

| Metric | Qt Studio 4 | Tauri Stage 1 | Acceptance guidance |
|---|---|---|---|
| Cold/warm desktop start | NOT MEASURED | NOT MEASURED | Compare on same hardware |
| Total idle GUI+WebView RSS | NOT MEASURED | NOT MEASURED | Avoid unmanaged growth |
| Editor key to paint p95 | NOT MEASURED | NOT MEASURED | Target <=50ms |
| 20 opened documents | NOT MEASURED | NOT MEASURED | No visible freeze |
| C++ execution wall time | NOT MEASURED | NOT MEASURED | Compare identical binary |
| 225 native tests | Qt available | Stage 2 | Functional parity |
| Trace replay 5000 events | Qt available | NOT MEASURED | Interactive scrolling |
| Process CPU / peak RSS | Sampled by old Python | NOT MEASURED | Stage 2 |

Measurement protocol for Stage 3:
1. Record OS, GPU/WebView, CPU, RAM, scaling, compiler, Git SHA and
   C++ binary checksum; compare identical workloads and native binaries.
2. Report median/p95/worst of at least 10 cold and 20 warm startups.
3. Include all GUI/WebView/Rust/C++ processes in total memory.
4. Measure 1000-line/20000-line documents, 20 tabs, 225 tests, 5000
   trace events, source search, dock resize and UI startup.
5. Run installed Tauri packages as well as development builds and test
   original Qt GUI with real windowing, not solely offscreen CI.
6. Verify Windows x64, Linux X11/Wayland, macOS Intel and ARM64.
7. Archive raw measurements and scripts; never infer measured success
   from presence of source code or CI configuration.

Core language performance should not change when identical native binaries
are used; wrapper start/IPC/telemetry overhead remains to be measured.

## Stage 2 instrumentation availability

The Resources panel can sample Tauri/Rust backend CPU and RSS from the operating system; these are real process measurements but do not include the WebView renderer or native C++ worker. The Profiler panel graphs runner wall times and C++-reported opcode/VM metrics from actual executions. No cross-platform comparative measurements have been performed in this migration session and no baseline numbers are claimed.

## Observability and comparison limits (Stage 2)

The Rust resource sampler measures only its own PID's RSS/CPU; full desktop
RSS must also count WebView and C++ children. Benchmarks use the original
runner's wall/VM timing, with mean/median/interpolated p95, but no repeatable
hardware comparison against Studio 4 is present in this branch. No numerical
performance claim may be made until raw scripts and measurements are checked
on the same machine and identical C++ binary. CI packaging alone does not
measure UI responsiveness or installed launch success.

## Automated pre-cutover startup validation

PR #21 adds scripts/smoke-packaged-linux.sh to inspect the actual packaged .deb layout, execute embedded C++ runner and test sidecars and smoke the Linux GUI process under Xvfb for eight seconds. This is NOT an end-to-end GUI interaction or performance benchmark. A distinct script executes 225 C++ tests each in its own process in CI. Cross-OS installed performance measurements remain required in Stage 3.


## PR #22 additional regression methodology — not measured

Run `npm run lint:types && npm run test && npm run typecheck` under
`apps/studio/`; run `cargo check --all-targets && cargo test &&
cargo clippy --all-targets` under `apps/studio/src-tauri/` after staging
the unchanged C++ sidecars. On each platform, also execute
`node scripts/verify-native-isolation.mjs --build-dir build/studio5`
and the original CTest suite. These are *correctness* checks, not comparative
performance measurements. No new CPU/RSS, startup, editor-latency or Qt/Tauri
benchmark values have been obtained in this session.

## Stage 3 Qt-vs-Tauri matrix (Windows x64 / Linux x64)

**No desktop GUI comparison was performed in the agent environment.**
No made-up CPU, RAM or timing data are reported. CI package-build elapsed
time is not a user-facing desktop performance benchmark.

| Test | Qt Studio 4 | Tauri Studio 5 | Repeatable measurement protocol |
|---|---|---|---|
| Cold start | NOT MEASURED | NOT MEASURED | 10 fresh starts, window ready timestamp |
| Idle total RAM | NOT MEASURED | NOT MEASURED | 10 samples after 60s idle, all WebView/native children |
| Idle CPU | NOT MEASURED | NOT MEASURED | Process-tree CPU samples, median/p95 |
| Monaco typing latency | NOT MEASURED | NOT MEASURED | 200 key-to-paint events, 1k/20k-line corpus |
| Editor scrolling | NOT MEASURED | NOT MEASURED | 20k lines, frame rate and p95 frame time |
| Opening 20 files | NOT MEASURED | NOT MEASURED | Same 20 .pm files, 10 repeated runs |
| Complete native tests | NOT MEASURED | NOT MEASURED | All 225 individually, 3 sessions, compare IDs |
| Trace replay (5000) | NOT MEASURED | NOT MEASURED | Same native trace, 20 slider/scroll passes |
| Large history/table | NOT MEASURED | NOT MEASURED | 10k rows, 10 navigation passes |
| Open/close/resizing panels | NOT MEASURED | NOT MEASURED | 20 repeats, record frame times |
| Load and edit notebook | NOT MEASURED | NOT MEASURED | 500 code/Markdown cells, 5 repeats |
| Long-session memory leaks | NOT MEASURED | NOT MEASURED | 60-minute session, process RSS slope |

For EACH comparison capture: OS version/build, x64 CPU, logical cores, RAM,
GPU/WebView runtime, Node/npm, Rust/rustc, Qt/PySide6, compiler, release flags,
SHA of both installed packages, C++ executable SHA256, repetition count,
timestamped raw samples, median/p95 and dispersion. Use identical data,
hardware, native binary and user action scripts for both GUIs.

Commands for repeatable correctness inputs: `cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release`,
`cmake --build build/studio5 --config Release`,
`node scripts/verify-native-isolation.mjs --build-dir build/studio5`,
`node scripts/smoke-native.mjs --build-dir build/studio5`.
Install Qt and Studio 5 candidates on the same workstation, run the GUI actions
above, archive raw traces. Never label code-splitting or memoization as a
measured win without collected before/after traces.

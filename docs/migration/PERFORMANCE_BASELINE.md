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

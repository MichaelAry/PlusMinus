# Studio 5 Stage 2: evidence-based parity audit

Branch: feature/studio5-parity; PR #20 (Draft until independently accepted).
Stage 1 origin: c395dfe8. This is implementation-in-progress.

Status meanings: DONE = verified working with repeatable tests; PARTIAL =
new source exists, but parity is incomplete or runtime unverified;
BLOCKED = absent or requires prohibited changes to original C++ sources.

| Studio 4 feature | Status | Implementation / evidence | Remaining |
|---|---|---|---|
| Native 225 C++ test discovery | PARTIAL | native_tests.rs and TestLab.tsx | CI + real packaged GUI smoke |
| Per-test process isolation, cancellation and timeout | PARTIAL | native_tests.rs, bounded two-worker JoinSet | Verify crashes and no orphan processes |
| Test filters quick/full/selected/failed | PARTIAL | TestLab.tsx | Real UI comparisons |
| Native test source inspector | PARTIAL | TestLab.tsx and extra_files.rs | Test source anchor jump smoke |
| SQLite copy and migration | PARTIAL | history.rs, SQLite Backup API | Real Studio 4 nonempty database comparison |
| Runs, sessions, baselines, comparison | PARTIAL | history.rs, HistoryPanel.tsx | Older-session comparisons, metadata |
| Monaco multi-document split editor | PARTIAL | App.tsx, EditorPane.tsx | Split currently shares globally selected document |
| Portable Qt settings export | PARTIAL | scripts/export-studio4-settings.py | Test in actual Qt environment, no native dock layout bytes |
| Notebook v4 cells/Markdown/isolated execution | PARTIAL | NotebookPanel.tsx, model/notebook.ts | Real file round trips; large notebooks |
| Native opcode metrics and benchmark | PARTIAL | ProfilerPanel.tsx | CPU/RSS telemetry not integrated |
| Bytecode CFG and source heuristic call graph | PARTIAL | model/graphs.ts, GraphPanel.tsx | No structured native AST |
| Git read-only inspector | PARTIAL | git_view.rs and GitPanel.tsx | No source control write actions |
| Language C++ source navigation/rebuild | PARTIAL | language.rs and LanguagePanel.tsx | Full symbol map and build invalidation checks |
| Command palette + saved Dockview layout | PARTIAL | App.tsx | UI smoke and keyboard checks |
| User test JSON import/export | BLOCKED | Old Qt feature preserved | Not ported yet |
| Lexical live diagnostics and markers | BLOCKED | Old Qt feature preserved | Not ported yet |
| VM breakpoints/step | BLOCKED | One-shot original runner | Requires C++ API changes |
| Persistent notebook kernel | BLOCKED | One-shot original runner | Requires C++ API changes |

## Acceptance gates
- [ ] Latest HEAD: successful Studio 5 CI on Windows/Linux/macOS
- [ ] Latest HEAD: successful original Qt CI on Windows/Linux/macOS
- [ ] C++/root CMake/Qt source paths unchanged (git compare)
- [ ] Test cancellation, timeout, crash and data preservation tested
- [ ] Nonempty Studio 4 database migration checked against original counts
- [ ] Notebook and .pm round trips verified without loss
- [ ] Full feature parity matrix has file, test and commit evidence
- [ ] Installed packages launched with original sidecar executable

Do not merge before all mandatory acceptance gates have evidence.

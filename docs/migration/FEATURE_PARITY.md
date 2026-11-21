# Studio 5 feature parity ledger

Baseline: master 41360ed7f470dd76da264b24ff74171ef55da5c2.
Statuses: CODE = implemented in branch, not runtime validated; PENDING =
not yet ported; UNSUPPORTED = no existing native API.

| Qt Studio 4 feature | Stage 1 state | Next stage |
|---|---|---|
| Real C++ source Run/Compile/Profile/Trace | CODE | 1 |
| Bytecode, diagnostics, output, zero return, empty stdout | CODE | 1 |
| Native metrics and recorded trace | CODE | 1 |
| Monaco editor, basic .pm tree/tabs/open/save | CODE | 1 |
| Workspace path and executable resolution | CODE | 1 |
| Timeout/cancel/error/exit handling | CODE | 1 |
| Tauri sidecar staging (both C++ binaries) | CODE | 1 |
| Qt launcher and Qt CI still intact | CODE | 1 |
| 225 native C++ test GUI and source inspector | PENDING | 2 |
| Test batches, baselines, regression history | PENDING | 2 |
| SQLite ~/.plusminus/studio.db migration | PENDING | 2 |
| Custom test case import/export | PENDING | 2 |
| Full split editor, find, completion, diagnostics markers | PENDING | 2 |
| Notebook v4 editor/isolated execution/saving | PENDING | 2 |
| Language C++ source inspector and rebuild | PENDING | 2 |
| Profiler visualization and CPU/RSS sampling | PENDING | 2 |
| Benchmarks, resources, history and reports | PENDING | 2 |
| Bytecode CFG and heuristic call graph | PENDING | 2 |
| Read-only Git service and saved session layouts | PENDING | 2 |
| Production installer and default launcher switch | PENDING | 3 |
| Live breakpoints, VM pause/step | UNSUPPORTED | C++ API |
| Cross-cell persistent notebook kernel | UNSUPPORTED | C++ API |
| Native structured compiler AST | UNSUPPORTED | C++ API |

"CODE" is not "DONE". A test, successful package and actual desktop
execution must substantiate DONE. Do not invent measurements or CI results.

## Stage 1 acceptance checks (leave unchecked until observed)
- [ ] Existing C++ CTest and original desktop.yml are green.
- [ ] Windows CI Rust unit + frontend tests + packaged installer.
- [ ] Linux CI Rust unit + frontend tests + packaged AppImage/deb.
- [ ] macOS CI Rust unit + frontend tests + packaged app.
- [ ] Installed app launches actual C++ runner and accepts EOF.
- [ ] Empty stdout and numeric 0 return remain visible.
- [ ] Compiler errors yield ok=false, not a transport exception.
- [ ] Unknown metrics are explicitly marked "not measured".
- [ ] Cancel and timeout stop the process (no orphaned process).
- [ ] Unmodified C++ sources and CMake verified with git diff.

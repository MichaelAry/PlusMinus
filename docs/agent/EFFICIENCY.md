# Context, token and execution efficiency

This file defines **project-specific** exceptions and efficient commands. General mandatory procedure lives in the global `project-memory` skill, not duplicated in every project.

## Read policy: smallest sufficient context

- On entry, use `project_memory.py brief --project . --area <area>` (or `--session <id>` when known); inspect `STATE.md` only if cross-session handoff matters.
- Read one active prompt and required exact code locations. Never load all of `docs/agent/`, old prompt records, the full Git log, or entire source trees by default.
- Prefer path discovery (`rg --files`, directory listing) then narrow grep (`rg -n`) and bounded file sections. Exclude generated and vendor paths. Use `git diff --name-only` or `git status --short` before expanding a change review.
- Reuse previously established facts within the same conversation. Re-read only on detected change, contradiction, or evidence of staleness.
- Do not manufacture token/latency savings claims; optimize actual reads and tool outputs.

## Execution and verification

- Complexity-based planning: trivial change → acceptance check without adding tests; medium change → bounded plan; architectural/cross-module change → decision analysis and risk review. **Every actionable task gets one task record, but the record's detail scales with the work.**
- Batch related searches; do not repeat expensive directory scans; use a cached `INVENTORY.md` until a material tree change.
- **Do not create or modify automated test code, fixtures, snapshots, mocks, coverage settings or test dependencies for new changes unless the user explicitly requests it.** Do not add a “write tests” plan step automatically. Running existing relevant tests, lint, type-checks, build or manual smoke checks is allowed without changing tests. Escalate the risk if verification is insufficient; offer optional test coverage rather than implementing it unasked.
- Avoid unnecessary dependency installs, broad dependency upgrades, autoformatting unrelated files, large refactors, and speculative changes.
- Record significant decisions, file paths, tests and outcomes; do not copy raw command logs into Markdown. Store only concise evidence and a link or exact command.

## Documentation budget (targets, not hard truncation)

- Root `AGENTS.md` managed block: about 1–2 KB; must not embed the manual.
- `STATE.md`: active owners + pointers; target under 4 KB for ordinary projects.
- `PROMPTS.md`: up to 20 active and 12 recently closed entries; source archive never deleted.
- Completed task label: **2–4 meaningful words + `done`**, while original requirements remain in the archived prompt file.
- Session notes: milestones and handoff only; no transcript duplication or per-command logging.
- Preserve precise details in owning files rather than injecting them into global instructions.

## Repository-specific confirmed shortcuts

- **Existing test commands (run-only by default):** _Unverified; add a confirmed command/path when known._
- **Fast build/lint:** _Unverified._
- **High-value source entrypoints:** _Unverified._
- **Project-specific large folders to avoid:** _Unverified._

Update this section only with verified observations. Do not treat placeholders as facts.

## v4 process shortcuts

Use `development_os.py route` when scope is nontrivial, `search` for metadata lookup, `checkpoint`/`resume` for handoff, and `verify-doc`/`stale` for exact source freshness. For overlapping work use `claim`/`conflicts`/`release`. Keep L0 instructions stable; read L1 working context, L2 exact module docs and L3 history only on demand. Do not run full doctor/reindex/scan or all checks for every tiny task. Do not mistake estimated budgets or local event counts for measured token savings.

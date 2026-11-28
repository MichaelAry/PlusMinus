# Development process

Project management, not coding style. User instructions define execution scope. A backlog, priority, approved roadmap or readiness is never standalone permission to execute. The agent may record relevant discoveries without implementing them.

## Lifecycle

- `proposed`: idea, observation or hypothesis; no implementation commitment.
- `planned`: accepted candidate, not yet ready; record scope and dependencies.
- `ready`: sufficiently specified, dependencies satisfied or explicitly waived; wait for an explicit execution request.
- `in_progress`: user authorized work, linked to one existing prompt record; do not start other items automatically.
- `blocked`: record the concrete obstacle and next action; do not guess or silently bypass it.
- `deferred` / `rejected`: record why; do not erase history.
- `done`: actual result/evidence, compact 2–4-word title, full detail and linked prompt retained. Risks can be closed on observed mitigation/acceptance without implementation.

## Triage (only on request or relevant discovery)

Search titles/IDs before adding. Classify `idea`, `task`, `debt`, `risk`; assign P0 (critical), P1 (high), P2 (normal), P3 (low); default P2 if unknown. Record source, benefit/problem, observable evidence or hypothesis, rough effort (S/M/L/unknown), dependencies and next action. Use estimates as estimates, not facts. Do not invent dates/owners or approve proposals on behalf of the user. Priorities are not execution authorization.

## Ownership

`ROADMAP.md` owns milestones and strategic direction, linking item IDs without repeating descriptions. `IDEAS.md`, `BACKLOG.md`, `TODO.md`, `TECH_DEBT.md`, `RISKS.md` are generated bounded views of `items/YYYY/MM/*.md`. `PROMPTS.md` indexes actual user assignments; `TASKS.md` indexes conversations; neither is a second backlog. `STATE.md` owns concise current handoff. `DECISIONS.md` owns lasting decisions. `CHANGELOG.md` records material verified changes. A single item may appear as a link in multiple views but its details live only in its item record.

## Work rhythm

Before a task: read STATE, active prompt and relevant pointers; establish acceptance criteria, identify dependencies and scope. If it corresponds to an item, link the prompt when starting implementation. During work: batch meaningful milestones, note blockers, capture relevant ideas/debt/risks separately without expanding scope. After work: close prompt with verified result or documented check limitation, then close linked item only if its own criteria are satisfied. If the task is planning-only, close the planning deliverable when complete without claiming the proposed implementation is done. Update durable docs only for actual changes. Do not create tests unless explicitly requested; run appropriate existing checks only.

## Token economy

Do not load all ideas, backlog, roadmap and archives for ordinary coding. Use `brief --area plan` only for planning; `process list --query ... --limit 10` for targeted discovery; read exact item/prompt only. Keep item titles short and bounded, avoid raw logs and duplicate specs, use links and IDs. No routine full audit, reprioritization, mass task generation, extra agents or scheduled work unless requested. If concurrent work, use one writer per item and coordinate Git/worktrees; local locks do not coordinate across machines/Windows vs WSL. Never commit or push solely to maintain this system.

## v4 process extensions

Use `development_os.py next` to review dependency-ready candidates (not authorization), `triage` for explicit estimates, and `extend` for optional product, research or knowledge documents. Record validated non-goals, rejected approaches, lessons and experiments only when they prevent repeated work. One owner per durable fact. Claims across local worktrees are advisory; coordinate with `claim`, `conflicts` and `release`. Existing task records and paths remain canonical. Use `checkpoint` for factual handoff; never equate a hook Stop event with completed implementation.

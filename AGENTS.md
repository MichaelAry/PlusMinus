# Сопровождение PlusMinusM

## Проект и источники

- [README](README.md) описывает сборку C++20 и запуск обеих редакций Studio. Компилятор находится в `src/compiler/`, виртуальная машина и Math — в `src/vm/`, публичный API — в `include/plusminus/`. Обе редакции используют нативный runner из `ide/runner.cpp`.
- Studio 4 (PySide6) остаётся запуском по умолчанию. Условия перехода на Studio 5 (Tauri, Rust, React и TypeScript) ведутся в [чек-листе приёмки](docs/migration/PRE_CUTOVER_VERIFICATION.md). Подтверждайте состояние функций по реализации и результатам проверок.
- Для изменений графики сначала проверьте [протокол рисования](docs/PLOT_PROTOCOL.md) и [формат Plot Editor](docs/PLOT_EDITOR_PLAN.md).

## Работа над задачами

- Перед существенной работой проверьте профиль Project Development OS командой `python3 ~/.agents/skills/project-memory/scripts/project_memory.py profile status --project .`. При `UNSET` уточните назначение, горизонт развития и критерии успеха, затем согласуйте профиль перед инициализацией. Трёхуровневое планирование требует отдельного согласия.
- Для каждого нового запроса уточняйте границы и критерии приёмки пропорционально сложности и риску. При изменении требований пересмотрите готовность задачи. Сначала читайте документацию и код затронутого компонента.
- При активной памяти ведите одну запись на содержательный запрос. Сохраняйте подтверждённые решения, обновляйте затронутые документы и закрывайте задачи с результатами проверок. Ссылайтесь на канонические документы и существующие задачи.
- Запись в плане или backlog сама по себе не даёт разрешения на реализацию. Архитектурные изменения, установка зависимостей, изменения тестов и публикация через Git требуют отдельного поручения.

## Проверки

- Для ядра используйте CMake и CTest по [инструкции сборки](README.md#build-and-test-the-interpreter). Проверки `core_smoke`, `drawer_smoke` и `native_quick` покрывают базовую работу ядра, математику и рисование, а также быстрый набор нативных тестов. Для Windows используйте CMake: старый `UnitTest1.vcxproj` не включает `src/vm/mathlib.cpp`.
- Для локальной диагностики запуска используйте preflight из [README](README.md#choose-a-desktop-launcher). Для проверки установленной Studio 5 используйте чек-лист приёмки и фиксируйте ОС и выполненные сценарии.
- Запускайте существующие проверки по области изменений. Указывайте ограничения проверки и сохраняйте пользовательские файлы и историю.

<!-- project-memory:begin -->
## Project memory protocol (managed block) — FULL
- Respect `.project-memory.json`; never change the profile silently. Use only relevant context and scale task effort independently.
- Before new work, classify goal/scope/acceptance, complexity/risk, context and verification. Ask proactively about material unknowns in batches, reuse confirmed answers, and resolve blocking ambiguity before implementation. Use `discovery.py` for substantial tasks; no unsolicited implementation.
- Use `docs/agent/INDEX.md` for the documentation map and `docs/agent/STATE.md` for short handoff. `INVENTORY.md` contains bounded machine-generated evidence, not full code understanding.
- For each new Codex conversation use the session ID supplied by the trusted lifecycle hook, else the launcher variable `PROJECT_MEMORY_SESSION_ID`, else create one session. Never adopt another agent's session. Use the hook turn key for new prompt idempotency; amend clarifications.
- For each NEW actionable user task in the conversation, create ONE prompt record under `docs/agent/prompts/YYYY/MM/`, linked from its owning session. Before coding record a concise faithful specification, scope, acceptance criteria and proportional plan. An amendment to an unfinished task updates that prompt, not a duplicate.
- Manage development through `docs/agent/PROCESS.md`: capture ideas/debt/risks as proposals, use `process list` for selective lookup, link explicitly requested implementation to a prompt, never execute backlog or TODO on your own.
- Do not add or modify automated tests, fixtures, snapshots, mocks, or test coverage for new changes unless the user explicitly requests test work. Existing tests and other lightweight checks may be run without creating test files; document results and residual risk.
- When a task is proven complete, update its prompt to `done`, supply concrete result + verification, and replace its index label with a concise **2–4 word** short title. Keep the full original specification and proof in the linked archived prompt Markdown.
- Classify work (question/research/plan/fix/feature/audit/release) and choose proportional depth XS–XL. Use `development_os.py route`, `search`, `claim`, `checkpoint`, `release`, `stale` as relevant. Read `STATE.md`, relevant sections of `INDEX.md` and active prompt(s) on entry. Consult `PROJECT.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, ADRs and old prompts only when needed; never bulk-read the archive by default.
- Maintain project documentation only when corresponding verified facts actually change. No fabricated facts/tests, secrets, raw transcripts, automatic commits/pushes/deploys, or changes beyond user permission. Do not overwrite other documentation or manual sections.
- Run `project-memory` script commands via global skill `~/.agents/skills/project-memory/SKILL.md`; if unavailable, follow this protocol manually within permissions.
- Optional planning is active: strategy → tactical initiatives → existing operational items. For planning tasks use `planning.py list/trace` and `docs/agent/planning/STRATEGY.md`, `TACTICAL.md`, `OPERATIONS.md` selectively. Link existing items; no duplicate tasks or implied execution authority.
<!-- project-memory:end -->

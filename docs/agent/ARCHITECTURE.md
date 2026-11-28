# Архитектура

- [Компилятор](../../src/compiler/) преобразует исходник в байткод. [VM](../../src/vm/) исполняет его, включая конкурентные программы, Math и вывод событий рисования. [Публичный API](../../include/plusminus/) доступен из статического ядра C++20.
- [Нативный runner](../../ide/runner.cpp) связывает ядро с настольными приложениями и отдаёт результаты в JSON. Протокол рисования описан в [PLOT_PROTOCOL](../PLOT_PROTOCOL.md).
- Studio 4 использует [Python и Qt/PySide6](../../ide/README.md). Studio 5 использует [React/TypeScript и Rust/Tauri](../../apps/studio/README.md). Контракт IPC описан в [документации миграции](../migration/IPC_CONTRACT.md).
- Studio 5 ведёт отдельную SQLite-базу. Приёмка миграции на непустых данных и отката описана в [чек-листе](../migration/PRE_CUTOVER_VERIFICATION.md). Дочерние процессы исполняются с правами пользователя.

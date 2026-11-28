# Сборка и проверки

- Используйте команды [CMake Release и CTest](../../README.md#build-and-test-the-interpreter) на актуальных исходниках. На Fedora 44 при первичном аудите прошли core_smoke, drawer_smoke и native_quick.
- Проверяйте зависимости запуска через `python3 launch.py --check` и `bash ./Start-PlusMinus-Studio5.sh --check`. Оба preflight прошли на Fedora 44. Полная проверка поставки описана в [чек-листе](../migration/PRE_CUTOVER_VERIFICATION.md).
- Правила уточнения задач, согласования изменений и запуска существующих тестов описаны в [AGENTS.md](../../AGENTS.md).

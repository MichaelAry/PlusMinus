# Многопоточная рисовалка: протокол данных

Документ описывает **готовый backend** для UI графики. Сам интерфейс
(панель, canvas, цвета, байткод-вьюер) делает отдельный разработчик; здесь
зафиксировано, что именно приходит из C++ runner'а и как это трактовать.

## Запуск примера

```bash
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --target plusminus_runner -j
./build/studio5/plusminus_runner run < examples/mandelbrot.pm
```

Runner — однократный процесс: исходник читается из stdin до EOF, в stdout
печатается **один** JSON-объект. Все поля ниже уже присутствуют в текущей
сборке.

## Поле `plot`

Добавлено в JSON-отчёт runner'а рядом с `output`, `bytecode`, `trace` и
`metrics`:

```json
"plot": {
  "events": [
    { "thread": 1, "kind": "point", "x": -2.2,  "y": 1 },
    { "thread": 1, "kind": "point", "x": -2.1825, "y": 1 },
    { "thread": 2, "kind": "dot",   "x": 0,     "y": 0 },
    { "thread": 2, "kind": "line",  "x": 0,     "y": 0, "x2": 1, "y2": 1 }
  ],
  "truncated": false,
  "threads": 33
}
```

| Поле | Смысл |
|---|---|
| `events` | Примитивы рисования в порядке фиксации. |
| `events[].thread` | Номер VM-потока, который вызвал `plot`/`point`/`line`. `0` — главный поток, рабочие потоки начинаются с `1`. |
| `events[].kind` | `point` — точка связной кривой потока; `dot` — отдельная точка; `line` — явный отрезок. |
| `events[].x`, `y` | Координаты (для `line` — начало отрезка). |
| `events[].x2`, `y2` | Конец отрезка; присутствуют только у `kind: "line"`. |
| `truncated` | `true`, если сработал лимит 50 000 событий. |
| `threads` | Сколько раз VM создала исполняемый поток, включая главный. То есть `32` рабочих + `1` главный = `33`. |

### Как рисовать

1. Сгруппировать `events` по `thread`.
2. Назначить каждому `thread` свой цвет (например,
   `palette[thread % palette.length]`).
3. Для каждого потока:
   - `point` — добавить точку в полилинию этого потока; соединять
     последовательные `point` одного потока;
   - `dot` — нарисовать отдельную точку, не соединять;
   - `line` — нарисовать отрезок `(x,y) — (x2,y2)`.
4. Подписать легенду «Thread N».

Порядок событий **внутри одного потока** соответствует порядку вызовов;
между потоками события перемешаны (это настоящая конкурентность, а не
имитация). Сортировать по `thread` для раскраски, но не менять порядок
внутри потока.

### Границы

- Лимит: `plusminus::PlotEventLimit == 50000` событий на запуск.
- При переполнении события отбрасываются, `truncated: true`.
- `clear()` очищает буфер целиком (событий `clear` в JSON нет).
- Координаты `NaN`/`Inf` заменяются на `0`, чтобы JSON оставался валидным.

## Байткод и трассировка по потокам

`report.bytecode` — текстовый листинг скомпилированной программы:

```
   0  FuncDef  mandel  cx  cy
   1  Jmp  -> 20
   ...
  37  Call  plot  argc=2
  38  Pop
```

Кнопка/вкладка «Байткод» в рисовалке может показывать это поле как есть.
Оно доступно и в режиме `compile`, и в `run`.

Для «какой поток что исполнял» используйте `report.trace` (только режим
`trace`; обычный `run` возвращает пустой массив):

```json
"trace": [
  { "ip": 37, "opcode": "Call", "thread": 5, "stack_depth": 2 },
  { "ip": 38, "opcode": "Pop",  "thread": 5, "stack_depth": 1 }
],
"trace_truncated": false
```

- `thread` совпадает с `thread` в `plot.events` — можно подсвечивать
  исполненные инструкции цветом потока.
- Трасса ограничена 5 000 событиями; `trace_truncated` сообщает об
  усечении.
- Чтобы получить и график, и трассу, запускайте runner в режиме `trace`:
  `plusminus_runner trace`. Поле `plot` заполняется во всех режимах
  исполнения (`run`, `profile`, `trace`).

## Встроенные функции рисования

| Функция | Действие |
|---|---|
| `plot(x, y)` | Точка связной кривой текущего потока. |
| `point(x, y)` | Отдельная точка. |
| `line(x1, y1, x2, y2)` | Отрезок. |
| `clear()` | Очистить накопленные события. |

Все возвращают `0`, поэтому их можно писать как обычные операторы.
Координаты должны быть вещественными числами; комплексные координаты
вызывают ошибку.

## Math-библиотека

Вся нетривиальная математика вынесена в
`include/plusminus/math.hpp` + `src/vm/mathlib.cpp`
(пространство имён `plusminus::math`). `builtins.cpp` делегирует туда
вызовы; executor использует ту же библиотеку для `+ - * / % ^`, сравнений
и истинности.

### Комплексные числа

```plusminus
c = complex(1, 2);      // 1 + 2i
z = complex(0, 0);
z = z * z + c;          // комплексная арифметика через обычные операторы
m = abs(z);             // модуль
r = re(z);
i = im(z);
```

Доступно: `complex(re, im)`, `re`, `im`, `conj`, `arg`, `abs`/`cabs`,
`cadd`, `csub`, `cmul`, `cdiv`. Печать: `print(complex(1, 2))` → `1+2i`.
Сравнения порядка (`<`, `>`) для комплексных чисел запрещены; сравнивайте
`abs(z)`.

### Скалярные функции

`sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sqrt`, `cbrt`,
`exp`, `log`, `log10`, `floor`, `ceil`, `round`, `abs`, `sign`, `min`,
`max`, `hypot`, `clamp`, `lerp`, `deg`, `rad`, `pow`, `fact`, `multifact`,
`pi()`, `e()`.

`sqrt(-x)` и `log(-x)` возвращают комплексный результат, а не `NaN`.
`sin`/`cos`/`tan`/`exp`/`log`/`sqrt`/`pow` принимают и комплексные
аргументы. Массивы по-прежнему хранят только вещественные числа.

## Пример Mandelbrot

`examples/mandelbrot.pm` — дефолтный пример:

- 32 рабочих потока (`go row(r)`), каждый рисует свою горизонтальную
  полосу;
- 160 точек на поток, 5 120 событий;
- каждая кривая помечена своим `thread`, поэтому UI красит её в свой цвет;
- `report.bytecode` содержит 89 инструкций;
- при `trace` в `trace.events[].thread` видно, какой поток исполнял
  какие инструкции.

Проверка из командной строки:

```bash
./build/studio5/plusminus_runner run < examples/mandelbrot.pm | python3 -c '
import json,sys
r=json.load(sys.stdin)
print(r["ok"], len(r["plot"]["events"]), r["plot"]["threads"])'
```

Ожидаемо: `True 5120 33`.

## Тесты

```bash
cmake --build build/studio5 --target plusminus_drawer_smoke
./build/studio5/plusminus_drawer_smoke
```

`plusminus_drawer_smoke` проверяет комплексную арифметику, печать,
примитивы рисования и то, что три рабочих потока дают три разных
`thread`.

## Сборка и стейджинг для Studio 5

```bash
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --target plusminus_runner plusminus_native_tests -j
node scripts/stage-native.mjs --build-dir build/studio5 --target x86_64-unknown-linux-gnu
```

`stage-native.mjs` копирует sidecar'ы в `apps/studio/src-tauri/binaries/`
и обновляет `source-fingerprint.json`. Старые sidecar'ы поля `plot` не
содержат; UI должен трактовать отсутствие `plot` как пустой набор событий.

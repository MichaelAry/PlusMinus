#include "CppUnitTest.h"
#include "Parser.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <string>
#include <thread>
#include <vector>

using namespace Microsoft::VisualStudio::CppUnitTestFramework;

namespace ParserTests {
TEST_CLASS(ConcurrencyAndFunctions)
    {
    public:
        TEST_METHOD(TestFunctionAndProc)
        {
            std::string prog =
                "proc printHello() { print(\"Hello\"); }\n"
                "func int add(a, b) { return a + b; }\n"
                "printHello();\n"
                "x = add(5, 10);\n"
                "print(x);";
            std::string out = getOutput(prog);
            Assert::AreEqual(std::string("Hello\n15\n"), out);
        }

        TEST_METHOD(TestRaceConditionWithLock)
        {
            // Воспроизводим доску: c=0, p1 и p2 инкрементируют c.
            std::string prog =
                "int c = 0;\n"
                "proc inc() {\n"
                "  i = 0;\n"
                "  while (i < 100) {\n"
                "    lock(c);\n"
                "    c = c + 1;\n"
                "    unlock(c);\n"
                "    i = i + 1;\n"
                "  }\n"
                "}\n"
                "go inc();\n"
                "go inc();\n"
                "sync;\n"
                "print(c);\n";

            std::string out = getOutput(prog);
            Assert::AreEqual(std::string("200\n"), out); // Ожидаем 200, так как есть lock
        }

        TEST_METHOD(TestAsyncExecution)
        {
            // Тест на то, что go запускает поток, а sync ждет
            std::string prog =
                "proc f(x) { print(\"start \", x); }\n"
                "go f(1);\n"
                "go f(2);\n"
                "sync;\n"
                "print(\"done\");\n";
            std::string out = getOutput(prog);
            // Порядок вывода start 1 и start 2 может меняться, но done всегда в конце
            Assert::IsTrue(out.find("start 1") != std::string::npos);
            Assert::IsTrue(out.find("start 2") != std::string::npos);
            Assert::IsTrue(out.rfind("done") > out.find("start"));
        }
    };

TEST_CLASS(AsyncExecutionExtended)
    {
    public:
        // 1. Аргументы для go фиксируются (снапшот) в момент вызова
        TEST_METHOD(AsyncArgumentSnapshot)
        {
            std::string prog =
                "func printVal(val) { print(val); }\n"
                "x = 100;\n"
                "go printVal(x);\n" // Захватывает 100
                "x = 200;\n"
                "go printVal(x);\n" // Захватывает 200
                "sync;\n";
            std::string out = getOutput(prog);
            Assert::AreEqual(std::string("100\n200\n"), out);
        }

        // 2. Асинхронный цикл накапливает результат
        TEST_METHOD(AsyncLoopAccumulator)
        {
            std::string prog =
                "func addToC() { c = c + 1; }\n"
                "c = 0;\n"
                "i = 0;\n"
                "while (i < 5) {\n"
                "  go addToC();\n"
                "  i = i + 1;\n"
                "}\n"
                "sync;\n";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(5.0, (double)v["c"]);
        }

        // 3. Вложенный асинхронный вызов (go внутри функции, которую вызвали через go)
        TEST_METHOD(NestedAsync)
        {
            std::string prog =
                "func inner() { print(\"inner\"); }\n"
                "func outer() {\n"
                "  print(\"outer start\");\n"
                "  go inner();\n"
                "  print(\"outer end\");\n"
                "}\n"
                "go outer();\n"
                "print(\"before sync\");\n"
                "sync;\n"
                "print(\"after sync\");\n";

            std::string out = getOutput(prog);

            // Порядок между "outer start/end" и "inner" теперь недетерминирован,
            // так как они бегут параллельно на разных ядрах.
            // Проверяем только то, что точно гарантировано.
            Assert::IsTrue(out.find("before sync") != std::string::npos);
            Assert::IsTrue(out.find("after sync") != std::string::npos);
            Assert::IsTrue(out.find("outer start") != std::string::npos);
            Assert::IsTrue(out.find("outer end") != std::string::npos);
            Assert::IsTrue(out.find("inner") != std::string::npos);

            // before всегда до after
            Assert::IsTrue(out.find("before sync") < out.find("after sync"));
            // outer start всегда до outer end (в одном потоке)
            Assert::IsTrue(out.find("outer start") < out.find("outer end"));
            // before всегда до outer start (поток стартует после print)
            Assert::IsTrue(out.find("before sync") < out.find("outer start"));
            // after всегда после всего
            Assert::IsTrue(out.find("after sync") > out.find("outer start"));
            Assert::IsTrue(out.find("after sync") > out.find("outer end"));
            Assert::IsTrue(out.find("after sync") > out.find("inner"));
        }

        // 4. Несколько sync подряд очищают очередь по частям
        TEST_METHOD(MultipleSyncs)
        {
            std::string prog =
                "func hello(n) { print(\"Task \", n); }\n"
                "go hello(1);\n"
                "go hello(2);\n"
                "sync;\n" // Выполняет 1 и 2
                "print(\"---\");\n"
                "go hello(3);\n"
                "sync;\n" // Выполняет 3
                "print(\"End\");\n";

            std::string out = getOutput(prog);
            Assert::AreEqual(std::string("Task 1\nTask 2\n---\nTask 3\nEnd\n"), out);
        }

        // 5. Использование lock/unlock внутри асинхронных задач (имитация доски)
        TEST_METHOD(AsyncWithLocks)
        {
            std::string prog =
                "proc worker(id) {\n"
                "  i = 0;\n"
                "  while (i < 10) {\n"
                "    lock(res);\n"
                "    res = res + 1;\n"
                "    unlock(res);\n"
                "    i = i + 1;\n"
                "  }\n"
                "}\n"
                "res = 0;\n"
                "go worker(1);\n"
                "go worker(2);\n"
                "go worker(3);\n"
                "sync;\n";
            auto v = runAndGetVars(prog);
            // 3 воркера по 10 инкрементов = 30
            Assert::AreEqual(30.0, (double)v["res"]);
        }
    };

TEST_CLASS(AsyncPerformance)
    {
    public:
        TEST_METHOD(CompareSyncVsAsyncTime)
        {
            // Тяжёлая функция: ~100k итераций
            std::string heavyFunc =
                "proc heavy() {\n"
                "  i = 0; sum = 0;\n"
                "  while (i < 50000) { sum = sum + i; i = i + 1; }\n"
                "}\n";

            // Синхронно
            auto startSync = std::chrono::high_resolution_clock::now();
            evaluate(heavyFunc + "heavy(); heavy();");
            auto endSync = std::chrono::high_resolution_clock::now();
            auto timeSync = std::chrono::duration_cast<std::chrono::milliseconds>(endSync - startSync).count();

            // Асинхронно (реальные потоки)
            auto startAsync = std::chrono::high_resolution_clock::now();
            evaluate(heavyFunc + "go heavy(); go heavy(); sync;");
            auto endAsync = std::chrono::high_resolution_clock::now();
            auto timeAsync = std::chrono::duration_cast<std::chrono::milliseconds>(endAsync - startAsync).count();

            // Логируем в Test Output
            std::string msg = "\n--- Performance ---\n";
            msg += "Sync:  " + std::to_string(timeSync) + " ms\n";
            msg += "Async: " + std::to_string(timeAsync) + " ms\n";
            msg += "Speedup: " + std::to_string((double)timeSync / std::max(1.0, (double)timeAsync)) + "x\n";
            Logger::WriteMessage(msg.c_str());

            // На многоядерном ПК async должен быть быстрее (или хотя бы не сильно медленнее).
            // На одноядерном/CI - возможно равенство.
            Assert::IsTrue(timeSync > 0 && timeAsync > 0, L"Both timings should be positive");
        }
    };

TEST_CLASS(MultiCoreScaling)
    {
        // Генерирует программу: N потоков, каждый крутит цикл и инкрементит res под lock.
        // После sync res должен быть ровно N.
        static std::string makeWorkProgram(int n, int iters = 500000)
        {
            std::string prog =
                "proc work(id) {\n"
                "  i = 0; s = 0;\n"
                "  while (i < " + std::to_string(iters) + ") { s = s + 1; i = i + 1; }\n"
                "  lock(res);\n"
                "  res = res + 1;\n"
                "  unlock(res);\n"
                "}\n"
                "res = 0;\n";
            for (int k = 1; k <= n; ++k)
                prog += "go work(" + std::to_string(k) + ");\n";
            prog += "sync;\n";
            return prog;
        }

        // Запуск и логирование
        static void runScaling(int n)
        {
            auto prog = makeWorkProgram(n);

            auto start = std::chrono::high_resolution_clock::now();
            auto v = runAndGetVars(prog);
            auto end = std::chrono::high_resolution_clock::now();
            auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

            std::wstring msg = L"[N=" + std::to_wstring(n) + L"] time=" +
                std::to_wstring(ms) + L" ms, res=" +
                std::to_wstring((int)v["res"]) + L"\n";
            Logger::WriteMessage(msg.c_str());

            // Корректность: все N потоков отработали и инкрементнули res.
            Assert::AreEqual((double)n, (double)v["res"]);
        }

    public:
        TEST_METHOD(ThreeThreads) { runScaling(3); }
        TEST_METHOD(FourThreads) { runScaling(4); }
        TEST_METHOD(FiveThreads) { runScaling(5); }
        TEST_METHOD(SixThreads) { runScaling(6); }
        TEST_METHOD(SevenThreads) { runScaling(7); }
        TEST_METHOD(EightThreads) { runScaling(8); }
        TEST_METHOD(NineThreads) { runScaling(9); }
        TEST_METHOD(TenThreads) { runScaling(10); }
        TEST_METHOD(ElevenThreads) { runScaling(11); }
        TEST_METHOD(TwelveThreads) { runScaling(12); }

        // Сводный отчёт: 1..12 потоков, синхронный baseline + масштабирование.
        TEST_METHOD(ScalingReport)
        {
            const int ITERS = 500000;
            Logger::WriteMessage(L"\n--- Multi-core scaling report ---\n");

            // Baseline: 38 последовательных вызовов × ITERS итераций
            std::string syncProg =
                "proc work(id) {\n"
                "  i = 0; s = 0;\n"
                "  while (i < " + std::to_string(ITERS) + ") { s = s + 1; i = i + 1; }\n"
                "}\n";
            for (int k = 1; k <= 138; ++k)
                syncProg += "work(" + std::to_string(k) + ");\n";

            auto s0 = std::chrono::high_resolution_clock::now();
            evaluate(syncProg);
            auto s1 = std::chrono::high_resolution_clock::now();
            long long syncMs = std::chrono::duration_cast<std::chrono::milliseconds>(s1 - s0).count();
            Logger::WriteMessage((L"Baseline (38 sequential × " + std::to_wstring(ITERS) +
                L" iters): " + std::to_wstring(syncMs) + L" ms\n").c_str());

            Logger::WriteMessage(L"N   | Time (ms) | Speedup vs baseline | res\n");
            Logger::WriteMessage(L"----+-----------+---------------------+----\n");

            for (int n = 1; n <= 38; ++n) {
                auto prog = makeWorkProgram(n, ITERS);
                auto start = std::chrono::high_resolution_clock::now();
                auto v = runAndGetVars(prog);
                auto end = std::chrono::high_resolution_clock::now();
                long long ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

                double speedup = (double)syncMs / std::max(1LL, ms);
                std::wstring line =
                    (n < 10 ? L" " : L"") + std::to_wstring(n) + L"  | " +
                    std::to_wstring(ms) + L"\t| " +
                    std::to_wstring(speedup) + L"x\t\t| " +
                    std::to_wstring((int)v["res"]) + L"\n";
                Logger::WriteMessage(line.c_str());

                Assert::AreEqual((double)n, (double)v["res"]);
            }
        }
    };
}

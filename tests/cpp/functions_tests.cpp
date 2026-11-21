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
TEST_CLASS(AdvancedFunctions)
    {
    public:
        // 1. Рекурсивный расчет чисел Фибоначчи
        TEST_METHOD(RecursiveFibonacci)
        {
            std::string prog =
                "func fib(n) {\n"
                "  if (n < 2) { return n; }\n"
                "  return fib(n - 1) + fib(n - 2);\n"
                "}\n"
                "x = fib(10);";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(55.0, (double)v["x"]);
        }

        // 2. Передача массива в функцию по ссылке (shared_ptr)
        TEST_METHOD(ArrayPassByReference)
        {
            std::string prog =
                "proc modifyArray(arr) {\n"
                "  arr[0] = 99;\n"
                "  arr[1] = arr[0] + 1;\n"
                "}\n"
                "int a = [1, 2, 3];\n"
                "modifyArray(a);\n";
            auto arr = getArrayVar(prog, "a");
            Assert::AreEqual((size_t)3, arr.size());
            Assert::AreEqual(99.0, (double)arr[0]);
            Assert::AreEqual(100.0, (double)arr[1]);
            Assert::AreEqual(3.0, (double)arr[2]); // Третий элемент не тронут
        }

        // 3. Изменение глобальной переменной изнутри функции
        TEST_METHOD(FunctionModifiesGlobal)
        {
            std::string prog =
                "c = 10;\n"
                "proc incGlobal() {\n"
                "  c = c + 5;\n" // Store найдет 'c' в глобальной области
                "}\n"
                "incGlobal();\n"
                "incGlobal();\n";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(20.0, (double)v["c"]);
        }

        // 4. Функция возвращает массив (динамическое создание)
        TEST_METHOD(FunctionReturnsArray)
        {
            std::string prog =
                "func createArray(n) {\n"
                "  int a[3];\n"
                "  a[0] = n;\n"
                "  a[1] = n * 2;\n"
                "  a[2] = n * 3;\n"
                "  return a;\n"
                "}\n"
                "b = createArray(5);\n";
            auto arr = getArrayVar(prog, "b");
            Assert::AreEqual((size_t)3, arr.size());
            Assert::AreEqual(5.0, (double)arr[0]);
            Assert::AreEqual(10.0, (double)arr[1]);
            Assert::AreEqual(15.0, (double)arr[2]);
        }

        // 5. Функция с несколькими параметрами и отсутствием return (возвращает 0)
        TEST_METHOD(DefaultReturnValue)
        {
            std::string prog =
                "func doNothing(a, b) {\n"
                "  x = a + b;\n" // Просто вычисляем, но не возвращаем
                "}\n"
                "y = doNothing(10, 20);\n";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(0.0, (double)v["y"]); // Неявный return 0.0
        }
    };
}

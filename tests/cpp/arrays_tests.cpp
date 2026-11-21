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
TEST_CLASS(ArraysInit)
    {
    public:
        TEST_METHOD(ArrayWithSize)
        {
            auto arr = getArrayVar("int a[5];", "a");
            Assert::AreEqual<size_t>(5, arr.size());
            for (double v : arr) Assert::AreEqual(0.0, v);
        }

        TEST_METHOD(ArrayWithValues)
        {
            auto arr = getArrayVar("int b = [7, 5, 2];", "b");
            Assert::AreEqual<size_t>(3, arr.size());
            Assert::AreEqual(7.0, arr[0]);
            Assert::AreEqual(5.0, arr[1]);
            Assert::AreEqual(2.0, arr[2]);
        }

        TEST_METHOD(SingleElementArray)
        {
            auto arr = getArrayVar("int d = [5];", "d");
            Assert::AreEqual<size_t>(1, arr.size());
            Assert::AreEqual(5.0, arr[0]);
        }

        TEST_METHOD(ResizeArray)
        {
            auto arr = getArrayVar("int b = [1, 2]; resize(b, 5);", "b");
            Assert::AreEqual<size_t>(5, arr.size());
            Assert::AreEqual(1.0, arr[0]);
            Assert::AreEqual(0.0, arr[2]); // новые элементы заполняются нулями
        }
    };

TEST_CLASS(ArraysAccess)
    {
    public:
        TEST_METHOD(ReadElement)
        {
            auto v = runAndGetVars("int b = [7, 5, 2]; int x = b[1];");
            Assert::AreEqual(5.0, v["x"]);
        }

        TEST_METHOD(WriteElement)
        {
            auto arr = getArrayVar("int b = [7, 5, 2]; b[1] = 99;", "b");
            Assert::AreEqual(7.0, arr[0]);
            Assert::AreEqual(99.0, arr[1]);
            Assert::AreEqual(2.0, arr[2]);
        }

        TEST_METHOD(WriteWithExpressionIndex)
        {
            auto arr = getArrayVar("int a = [0, 0, 0]; int i = 2; a[i - 1] = 42;", "a");
            Assert::AreEqual(0.0, arr[0]);
            Assert::AreEqual(42.0, arr[1]);
            Assert::AreEqual(0.0, arr[2]);
        }

        TEST_METHOD(ReadOutOfBounds_Throws)
        {
            bool threw = false;
            try {
                // evaluate запускает и компилятор, и виртуальную машину
                evaluate("int a = [1]; int x = a[5];");
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Expected an out-of-bounds exception");
        }
    };

TEST_CLASS(ComplexArrays)
    {
    public:
        TEST_METHOD(WhiteboardExample)
        {
            // b = [10, 20, 30, 40, 50, 60]
            // i = 0
            // x = b[b[i+1]+4] => i+1 = 1 => b[1] = 20 => 20+4 = 24 => b[24] - ошибка!
            // Изменим данные, чтобы не выходить за пределы:
            // b = [4, 2, 7, 5, 9] (размер 6)
            // i = 0. b[i+1] => b[1] = 2. 2+4 = 6 => b[6] - опять выход.
            // Сделаем b подлиннее: b = [1, 1, 1, 1, 1, 10]
            // i = 0. b[i+1] => b[1] = 1. 1+4 = 5 => b[5] = 10.
            std::string prog =
                "int b = [1, 1, 1, 1, 1, 10];"
                "int i = 0;"
                "int x = b[b[i+1]+4];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(10.0, v["x"]);
        }

        TEST_METHOD(ArrayInLoop)
        {
            // Заполняем массив квадратами чисел
            std::string prog =
                "int arr[5];"
                "int i = 0;"
                "while (i < 5) {"
                "  arr[i] = i * i;"
                "  i = i + 1;"
                "}";
            auto arr = getArrayVar(prog, "arr");
            Assert::AreEqual(0.0, arr[0]);
            Assert::AreEqual(1.0, arr[1]);
            Assert::AreEqual(4.0, arr[2]);
            Assert::AreEqual(9.0, arr[3]);
            Assert::AreEqual(16.0, arr[4]);
        }
    };

TEST_CLASS(ArraysLen)
    {
    public:
        TEST_METHOD(LenOnInitializedArray)
        {
            auto v = runAndGetVars("int a = [10, 20, 30, 40]; int x = len(a);");
            Assert::AreEqual(4.0, v["x"]);
        }

        TEST_METHOD(LenOnSizedArray)
        {
            auto v = runAndGetVars("int a[100]; int x = len(a);");
            Assert::AreEqual(100.0, v["x"]);
        }

        TEST_METHOD(LenAfterResize)
        {
            auto v = runAndGetVars("int a = [1, 2]; resize(a, 50); int x = len(a);");
            Assert::AreEqual(50.0, v["x"]);
        }

        TEST_METHOD(LenInExpression)
        {
            auto v = runAndGetVars("int a = [1, 2, 3]; int x = len(a) * 2 + 1;");
            Assert::AreEqual(7.0, v["x"]);
        }

        TEST_METHOD(LenInWhileCondition)
        {
            std::string prog =
                "int a[5];"
                "int i = 0;"
                "while (i < len(a)) {"
                "  i = i + 1;"
                "}";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(5.0, v["i"]);
        }

        TEST_METHOD(LenOnPassedArray)
        {
            auto v = runAndGetVars(
                "int myArr = [7, 8, 9];"
                "int size = len(myArr);"
                "int last = myArr[size - 1];");
            Assert::AreEqual(3.0, v["size"]);
            Assert::AreEqual(9.0, v["last"]);
        }

        TEST_METHOD(LenOnNonArray_Throws)
        {
            bool threw = false;
            try {
                evaluate("int num = 42; int x = len(num);");
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Expected exception when calling len() on a number");
        }
    };

TEST_CLASS(ArrayDynamicResize)
    {
    public:
        // ----- УВЕЛИЧЕНИЕ (Рост) -----

        TEST_METHOD(GrowDoubleSize)
        {
            // Увеличиваем размер в 2 раза
            auto arr = getArrayVar("int a = [1, 2, 3]; resize(a, len(a) * 2);", "a");
            Assert::AreEqual<size_t>(6, arr.size());
            Assert::AreEqual(1.0, arr[0]);
            Assert::AreEqual(0.0, arr[3]); // новые элементы заполнены нулями
        }

        TEST_METHOD(GrowByConstant)
        {
            // Прибавляем к размеру константу
            auto arr = getArrayVar("int a[2]; resize(a, len(a) + 8);", "a");
            Assert::AreEqual<size_t>(10, arr.size());
        }

        TEST_METHOD(GrowLoop)
        {
            // Удваиваем размер в цикле 3 раза: 2 -> 4 -> 8 -> 16
            auto arr = getArrayVar(
                "int a[2];"
                "int i = 0;"
                "while (i < 3) {"
                "  resize(a, len(a) * 2);"
                "  i = i + 1;"
                "}",
                "a");
            Assert::AreEqual<size_t>(16, arr.size());
        }

        TEST_METHOD(GrowByFormula)
        {
            // Формула: len(a) * len(a) + 1 (3*3+1 = 10)
            auto arr = getArrayVar("int a = [1, 2, 3]; resize(a, len(a) * len(a) + 1);", "a");
            Assert::AreEqual<size_t>(10, arr.size());
        }


        // ----- УМЕНЬШЕНИЕ (Сжатие) -----

        TEST_METHOD(ShrinkHalfSize)
        {
            // Уменьшаем размер в 2 раза
            auto arr = getArrayVar("int a = [10, 20, 30, 40, 50, 60]; resize(a, len(a) / 2);", "a");
            Assert::AreEqual<size_t>(3, arr.size());
            Assert::AreEqual(10.0, arr[0]); // первые элементы сохраняются
            Assert::AreEqual(30.0, arr[2]);
        }

        TEST_METHOD(ShrinkByConstant)
        {
            // Отнимаем от размера константу
            auto arr = getArrayVar("int a[10]; resize(a, len(a) - 7);", "a");
            Assert::AreEqual<size_t>(3, arr.size());
        }

        TEST_METHOD(ShrinkToZero)
        {
            // Сжимаем в ноль
            auto arr = getArrayVar("int a[100]; resize(a, len(a) - len(a));", "a");
            Assert::AreEqual<size_t>(0, arr.size());
        }

        TEST_METHOD(ShrinkLoop)
        {
            // Уменьшаем размер в цикле 3 раза: 16 -> 8 -> 4 -> 2
            auto arr = getArrayVar(
                "int a[16];"
                "int i = 0;"
                "while (i < 3) {"
                "  resize(a, len(a) / 2);"
                "  i = i + 1;"
                "}",
                "a");
            Assert::AreEqual<size_t>(2, arr.size());
        }


        // ----- СМЕШАННЫЕ СЦЕНАРИИ (Рост и Сжатие) -----

        TEST_METHOD(GrowThenShrink)
        {
            // 5 -> +5 -> 10 -> /2 -> 5
            auto arr = getArrayVar(
                "int a = [1, 2, 3, 4, 5];"
                "resize(a, len(a) + 5);"
                "resize(a, len(a) / 2);",
                "a");
            Assert::AreEqual<size_t>(5, arr.size());
            Assert::AreEqual(5.0, arr[4]); // данные не потерялись
        }

        TEST_METHOD(ShrinkThenGrow)
        {
            // 5 -> -2 -> 3 -> *3 -> 9
            auto arr = getArrayVar(
                "int a = [10, 20, 30, 40, 50];"
                "resize(a, len(a) - 2);" // стало 3
                "resize(a, len(a) * 3);", // стало 9
                "a");
            Assert::AreEqual<size_t>(9, arr.size());
            Assert::AreEqual(10.0, arr[0]);
            Assert::AreEqual(30.0, arr[2]);
            Assert::AreEqual(0.0, arr[5]); // новые элементы — нули
        }

        TEST_METHOD(ChainResize)
        {
            // Сложная цепочка: 1 -> *10 -> 10 -> +10 -> 20 -> /4 -> 5
            auto arr = getArrayVar(
                "int a = [1];"
                "resize(a, len(a) * 10);"
                "resize(a, len(a) + 10);"
                "resize(a, len(a) / 4);",
                "a");
            Assert::AreEqual<size_t>(5, arr.size());
            Assert::AreEqual(1.0, arr[0]);
            Assert::AreEqual(0.0, arr[1]);
        }


        // ----- ПРОВЕРКА ОШИБОК И ГРАНИЦ -----

        TEST_METHOD(ShrinkOutOfBoundsAccess_Throws)
        {
            // После сжатия доступ к старым индексам должен вызывать ошибку
            bool threw = false;
            try {
                // Размер был 5, стал 2. Пытаемся прочитать a[4]
                evaluate(
                    "int a[5];"
                    "resize(a, len(a) - 3);"
                    "int x = a[4];"
                );
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Expected out-of-bounds exception after shrinking");
        }

        TEST_METHOD(NegativeResize_Throws)
        {
            // Попытка сделать размер отрицательным
            bool threw = false;
            try {
                evaluate("int a[2]; resize(a, len(a) - 5);");
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Expected exception on negative size");
        }
    };

TEST_CLASS(DeepNestedArraysAndMath)
    {
    public:
        TEST_METHOD(SimpleNestedArrayIndex)
        {
            // a[b[0]] — используем массив как индекс для другого массива
            // b[0] = 2, значит берем a[2]
            std::string prog =
                "int b = [2, 1, 0];"
                "int a = [10, 20, 30];"
                "x = a[b[0]];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(30.0, v["x"]);
        }

        TEST_METHOD(MathFunctionAsIndex)
        {
            // a[sin(pi/2) + 1]
            // sin(pi/2) = 1, 1 + 1 = 2, берем a[2]
            std::string prog =
                "pi = 3.141592653589793;"
                "int a = [10, 20, 30];"
                "x = a[sin(pi/2) + 1];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(30.0, v["x"]);
        }

        TEST_METHOD(MathInsideArrayInsideMath)
        {
            // sin(a[cos(0) + 1])
            // cos(0) = 1, 1 + 1 = 2. a[2] = pi/2. sin(pi/2) = 1.
            std::string prog =
                "pi = 3.141592653589793;"
                "int a = [0, 0, 1.5707963267948966];" // a[2] = pi/2
                "x = sin(a[cos(0) + 1]);";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(1.0, v["x"], 0.00001);
        }

        TEST_METHOD(UserExampleExact)
        {
            // Точная копия вашего примера: a[sin(a[1+cos(a[sin(pi/2)])])]
            std::string prog =
                "pi = 3.141592653589793;"
                "int a = [42, 0.8414709848078965, 1.5707963267948966];"
                "x = sin(a[1+cos(a[sin(pi/2)])]);";

            // Как это вычисляется:
            // 1. sin(pi/2) = 1.0
            // 2. a[1] = 0.84147
            // 3. cos(0.84147) = 0.66636
            // 4. 1 + 0.66636 = 1.66636
            // 5. a[1.66636] -> приведение к int = a[1] = 0.84147
            // 6. sin(0.84147) = 0.74562
            // 7. a[0.74562] -> приведение к int = a[0] = 42.0

            auto v = runAndGetVars(prog);
            Assert::AreEqual(0.74562, v["x"], 0.00001);
        }

        TEST_METHOD(ExtremeNesting)
        {
            // a[b[a[0]]]
            // a[0] = 1 -> b[1] = 2 -> a[2] = 30
            std::string prog =
                "int a = [1, 10, 30];"
                "int b = [0, 2, 40];"
                "x = a[b[a[0]]];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(30.0, v["x"]);
        }

        TEST_METHOD(NestedFunctionCalls)
        {
            // sin(cos(sin(pi/2)))
            // sin(pi/2) = 1 -> cos(1) = 0.5403 -> sin(0.5403) = 0.5143
            std::string prog =
                "pi = 3.141592653589793;"
                "x = sin(cos(sin(pi/2)));";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(0.514395, v["x"], 0.00001);
        }
        TEST_METHOD(ArrayInsideArrayInsideCos)
        {
            // cos( arr1[ arr2[0] ] )
            // arr2[0] = 1 -> arr1[1] = 0 -> cos(0) = 1.0
            std::string prog =
                "int arr2 = [1, 0];"
                "int arr1 = [1.5707963267948966, 0];"
                "x = cos( arr1[ arr2[0] ] );";

            auto v = runAndGetVars(prog);
            Assert::AreEqual(1.0, v["x"], 0.00001);
        }

        TEST_METHOD(DeepNestedMathWrappedInArray)
        {
            // sin( cos( sin( arr[0] ) ) )
            // arr[0] = pi -> sin(pi) = 0 -> cos(0) = 1 -> sin(1) = 0.84147
            std::string prog =
                "pi = 3.141592653589793;"
                "int arr = [3.141592653589793];"
                "x = sin( cos( sin( arr[0] ) ) );";

            auto v = runAndGetVars(prog);
            Assert::AreEqual(0.8414709848, v["x"], 0.00001);
        }
    };
}

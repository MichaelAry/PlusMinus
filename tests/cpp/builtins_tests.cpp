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
TEST_CLASS(MathFunctions)
    {
    public:
        // ----- Синус (sin) -----
        TEST_METHOD(SinZero)
        {
            // sin(0) = 0
            Assert::AreEqual(0.0, evaluate("sin(0)"), 0.00001);
        }

        TEST_METHOD(SinPiHalf)
        {
            // sin(pi/2) = 1
            Assert::AreEqual(1.0, evaluate("sin(3.141592653589793 / 2)"), 0.00001);
        }

        TEST_METHOD(SinPi)
        {
            // sin(pi) = 0
            Assert::AreEqual(0.0, evaluate("sin(3.141592653589793)"), 0.00001);
        }

        TEST_METHOD(SinWithExpression)
        {
            // sin(pi/6) = 0.5
            Assert::AreEqual(0.5, evaluate("sin(3.141592653589793 / 6)"), 0.00001);
        }

        TEST_METHOD(SinWithVariable)
        {
            // Использование переменной в качестве аргумента
            auto v = runAndGetVars("pi = 3.141592653589793; x = sin(pi / 2);");
            Assert::AreEqual(1.0, v["x"], 0.00001);
        }

        // ----- Косинус (cos) -----
        TEST_METHOD(CosZero)
        {
            // cos(0) = 1
            Assert::AreEqual(1.0, evaluate("cos(0)"), 0.00001);
        }

        TEST_METHOD(CosPiHalf)
        {
            // cos(pi/2) = 0
            Assert::AreEqual(0.0, evaluate("cos(3.141592653589793 / 2)"), 0.00001);
        }

        TEST_METHOD(CosPi)
        {
            // cos(pi) = -1
            Assert::AreEqual(-1.0, evaluate("cos(3.141592653589793)"), 0.00001);
        }

        TEST_METHOD(CosWithExpression)
        {
            // cos(pi/3) = 0.5
            Assert::AreEqual(0.5, evaluate("cos(3.141592653589793 / 3)"), 0.00001);
        }

        // ----- Комбинации и вложенность -----
        TEST_METHOD(SinCosCombo)
        {
            // sin(pi/2) + cos(0) = 1 + 1 = 2
            Assert::AreEqual(2.0, evaluate("sin(3.141592653589793 / 2) + cos(0)"), 0.00001);
        }

        TEST_METHOD(NestedMath)
        {
            // sin(cos(0)) = sin(1) = 0.84147...
            // Используем std::sin напрямую в C++, чтобы получить точное значение
            Assert::AreEqual(std::sin(1.0), evaluate("sin(cos(0))"), 0.00001);
        }

        TEST_METHOD(MathInLoop)
        {
            // Вычисление синусов углов и сохранение в массив
            std::string prog =
                "int a[3];"
                "pi = 3.141592653589793;"
                "a[0] = sin(0);"
                "a[1] = sin(pi / 2);"
                "a[2] = sin(pi);";
            auto arr = getArrayVar(prog, "a");
            Assert::AreEqual(0.0, arr[0], 0.00001);
            Assert::AreEqual(1.0, arr[1], 0.00001);
            Assert::AreEqual(0.0, arr[2], 0.00001);
        }

        // ----- Обработка ошибок -----
        TEST_METHOD(SinWrongArgCount_Throws)
        {
            bool threw = false;
            try { evaluate("sin()"); }
            catch (...) { threw = true; }
            Assert::IsTrue(threw, L"sin() without arguments should throw");

            threw = false;
            try { evaluate("sin(1, 2)"); }
            catch (...) { threw = true; }
            Assert::IsTrue(threw, L"sin(1, 2) with 2 arguments should throw");
        }

        TEST_METHOD(SinOnArray_Throws)
        {
            bool threw = false;
            try {
                evaluate("int a = [1, 2]; x = sin(a);");
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"sin() on an array should throw");
        }
    };

TEST_CLASS(PrintFunctionMultiArgs)
    {
    public:
        TEST_METHOD(PrintTwoNumbers)
        {
            std::string out = getOutput("print(10, 20);");
            Assert::AreEqual(std::string("10 20\n"), out);
        }

        TEST_METHOD(PrintThreeNumbers)
        {
            std::string out = getOutput("print(1, 2, 3);");
            Assert::AreEqual(std::string("1 2 3\n"), out);
        }

        TEST_METHOD(PrintMixedTypes)
        {
            std::string out = getOutput("int a = [1, 2222, 4, 11]; print(42, a, 99);");
            Assert::AreEqual(std::string("42 [1, 2222, 4, 11] 99\n"), out);
        }

        TEST_METHOD(PrintExpressions)
        {
            std::string out = getOutput("print(2 + 2, 3 * 3, 10 / 2);");
            Assert::AreEqual(std::string("4 9 5\n"), out);
        }

        TEST_METHOD(PrintNoArgs)
        {
            // Печать без аргументов просто выведет пустую строку
            std::string out = getOutput("print();");
            Assert::AreEqual(std::string("\n"), out);
        }
    };

TEST_CLASS(PowFunction)
    {
    public:
        TEST_METHOD(PowBasic)
        {
            Assert::AreEqual(8.0, evaluate("pow(2, 3)"));
            Assert::AreEqual(81.0, evaluate("pow(3, 4)"));
        }

        TEST_METHOD(PowZeroAndOne)
        {
            Assert::AreEqual(1.0, evaluate("pow(5, 0)"));  // Любое число в 0 степени = 1
            Assert::AreEqual(1.0, evaluate("pow(1, 100)"));
            Assert::AreEqual(0.0, evaluate("pow(0, 5)"));
        }

        TEST_METHOD(PowNegativeExp)
        {
            // 2^(-2) = 1 / 2^2 = 0.25
            Assert::AreEqual(0.25, evaluate("pow(2, -2)"), 0.000001);
        }

        TEST_METHOD(PowWithExpressions)
        {
            // (1+1)^(2*2) = 2^4 = 16
            Assert::AreEqual(16.0, evaluate("pow(1 + 1, 2 * 2)"));
        }

        TEST_METHOD(PowWithVariables)
        {
            auto v = runAndGetVars("base = 3; exp = 2; x = pow(base, exp);");
            Assert::AreEqual(9.0, v["x"]);
        }

        TEST_METHOD(PowWithArrays)
        {
            // arr[0]^arr[1] = 2^4 = 16
            std::string prog =
                "int arr = [2, 4];"
                "x = pow(arr[0], arr[1]);";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(16.0, v["x"]);
        }

        TEST_METHOD(PowNestedMath)
        {
            // pow(sin(pi/2), 2) + pow(cos(0), 2) = 1^2 + 1^2 = 2
            std::string prog =
                "pi = 3.141592653589793;"
                "x = pow(sin(pi/2), 2) + pow(cos(0), 2);";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(2.0, v["x"], 0.00001);
        }

        TEST_METHOD(PowInsideArrayIndex)
        {
            // arr[ pow(2, 1) ] -> arr[2] = 30
            std::string prog =
                "int arr = [10, 20, 30, 40];"
                "x = arr[ pow(2, 1) ];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(30.0, v["x"]);
        }

        TEST_METHOD(PowCombinedWithOtherFunctions)
        {
            // pow( cos( sin(pi/2) ), 2 ) -> sin(pi/2)=1, cos(1)=0.5403, 0.5403^2 = 0.2919
            std::string prog =
                "pi = 3.141592653589793;"
                "x = pow( cos( sin(pi/2) ), 2 );";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(0.29192658, v["x"], 0.00001);
        }

        TEST_METHOD(PowWrongArgCount_Throws)
        {
            bool threw = false;
            try { evaluate("pow(2);"); }
            catch (...) { threw = true; }
            Assert::IsTrue(threw, L"pow(2) with 1 argument should throw");

            threw = false;
            try { evaluate("pow(2, 3, 4);"); }
            catch (...) { threw = true; }
            Assert::IsTrue(threw, L"pow(2, 3, 4) with 3 arguments should throw");
        }
    };

TEST_CLASS(Factorial)
    {
    public:
        TEST_METHOD(BasicFactorialOperator)
        {
            Assert::AreEqual(1.0, evaluate("0!"));
            Assert::AreEqual(1.0, evaluate("1!"));
            Assert::AreEqual(2.0, evaluate("2!"));
            Assert::AreEqual(6.0, evaluate("3!"));
            Assert::AreEqual(24.0, evaluate("4!"));
            Assert::AreEqual(120.0, evaluate("5!"));
        }

        TEST_METHOD(BasicFactorialFunction)
        {
            Assert::AreEqual(1.0, evaluate("fact(0)"));
            Assert::AreEqual(120.0, evaluate("fact(5)"));
        }

        TEST_METHOD(FactorialPrecedence)
        {
            // ! имеет более высокий приоритет, чем * и ^
            // 3! * 2 = 6 * 2 = 12
            Assert::AreEqual(12.0, evaluate("3! * 2"));

            // 2 ^ 3! = 2 ^ 6 = 64
            Assert::AreEqual(64.0, evaluate("2 ^ 3!"));

            // 3! ^ 2 = 6 ^ 2 = 36
            Assert::AreEqual(36.0, evaluate("3! ^ 2"));
        }

        TEST_METHOD(FactorialWithUnaryMinus)
        {
            // -3! = -(3!) = -6
            Assert::AreEqual(-6.0, evaluate("-3!"));
            // -(3!) = -6
            Assert::AreEqual(-6.0, evaluate("-(3!)"));
        }

        TEST_METHOD(FactorialInExpressions)
        {
            // (2 + 2)! = 4! = 24
            Assert::AreEqual(24.0, evaluate("(2 + 2)!"));

            // 3! + 4! = 6 + 24 = 30
            Assert::AreEqual(30.0, evaluate("3! + 4!"));
        }

        TEST_METHOD(FactorialWithArrays)
        {
            // arr[3!] -> arr[6] = 60
            std::string prog =
                "int arr = [10, 20, 30, 40, 50, 60, 70];"
                "x = arr[3!];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(70.0, v["x"]); // Индексы с 0: arr[6] это 7-й элемент (70)
        }

        TEST_METHOD(FactorialWrongInput_Throws)
        {
            bool threw = false;
            try {
                evaluate("(-5)!"); // Отрицательный факториал
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Factorial of negative should throw");

            threw = false;
            try {
                evaluate("2.5!"); // Дробный факториал
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw, L"Factorial of float should throw");
        }
    };

TEST_CLASS(MultiFactorial)
    {
    public:
        TEST_METHOD(DoubleFactorial)
        {
            // 5!! = 5 * 3 * 1 = 15
            Assert::AreEqual(15.0, evaluate("5!!"));
            // 6!! = 6 * 4 * 2 = 48
            Assert::AreEqual(48.0, evaluate("6!!"));
            // 7!! = 7 * 5 * 3 * 1 = 105
            Assert::AreEqual(105.0, evaluate("7!!"));
        }

        TEST_METHOD(TripleFactorial)
        {
            // 5!!! = 5 * 2 = 10
            Assert::AreEqual(10.0, evaluate("5!!!"));
            // 7!!! = 7 * 4 * 1 = 28
            Assert::AreEqual(28.0, evaluate("7!!!"));
            // 8!!! = 8 * 5 * 2 = 80
            Assert::AreEqual(80.0, evaluate("8!!!"));
        }

        TEST_METHOD(DoubleFactorialWithSpaces)
        {
            // Пробелы не должны ломать логику
            Assert::AreEqual(15.0, evaluate("5 ! !"));
        }

        TEST_METHOD(RepeatedFactorialInBrackets)
        {
            // Если нужен именно (3!)! = 6! = 720, используем скобки
            Assert::AreEqual(720.0, evaluate("(3!)!"));

            // (2!)! = 2! = 2
            Assert::AreEqual(2.0, evaluate("(2!)!"));
        }

        TEST_METHOD(MultiFactorialInExpression)
        {
            // 3!! + 4!! = 3 + 8 = 11
            Assert::AreEqual(11.0, evaluate("3!! + 4!!"));

            // 2 ^ 3!! = 2 ^ 3 = 8
            Assert::AreEqual(8.0, evaluate("2 ^ 3!!"));
        }

        TEST_METHOD(MultiFactorialWithArray)
        {
            // arr[3!!] -> arr[3] = 40
            std::string prog =
                "int arr = [10, 20, 30, 40, 50];"
                "x = arr[3!!];";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(40.0, v["x"]);
        }
        TEST_METHOD(SinTeilor)
        {
            std::string prog =
                "float pi = 3.141592653589793;"
                "float x = pi/2, sum = 0;"
                "while i < 10 {"
                    "sum = sum + pow(-1, i) * x^(2 * i + 1)/((2 * i + 1)!);"
                    "i = i+1;"
                "}";

            auto v = runAndGetVars(prog);
            Assert::AreEqual(std::sin(3.141592653589793 / 2), v["sum"], 0.01);

        }
    };
}

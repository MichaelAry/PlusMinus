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
TEST_CLASS(IfBasic)
    {
    public:
        TEST_METHOD(TrueBlock) { auto v = runAndGetVars("x = 0; if (1) { x = 1; }"); Assert::AreEqual(1.0, v["x"]); }
        TEST_METHOD(FalseBlock) { auto v = runAndGetVars("x = 0; if (0) { x = 1; }"); Assert::AreEqual(0.0, v["x"]); }
        TEST_METHOD(EmptyTrue) { auto v = runAndGetVars("x = 5; if (1) {}");          Assert::AreEqual(5.0, v["x"]); }
        TEST_METHOD(EmptyFalse) { auto v = runAndGetVars("x = 5; if (0) {}");          Assert::AreEqual(5.0, v["x"]); }

        TEST_METHOD(VarCondition) { auto v = runAndGetVars("c = 1; x = 0; if (c) { x = 7; }"); Assert::AreEqual(7.0, v["x"]); }
        TEST_METHOD(VarCondition0) { auto v = runAndGetVars("c = 0; x = 0; if (c) { x = 7; }"); Assert::AreEqual(0.0, v["x"]); }

        TEST_METHOD(ComplexCondition) { auto v = runAndGetVars("x = 0; if (2 + 3 > 4) { x = 1; }"); Assert::AreEqual(1.0, v["x"]); }
        TEST_METHOD(AndCondition) { auto v = runAndGetVars("x = 0; if (1 < 2 && 3 > 2) { x = 1; }"); Assert::AreEqual(1.0, v["x"]); }
        TEST_METHOD(AndCondition2) { auto v = runAndGetVars("x = 0; if (1 < 2 && 2 > 3) { x = 1; }"); Assert::AreEqual(0.0, v["x"]); }
    };

TEST_CLASS(IfElse)
    {
    public:
        TEST_METHOD(TrueBranch)
        {
            auto v = runAndGetVars("x = 0; if (1) { x = 1; } else { x = 2; }");
            Assert::AreEqual(1.0, v["x"]);
        }
        TEST_METHOD(FalseBranch)
        {
            auto v = runAndGetVars("x = 0; if (0) { x = 1; } else { x = 2; }");
            Assert::AreEqual(2.0, v["x"]);
        }
        TEST_METHOD(ElseNotTaken_True)
        {
            auto v = runAndGetVars("a = 0; b = 0; if (1) { a = 1; } else { b = 1; }");
            Assert::AreEqual(1.0, v["a"]);
            Assert::AreEqual(0.0, v["b"]);
        }
        TEST_METHOD(ElseNotTaken_False)
        {
            auto v = runAndGetVars("a = 0; b = 0; if (0) { a = 1; } else { b = 1; }");
            Assert::AreEqual(0.0, v["a"]);
            Assert::AreEqual(1.0, v["b"]);
        }
    };

TEST_CLASS(IfNested)
    {
    public:
        TEST_METHOD(IfInIf_TrueTrue)
        {
            auto v = runAndGetVars("x = 0; if (1) { if (1) { x = 5; } }");
            Assert::AreEqual(5.0, v["x"]);
        }
        TEST_METHOD(IfInIf_TrueFalse)
        {
            auto v = runAndGetVars("x = 0; if (1) { if (0) { x = 5; } }");
            Assert::AreEqual(0.0, v["x"]);
        }
        TEST_METHOD(IfInIf_FalseTrue)
        {
            auto v = runAndGetVars("x = 0; if (0) { if (1) { x = 5; } }");
            Assert::AreEqual(0.0, v["x"]);
        }

        TEST_METHOD(ElseIf_First)
        {
            auto v = runAndGetVars(
                "x = 0;"
                "if (1) { x = 1; }"
                "else { if (1) { x = 2; } }");
            Assert::AreEqual(1.0, v["x"]);
        }
        TEST_METHOD(ElseIf_Second)
        {
            auto v = runAndGetVars(
                "x = 0;"
                "if (0) { x = 1; }"
                "else { if (1) { x = 2; } }");
            Assert::AreEqual(2.0, v["x"]);
        }

        TEST_METHOD(TripleNested)
        {
            auto v = runAndGetVars(
                "x = 0;"
                "if (1) {"
                "  if (1) {"
                "    if (1) { x = 9; }"
                "  }"
                "}");
            Assert::AreEqual(9.0, v["x"]);
        }
    };

TEST_CLASS(WhileBasic)
    {
    public:
        TEST_METHOD(ZeroIterations)
        {
            auto v = runAndGetVars("x = 42; while (0) { x = 1; }");
            Assert::AreEqual(42.0, v["x"]);
        }
        TEST_METHOD(SingleIteration)
        {
            auto v = runAndGetVars("i = 1; x = 0; while (i) { x = 1; i = 0; }");
            Assert::AreEqual(1.0, v["x"]);
        }
        TEST_METHOD(CountUp)
        {
            auto v = runAndGetVars("i = 0; while (i < 5) { i = i + 1; }");
            Assert::AreEqual(5.0, v["i"]);
        }
        TEST_METHOD(CountDown)
        {
            auto v = runAndGetVars("i = 10; while (i > 0) { i = i - 1; }");
            Assert::AreEqual(0.0, v["i"]);
        }
        TEST_METHOD(Sum)
        {
            auto v = runAndGetVars(
                "i = 1; sum = 0;"
                "while (i < 6) {"
                "  sum = sum + i;"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(15.0, v["sum"]);   // 1+2+3+4+5
        }
        TEST_METHOD(Product)
        {
            auto v = runAndGetVars(
                "i = 1; p = 1;"
                "while (i < 5) {"
                "  p = p * i;"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(24.0, v["p"]);     // 1*2*3*4
        }
    };

TEST_CLASS(WhileConditions)
    {
    public:
        TEST_METHOD(WithAnd)
        {
            auto v = runAndGetVars(
                "i = 0; s = 0;"
                "while (i < 10 && s < 6) {"
                "  s = s + i;"
                "  i = i + 1;"
                "}");
            // s: 0,1,3,6 — стоп, s=6
            Assert::AreEqual(6.0, v["s"]);
        }
        TEST_METHOD(WithComparisonInBody)
        {
            auto v = runAndGetVars(
                "i = 0; c = 0;"
                "while (i < 10) {"
                "  if (i > 5) { c = c + 1; }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(4.0, v["c"]);      // 6,7,8,9
        }
        TEST_METHOD(Factorial)
        {
            auto v = runAndGetVars(
                "n = 5; f = 1;"
                "while (n > 1) {"
                "  f = f * n;"
                "  n = n - 1;"
                "}");
            Assert::AreEqual(120.0, v["f"]);
        }
        TEST_METHOD(CountEven)
        {
            auto v = runAndGetVars(
                "i = 0; c = 0;"
                "while (i < 20) {"
                "  if (i % 2 < 1) { c = c + 1; }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(10.0, v["c"]);
        }
    };

TEST_CLASS(WhileNested)
    {
    public:
        TEST_METHOD(TwoLoops)
        {
            auto v = runAndGetVars(
                "i = 0; t = 0;"
                "while (i < 3) {"
                "  j = 0;"
                "  while (j < 3) {"
                "    t = t + 1;"
                "    j = j + 1;"
                "  }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(9.0, v["t"]);
        }
        TEST_METHOD(Triangle)
        {
            auto v = runAndGetVars(
                "i = 0; t = 0;"
                "while (i < 4) {"
                "  j = 0;"
                "  while (j < i) {"
                "    t = t + 1;"
                "    j = j + 1;"
                "  }"
                "  i = i + 1;"
                "}");
            // 0+1+2+3 = 6
            Assert::AreEqual(6.0, v["t"]);
        }
    };

TEST_CLASS(WhileWithIf)
    {
    public:
        TEST_METHOD(SumOdd)
        {
            auto v = runAndGetVars(
                "i = 0; s = 0;"
                "while (i < 10) {"
                "  if (i % 2 > 0) { s = s + i; }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(25.0, v["s"]);     // 1+3+5+7+9
        }
        TEST_METHOD(SumEven)
        {
            auto v = runAndGetVars(
                "i = 0; s = 0;"
                "while (i < 10) {"
                "  if (i % 2 < 1) { s = s + i; }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(20.0, v["s"]);     // 0+2+4+6+8
        }
        TEST_METHOD(FirstGreater)
        {
            auto v = runAndGetVars(
                "i = 0; found = 0;"
                "while (i < 20 && found < 1) {"
                "  if (i * i > 50) { found = i; }"
                "  i = i + 1;"
                "}");
            // 7^2 = 49 < 50, 8^2 = 64 > 50 — первое i = 8
            Assert::AreEqual(8.0, v["found"]);
        }
        TEST_METHOD(IfElseInsideWhile)
        {
            auto v = runAndGetVars(
                "i = 0; a = 0; b = 0;"
                "while (i < 10) {"
                "  if (i < 5) { a = a + 1; }"
                "  else { b = b + 1; }"
                "  i = i + 1;"
                "}");
            Assert::AreEqual(5.0, v["a"]);
            Assert::AreEqual(5.0, v["b"]);
        }
    };

TEST_CLASS(Programs)
    {
    public:
        TEST_METHOD(Fibonacci10)
        {
            auto v = runAndGetVars(
                "a = 0; b = 1; n = 0;"
                "while (n < 10) {"
                "  t = a + b;"
                "  a = b;"
                "  b = t;"
                "  n = n + 1;"
                "}");
            Assert::AreEqual(55.0, v["a"]);
            Assert::AreEqual(89.0, v["b"]);
        }

        TEST_METHOD(Gcd)
        {
            // НОД(48, 18) = 6  (алгоритм Евклида)
            auto v = runAndGetVars(
                "a = 48; b = 18;"
                "while (b > 0) {"
                "  t = a % b;"
                "  a = b;"
                "  b = t;"
                "}");
            Assert::AreEqual(6.0, v["a"]);
        }

        TEST_METHOD(PowerOfTwo)
        {
            // 2^10 = 1024
            auto v = runAndGetVars(
                "p = 1; n = 0;"
                "while (n < 10) {"
                "  p = p * 2;"
                "  n = n + 1;"
                "}");
            Assert::AreEqual(1024.0, v["p"]);
        }

        TEST_METHOD(CollatzSteps)
        {
            // Число шагов Коллатца для 27 — длинная история, но работает
            // Возьмём 6: 6 → 3 → 10 → 5 → 16 → 8 → 4 → 2 → 1  (8 шагов)
            auto v = runAndGetVars(
                "n = 6; steps = 0;"
                "while (n > 1) {"
                "  if (n % 2 < 1) { n = n / 2; }"
                "  else { n = 3 * n + 1; }"
                "  steps = steps + 1;"
                "}");
            Assert::AreEqual(1.0, v["n"]);
            Assert::AreEqual(8.0, v["steps"]);
        }

        TEST_METHOD(MaxInSequence)
        {
            auto v = runAndGetVars(
                "i = 0; max = 0;"
                "while (i < 10) {"
                "  v = (i * 7) % 10;"     // псевдослучайные 0..9
                "  if (v > max) { max = v; }"
                "  i = i + 1;"
                "}");
            Assert::IsTrue(v["max"] > 0.0);
        }
    };

TEST_CLASS(Comments)
    {
    public:
        TEST_METHOD(SingleLineAtStart)
        {
            auto v = runAndGetVars("// This is a comment\nx = 5;");
            Assert::AreEqual(5.0, v["x"]);
        }

        TEST_METHOD(SingleLineAtEnd)
        {
            auto v = runAndGetVars("x = 5; // Comment at the end");
            Assert::AreEqual(5.0, v["x"]);
        }

        TEST_METHOD(SingleLineInsideExpression)
        {
            auto v = runAndGetVars("x = 5 + // plus\n 3;");
            Assert::AreEqual(8.0, v["x"]);
        }

        TEST_METHOD(MultiLineSimple)
        {
            auto v = runAndGetVars("/* comment */ x = 10;");
            Assert::AreEqual(10.0, v["x"]);
        }

        TEST_METHOD(MultiLineInsideExpression)
        {
            auto v = runAndGetVars("x = 5 /* mid */ + 3;");
            Assert::AreEqual(8.0, v["x"]);
        }

        TEST_METHOD(MultiLineMultiline)
        {
            std::string prog =
                "x = 1;\n"
                "/*\n"
                "   Multi-line\n"
                "   comment\n"
                "*/\n"
                "x = x + 1;";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(2.0, v["x"]);
        }

        TEST_METHOD(MixedComments)
        {
            std::string prog =
                "// start\n"
                "x = /* inline */ 5;\n"
                "/* block\n"
                "   comment */\n"
                "y = 10; // end\n";
            auto v = runAndGetVars(prog);
            Assert::AreEqual(5.0, v["x"]);
            Assert::AreEqual(10.0, v["y"]);
        }

        TEST_METHOD(DivisionNotComment)
        {
            // Проверяем, что / всё ещё работает как деление
            auto v = runAndGetVars("x = 10 / 2;");
            Assert::AreEqual(5.0, v["x"]);
        }

        TEST_METHOD(UnclosedMultiLineComment_Throws)
        {
            bool threw = false;
            try {
                evaluate("x = 5; /* unclosed comment");
            }
            catch (...) {
                threw = true;
            }
            Assert::IsTrue(threw);
        }
    };
}

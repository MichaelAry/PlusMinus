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
TEST_CLASS(Arithmetic)
    {
    public:
        TEST_METHOD(Add) { Assert::AreEqual(7.0, evaluate("3 + 4")); }
        TEST_METHOD(Sub) { Assert::AreEqual(-1.0, evaluate("3 - 4")); }
        TEST_METHOD(Mul) { Assert::AreEqual(12.0, evaluate("3 * 4")); }
        TEST_METHOD(Div) { Assert::AreEqual(2.5, evaluate("10 / 4")); }
        TEST_METHOD(Mod) { Assert::AreEqual(2.0, evaluate("10 % 4")); }
        TEST_METHOD(Pow) { Assert::AreEqual(81.0, evaluate("3 ^ 4")); }

        TEST_METHOD(Zero) { Assert::AreEqual(0.0, evaluate("0")); }
        TEST_METHOD(Neg) { Assert::AreEqual(-5.0, evaluate("0 - 5")); }
        TEST_METHOD(Float) { Assert::AreEqual(3.5, evaluate("1.5 + 2.0")); }
    };

TEST_CLASS(Precedence)
    {
    public:
        TEST_METHOD(MulOverAdd) { Assert::AreEqual(7.0, evaluate("1 + 2 * 3")); }
        TEST_METHOD(MulOverSub) { Assert::AreEqual(-5.0, evaluate("1 - 2 * 3")); }
        TEST_METHOD(DivOverAdd) { Assert::AreEqual(4.0, evaluate("1 + 6 / 2")); }
        TEST_METHOD(PowOverMul) { Assert::AreEqual(18.0, evaluate("2 * 3 ^ 2")); }
        TEST_METHOD(PowOverAdd) { Assert::AreEqual(10.0, evaluate("1 + 3 ^ 2")); }
        TEST_METHOD(PowOverDiv) { Assert::AreEqual(4.0, evaluate("8 / 2 ^ 1")); }

        TEST_METHOD(Mixed) { Assert::AreEqual(50.0, evaluate("2 + 3 * 4 ^ 2")); }
        TEST_METHOD(Mixed2) { Assert::AreEqual(26.0, evaluate("2 * 3 + 4 * 5")); }
        TEST_METHOD(Mixed3) { Assert::AreEqual(12.0, evaluate("2 + 4 * 10 / 4")); }

        TEST_METHOD(ParensChangeOrder) { Assert::AreEqual(9.0, evaluate("(1 + 2) * 3")); }
        TEST_METHOD(ParensChangeOrder2) { Assert::AreEqual(1.0, evaluate("(1 + 2) % 2")); }
        TEST_METHOD(DeepParens) { Assert::AreEqual(14.0, evaluate("((1 + 2) * (3 + 1) + 2)")); }
    };

TEST_CLASS(Associativity)
    {
    public:
        // Левая ассоциативность: (a-b)-c
        TEST_METHOD(SubLeft) { Assert::AreEqual(5.0, evaluate("10 - 3 - 2")); }
        TEST_METHOD(DivLeft) { Assert::AreEqual(5.0, evaluate("100 / 10 / 2")); }
        TEST_METHOD(ModLeft) { Assert::AreEqual(0.0, evaluate("100 % 7 % 2")); }
        TEST_METHOD(AddLeft) { Assert::AreEqual(6.0, evaluate("1 + 2 + 3")); }
        TEST_METHOD(MulLeft) { Assert::AreEqual(24.0, evaluate("2 * 3 * 4")); }
        TEST_METHOD(MixedLeft) { Assert::AreEqual(6.0, evaluate("10 - 2 - 2")); }

        // Правая ассоциативность: a^(b^c)
        TEST_METHOD(PowRight) { Assert::AreEqual(512.0, evaluate("2 ^ 3 ^ 2")); }
        TEST_METHOD(PowRight2) { Assert::AreEqual(81.0, evaluate("3 ^ 2 ^ 2")); } // 3^4
        TEST_METHOD(PowExplicit) { Assert::AreEqual(64.0, evaluate("(2 ^ 3) ^ 2")); }
        TEST_METHOD(PowRightBig) { Assert::AreEqual(65536.0, evaluate("2 ^ 2 ^ 2 ^ 2")); } // 2^(2^(2^2)) = 2^16

        // Скобки меняют ассоциативность
        TEST_METHOD(ParensSub) { Assert::AreEqual(9.0, evaluate("10 - (3 - 2)")); }
        TEST_METHOD(ParensDiv) { Assert::AreEqual(20.0, evaluate("100 / (10 / 2)")); }
    };

TEST_CLASS(Comparison)
    {
    public:
        TEST_METHOD(LessTrue) { Assert::AreEqual(1.0, evaluate("1 < 2")); }
        TEST_METHOD(LessFalse) { Assert::AreEqual(0.0, evaluate("2 < 1")); }
        TEST_METHOD(LessEqual) { Assert::AreEqual(0.0, evaluate("2 < 2")); }
        TEST_METHOD(GreaterTrue) { Assert::AreEqual(1.0, evaluate("3 > 2")); }
        TEST_METHOD(GreaterFalse) { Assert::AreEqual(0.0, evaluate("1 > 2")); }
        TEST_METHOD(GreaterEq) { Assert::AreEqual(0.0, evaluate("2 > 2")); }

        TEST_METHOD(CompareExpr) { Assert::AreEqual(1.0, evaluate("1 + 1 < 1 + 2")); }
        TEST_METHOD(CompareExpr2) { Assert::AreEqual(0.0, evaluate("5 * 2 > 3 * 5")); }
        TEST_METHOD(CompareChain) { Assert::AreEqual(1.0, evaluate("1 < 2 < 3")); } // (1<2)<3 = 1<3 = 1
        TEST_METHOD(CompareChain2) { Assert::AreEqual(0.0, evaluate("3 > 2 > 1")); } // (3>2)>1 = 1>1 = 0
    };

TEST_CLASS(LogicalAnd)
    {
    public:
        TEST_METHOD(TrueTrue) { Assert::AreEqual(1.0, evaluate("1 && 1")); }
        TEST_METHOD(TrueFalse) { Assert::AreEqual(0.0, evaluate("1 && 0")); }
        TEST_METHOD(FalseTrue) { Assert::AreEqual(0.0, evaluate("0 && 1")); }
        TEST_METHOD(FalseFalse) { Assert::AreEqual(0.0, evaluate("0 && 0")); }

        TEST_METHOD(NonZero) { Assert::AreEqual(1.0, evaluate("5 && 3")); }
        TEST_METHOD(Chain) { Assert::AreEqual(1.0, evaluate("1 && 1 && 1")); }
        TEST_METHOD(ChainFalse) { Assert::AreEqual(0.0, evaluate("1 && 0 && 1")); }

        TEST_METHOD(WithComparisons) { Assert::AreEqual(1.0, evaluate("1 < 2 && 3 > 2")); }
        TEST_METHOD(WithComparisons2) { Assert::AreEqual(0.0, evaluate("1 < 2 && 2 > 3")); }

        TEST_METHOD(AndLowestPrecedence)
        {
            // 1 + 1 && 1 + 1  =>  (1+1) && (1+1)  =>  1
            Assert::AreEqual(1.0, evaluate("1 + 1 && 1 + 1"));
        }
        TEST_METHOD(AndLowerThanCompare)
        {
            // 1 < 2 && 2 < 3  =>  (1<2) && (2<3)  =>  1
            Assert::AreEqual(1.0, evaluate("1 < 2 && 2 < 3"));
        }
    };
}

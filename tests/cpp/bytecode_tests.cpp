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
TEST_CLASS(CodeGenOps)
    {
    public:
        TEST_METHOD(Add) { auto p = compileToCommands("1 + 2"); Assert::IsTrue(p[2].op == OpCode::Add); }
        TEST_METHOD(Sub) { auto p = compileToCommands("1 - 2"); Assert::IsTrue(p[2].op == OpCode::Sub); }
        TEST_METHOD(Mul) { auto p = compileToCommands("1 * 2"); Assert::IsTrue(p[2].op == OpCode::Mul); }
        TEST_METHOD(Div) { auto p = compileToCommands("1 / 2"); Assert::IsTrue(p[2].op == OpCode::Div); }
        TEST_METHOD(Mod) { auto p = compileToCommands("1 % 2"); Assert::IsTrue(p[2].op == OpCode::Mod); }
        TEST_METHOD(Pow) { auto p = compileToCommands("1 ^ 2"); Assert::IsTrue(p[2].op == OpCode::Pow); }
        TEST_METHOD(Less) { auto p = compileToCommands("1 < 2"); Assert::IsTrue(p[2].op == OpCode::Less); }
        TEST_METHOD(Greater) { auto p = compileToCommands("1 > 2"); Assert::IsTrue(p[2].op == OpCode::Greater); }
        TEST_METHOD(And) { auto p = compileToCommands("1 && 2"); Assert::IsTrue(p[2].op == OpCode::And); }
    };

TEST_CLASS(CodeGenControlFlow)
    {
    public:
        TEST_METHOD(IfEmitsJz)
        {
            auto p = compileToCommands("if (1) { x = 5; }");
            bool hasJz = false;
            for (auto& c : p) if (c.op == OpCode::Jz) hasJz = true;
            Assert::IsTrue(hasJz);
        }

        TEST_METHOD(IfNoElse_HasNoJmp)
        {
            auto p = compileToCommands("if (1) { x = 5; }");
            bool hasJmp = false;
            for (auto& c : p) if (c.op == OpCode::Jmp) hasJmp = true;
            Assert::IsFalse(hasJmp);
        }

        TEST_METHOD(IfElse_HasJzAndJmp)
        {
            auto p = compileToCommands("if (1) { x = 1; } else { x = 2; }");
            bool hasJz = false, hasJmp = false;
            for (auto& c : p) {
                if (c.op == OpCode::Jz)  hasJz = true;
                if (c.op == OpCode::Jmp) hasJmp = true;
            }
            Assert::IsTrue(hasJz);
            Assert::IsTrue(hasJmp);
        }

        TEST_METHOD(While_HasJzAndJmp)
        {
            auto p = compileToCommands("while (i < 5) { i = i + 1; }");
            bool hasJz = false, hasJmp = false;
            for (auto& c : p) {
                if (c.op == OpCode::Jz)  hasJz = true;
                if (c.op == OpCode::Jmp) hasJmp = true;
            }
            Assert::IsTrue(hasJz);
            Assert::IsTrue(hasJmp);
        }

        TEST_METHOD(While_JmpTargetsStart)
        {
            auto p = compileToCommands("while (i < 5) { i = i + 1; }");
            int jmpTarget = -1;
            for (auto& c : p) if (c.op == OpCode::Jmp) jmpTarget = c.target;
            Assert::AreEqual(0, jmpTarget);  // цикл начинается с нулевой команды
        }

        TEST_METHOD(AssignmentEmitsStore)
        {
            auto p = compileToCommands("x = 5;");
            bool hasStore = false;
            for (auto& c : p) if (c.op == OpCode::Store) { hasStore = true; Assert::AreEqual(std::string("x"), c.name); }
            Assert::IsTrue(hasStore);
        }

        TEST_METHOD(HaltIsLast)
        {
            auto p = compileToCommands("x = 5;");
            Assert::IsTrue(p.back().op == OpCode::Halt);
        }
    };
}

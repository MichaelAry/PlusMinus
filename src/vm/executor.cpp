#include "plusminus/vm.hpp"
#include "builtins.hpp"
#include <cmath>
#include <functional>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

double VM::executeThread(const std::vector<Command>& program, size_t startIp,
    std::vector<Frame> initialFrames, bool stopOnEmptyReturn)
{
    std::vector<Value> stack;
    std::vector<Frame> localStack = std::move(initialFrames);
    size_t ip = startIp;
    const std::uint64_t traceThread = traceEnabled ? traceThreadNext.fetch_add(1, std::memory_order_relaxed) : 0;

    auto popNum = [&]() {
        if (stack.empty()) throw std::runtime_error("Stack underflow");
        Value v = stack.back(); stack.pop_back();
        if (v.isArray()) throw std::runtime_error("Expected number, got array");
        return v.getNum();
        };

    auto binOp = [&](std::vector<Value>& st, std::function<double(double, double)> f) {
        if (st.size() < 2) throw std::runtime_error("Stack underflow");
        if (st.back().isArray() || st[st.size() - 2].isArray())
            throw std::runtime_error("Cannot perform arithmetic on an array");
        double b = st.back().getNum(); st.pop_back();
        double a = st.back().getNum(); st.pop_back();
        st.push_back(Value(f(a, b)));
        };

    while (ip < program.size()) {
        const Command& c = program[ip];
        if (profileEnabled)
            opcodeCounts[static_cast<std::size_t>(c.op)].fetch_add(1,std::memory_order_relaxed);
        if (traceEnabled) {
            const auto seen = traceSeen.fetch_add(1, std::memory_order_relaxed);
            if (seen < TraceLimit) {
                std::lock_guard<std::mutex> guard(traceMutex);
                traceEvents.push_back({ip, stack.size(),
                    static_cast<std::uint32_t>(c.op), traceThread});
            }
        }
        switch (c.op) {
        case OpCode::PushConst:
            if (c.isStr) stack.push_back(Value(c.str));
            else stack.push_back(Value(c.num));
            break;

        case OpCode::PushVar: {
            bool found = false;
            for (auto it = localStack.rbegin(); it != localStack.rend(); ++it) {
                auto f = it->locals.find(c.name);
                if (f != it->locals.end()) { stack.push_back(f->second); found = true; break; }
            }
            if (!found) {
                std::lock_guard<std::mutex> lock(varsMutex);
                auto it = vars.find(c.name);
                if (it != vars.end()) stack.push_back(it->second);
                else stack.push_back(Value(0.0));
            }
            break;
        }

        case OpCode::Store: {
            if (stack.empty()) throw std::runtime_error("Stack underflow (Store)");
            Value val = stack.back();
            stack.pop_back();

            bool found = false;
            for (auto it = localStack.rbegin(); it != localStack.rend(); ++it) {
                if (it->locals.count(c.name)) {
                    it->locals[c.name] = val;
                    found = true;
                    break;
                }
            }
            if (!found) {
                std::lock_guard<std::mutex> lock(varsMutex);
                if (vars.count(c.name)) {
                    vars[c.name] = val;
                }
                else if (!localStack.empty()) {
                    localStack.back().locals[c.name] = val;
                }
                else {
                    vars[c.name] = val;
                }
            }
            break;
        }

        case OpCode::MakeArray: {
            auto arr = std::make_shared<std::vector<double>>(c.argc);
            for (int i = c.argc - 1; i >= 0; --i) arr->at(i) = popNum();
            stack.push_back(Value(arr)); break;
        }
        case OpCode::MakeArraySized: {
            int size = (int)popNum();
            if (size < 0) throw std::runtime_error("Negative array size");
            stack.push_back(Value(std::make_shared<std::vector<double>>(size, 0.0))); break;
        }
        case OpCode::LoadIndex: {
            double idx = popNum();
            Value arrVal = stack.back(); stack.pop_back();
            if (!arrVal.isArray()) throw std::runtime_error("Not an array");
            auto arr = arrVal.getArr();
            if (idx < 0 || idx >= (double)arr->size()) throw std::runtime_error("Index out of bounds");
            stack.push_back(Value(arr->at((size_t)idx))); break;
        }
        case OpCode::StoreIndex: {
            double val = popNum();
            double idx = popNum();
            Value arrVal = stack.back(); stack.pop_back();
            if (!arrVal.isArray()) throw std::runtime_error("Not an array");
            auto arr = arrVal.getArr();
            if (idx < 0 || idx >= (double)arr->size()) throw std::runtime_error("Index out of bounds");
            arr->at((size_t)idx) = val; break;
        }

        case OpCode::Add:  binOp(stack, [](double a, double b) { return a + b; }); break;
        case OpCode::Sub:  binOp(stack, [](double a, double b) { return a - b; }); break;
        case OpCode::Mul:  binOp(stack, [](double a, double b) { return a * b; }); break;
        case OpCode::Div:  binOp(stack, [](double a, double b) { return a / b; }); break;
        case OpCode::Mod:  binOp(stack, [](double a, double b) { return std::fmod(a, b); }); break;
        case OpCode::Pow:  binOp(stack, [](double a, double b) { return std::pow(a, b); }); break;
        case OpCode::Less: binOp(stack, [](double a, double b) { return a < b ? 1.0 : 0.0; }); break;
        case OpCode::Greater: binOp(stack, [](double a, double b) { return a > b ? 1.0 : 0.0; }); break;
        case OpCode::And:  binOp(stack, [](double a, double b) { return (a != 0.0 && b != 0.0) ? 1.0 : 0.0; }); break;

        case OpCode::Call: {
            if (executeBuiltin(c, stack, output, outputMutex)) {
                break;
            }
            else if (functions.count(c.name)) {
                std::vector<Value> args(c.argc);
                for (int i = c.argc - 1; i >= 0; --i) { args[i] = stack.back(); stack.pop_back(); }
                const FuncInfo& fi = functions[c.name];
                Frame frame;
                frame.returnIp = ip + 1;
                for (size_t i = 0; i < fi.params.size(); ++i)
                    frame.locals[fi.params[i]] = (i < args.size() ? args[i] : Value(0.0));
                localStack.push_back(std::move(frame));
                ip = fi.bodyStart;
                continue;
            }
            else {
                for (int i = 0; i < c.argc; ++i) popNum();
                stack.push_back(Value(0.0));
            }
            break;
        }

        case OpCode::FuncDef:
        case OpCode::ProcDef:
            // Уже зарегистрировано в pre-scan. Просто пропускаем.
            break;

        case OpCode::Return: {
            Value ret = stack.empty() ? Value(0.0) : stack.back();
            if (!stack.empty()) stack.pop_back();

            if (localStack.empty()) {
                if (stopOnEmptyReturn) return ret.getNum();
                ip = program.size();
                continue;
            }

            size_t returnIp = localStack.back().returnIp;
            localStack.pop_back();

            if (localStack.empty() && stopOnEmptyReturn) {
                return ret.getNum();
            }

            ip = returnIp;
            stack.push_back(ret);
            continue;
        }

        case OpCode::GoCall: {
            std::vector<Value> args(c.argc);
            for (int i = c.argc - 1; i >= 0; --i) {
                if (stack.empty()) throw std::runtime_error("Stack underflow in go");
                args[i] = stack.back(); stack.pop_back();
            }
            auto it = functions.find(c.name);
            if (it == functions.end()) {
                for (auto& a : args) (void)a;
                break;
            }
            const FuncInfo& fi = it->second;
            Frame frame;
            frame.returnIp = program.size(); // фиктивный: не используется в потоке
            for (size_t i = 0; i < fi.params.size(); ++i)
                frame.locals[fi.params[i]] = (i < args.size() ? args[i] : Value(0.0));

            std::vector<Frame> initialStack;
            initialStack.push_back(std::move(frame));
            size_t startBody = fi.bodyStart;

            // Реальный поток!
            std::lock_guard<std::mutex> lock(threadsMutex);
            threads.emplace_back(
                [this, prog = &program, startBody, initialStack = std::move(initialStack)]() mutable {
                    try {
                        this->executeThread(*prog, startBody, std::move(initialStack), true);
                    }
                    catch (const std::exception& e) {
                        std::lock_guard<std::mutex> lk(this->outputMutex);
                        this->output += std::string("[thread error] ") + e.what() + "\n";
                    }
                });
            break;
        }

        case OpCode::Sync:
            syncAllThreads();
            break;

        case OpCode::Lock: {
            std::mutex* m = nullptr;
            {
                std::lock_guard<std::mutex> guard(locksMutex);
                if (!namedLocks[c.name]) namedLocks[c.name] = std::make_unique<std::mutex>();
                m = namedLocks[c.name].get();
            }
            m->lock();
            break;
        }
        case OpCode::Unlock: {
            std::mutex* m = nullptr;
            {
                std::lock_guard<std::mutex> guard(locksMutex);
                auto it = namedLocks.find(c.name);
                if (it == namedLocks.end()) break;
                m = it->second.get();
            }
            m->unlock();
            break;
        }

        case OpCode::Jmp: ip = (size_t)c.target; continue;
        case OpCode::Jz:  if (popNum() == 0.0) { ip = (size_t)c.target; continue; } break;
        case OpCode::Pop: if (!stack.empty()) stack.pop_back(); break;
        case OpCode::Halt:
            syncAllThreads(); // ждём все потоки перед выходом
            ip = program.size();
            continue;
        }
        ++ip;
    }
    return stack.empty() ? 0.0 : stack.back().getNum();
}
